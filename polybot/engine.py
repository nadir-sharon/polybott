"""One bot cycle: settle finished markets -> find candidates -> research -> decide -> trade."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from . import risk
from .brokers import LiveBroker, PaperBroker
from .config import Settings
from .report import write_report
from .research import Researcher
from .state import State, now_iso
from .strategy import decide
from .venues.polymarket import Polymarket, fee_rate_for

EST_COST_PER_FORECAST = 0.12   # used only to avoid starting a forecast we can't afford
MAX_RESOLUTION_CHECKS = 40     # per run, keeps API usage polite


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


class Engine:
    def __init__(self, s: Settings | None = None, venue=None, researcher=None, broker=None):
        self.s = s or Settings.load()
        self.state = State(self.s.state_dir / "state.json", self.s.STARTING_BANKROLL_USD)
        self.venue = venue or Polymarket()
        self._researcher = researcher
        if broker is not None:
            self.broker = broker
        else:
            self.broker = LiveBroker(self.s) if self.s.is_live else PaperBroker()

    @property
    def researcher(self):
        if self._researcher is None:
            self._researcher = Researcher(self.s)
        return self._researcher

    # ------------------------------------------------------------------ settle
    def settle(self) -> None:
        now = datetime.now(timezone.utc)
        checks = 0
        cache: dict = {}

        def resolution(mid):
            nonlocal checks
            if mid not in cache:
                if checks >= MAX_RESOLUTION_CHECKS:
                    return None
                checks += 1
                try:
                    cache[mid] = self.venue.get_resolution(mid)
                except Exception as e:  # network hiccup: try again next run
                    self.state.log(f"[settle] could not check {mid}: {e}")
                    cache[mid] = None
            return cache[mid]

        for pid, p in list(self.state.positions.items()):
            if _parse(p["end_date"]) > now:
                continue
            res = resolution(p["market_id"])
            if not res or not res.resolved or res.yes_payout is None:
                continue
            per_share = res.yes_payout if p["side"] == "YES" else 1 - res.yes_payout
            payout = p["shares"] * per_share
            pnl = payout - p["cost"]
            if self.broker.live and payout > 0:
                try:
                    self.broker.redeem(p)
                except Exception as e:
                    self.state.log(f"[settle] redeem failed for {p['question'][:50]} (retry later): {e}")
                    continue
            self.state.cash += payout
            self.state.add_realized(pnl)
            p.update(closed_at=now_iso(), payout=round(payout, 4), pnl=round(pnl, 4),
                     won=pnl > 0, yes_payout=res.yes_payout)
            self.state.data["closed"].append(p)
            del self.state.positions[pid]
            self.state.log(f"[settle] {'WON ' if pnl > 0 else 'LOST'} {pnl:+.2f}  "
                           f"{p['side']} {p['question'][:60]}")

        # score every past forecast (traded or not) so we learn if the AI beats the market
        for f in self.state.data["forecasts"]:
            if "yes_payout" in f or _parse(f["end_date"]) > now:
                continue
            res = resolution(f["market_id"])
            if res and res.resolved and res.yes_payout is not None:
                f["yes_payout"] = res.yes_payout

    # ------------------------------------------------------------------- trade
    def find_and_trade(self) -> None:
        st, s = self.state, self.s
        halt = risk.check_halt(st, s)
        if halt:
            st.log(f"[risk] not opening trades: {halt}")
            return

        try:
            candidates = self.venue.list_candidate_markets(s)
        except Exception as e:
            st.log(f"[scan] market list failed: {e}")
            return
        held_markets = {p["market_id"] for p in st.positions.values()}
        held_events = {p.get("event_id") for p in st.positions.values() if p.get("event_id")}
        cutoff = datetime.now(timezone.utc) - timedelta(hours=s.REFORECAST_AFTER_HOURS)

        fresh = []
        for mk in candidates:
            if mk.id in held_markets or (mk.event_id and mk.event_id in held_events):
                continue
            last = st.last_forecast(mk.id)
            if last and _parse(last["ts"]) > cutoff:
                continue
            fresh.append(mk)
        fresh.sort(key=lambda m: m.volume_24h, reverse=True)
        st.log(f"[scan] {len(candidates)} markets pass filters, {len(fresh)} not recently researched")

        done = 0
        used_events = set()
        for mk in fresh:
            if done >= s.FORECASTS_PER_RUN:
                break
            if mk.event_id and mk.event_id in used_events:
                continue  # one market per event per run: they're correlated
            if st.ai_spend_today() + EST_COST_PER_FORECAST > s.DAILY_AI_BUDGET_USD:
                st.log(f"[budget] daily AI budget ${s.DAILY_AI_BUDGET_USD:.2f} reached "
                       f"(spent ${st.ai_spend_today():.2f})")
                break
            used_events.add(mk.event_id)
            done += 1
            self._evaluate(mk)
            st.save()  # save after each market so a crash loses nothing
            if risk.check_halt(st, s):
                break

    def _evaluate(self, mk) -> None:
        st, s = self.state, self.s
        st.log(f"[research] {mk.question[:90]}")
        try:
            fc, cost = self.researcher.forecast(mk)
        except Exception as e:
            st.log(f"[research] failed: {e}")
            return
        st.add_ai_spend(cost)
        if not fc:
            st.log(f"[research] no usable answer (cost ${cost:.3f})")
            return

        try:
            yes_book = self.venue.get_book(mk.yes_token)
            no_book = self.venue.get_book(mk.no_token)
        except Exception as e:
            st.log(f"[book] failed: {e}")
            return

        eq = risk.equity(st)
        d = decide(mk, fc, yes_book, no_book, eq, st.cash, fee_rate_for(mk), s)
        st.data["forecasts"].append({
            "ts": now_iso(), "market_id": mk.id, "question": mk.question,
            "end_date": mk.end_date.isoformat(), "ai_prob": fc.probability,
            "confidence": fc.confidence, "market_mid": round(d.market_mid, 4),
            "summary": fc.summary, "sources": fc.sources, "cost": round(cost, 4),
            "decision": d.reason, "traded": False, "url": mk.url,
        })
        st.log(f"[decide] AI {fc.probability:.2f} ({fc.confidence}) vs market "
               f"{d.market_mid:.2f} -> {'TRADE ' + d.side if d.trade else 'skip'}: {d.reason}")
        if not d.trade:
            return

        block = risk.check_trade(st, s, mk.id, mk.event_id, d.stake_usd, d.fee_usd)
        if block:
            st.log(f"[risk] blocked: {block}")
            return
        max_px = min(d.avg_price + s.MAX_SLIPPAGE, d.fair_prob - s.MIN_EDGE / 2)
        try:
            fill = self.broker.buy(d, max_px)
        except Exception as e:
            st.log(f"[order] FAILED: {e}")
            return
        if not fill:
            st.log("[order] nothing filled")
            return

        st.cash -= fill.cost_usd
        pid = uuid.uuid4().hex[:10]
        st.positions[pid] = {
            "id": pid, "opened_at": now_iso(), "market_id": mk.id, "event_id": mk.event_id,
            "condition_id": mk.condition_id, "question": mk.question, "url": mk.url,
            "end_date": mk.end_date.isoformat(), "side": d.side, "token_id": d.token_id,
            "shares": round(fill.shares, 6), "avg_price": round(fill.avg_price, 4),
            "cost": round(fill.cost_usd, 4), "fair_prob": round(d.fair_prob, 4),
            "edge": round(d.edge, 4), "ai_prob": fc.probability, "confidence": fc.confidence,
            "market_mid": round(d.market_mid, 4), "order_id": fill.order_id,
            "mode": s.MODE,
        }
        st.data["forecasts"][-1]["traded"] = True
        st.log(f"[order] {'LIVE' if self.broker.live else 'PAPER'} BUY {d.side} "
               f"{fill.shares:.2f} sh @ {fill.avg_price:.3f} = ${fill.cost_usd:.2f}  "
               f"(edge {d.edge:+.3f})  {mk.question[:60]}")

    # --------------------------------------------------------------------- run
    def reconcile_live_cash(self) -> None:
        if not self.broker.live:
            return
        try:
            bal = self.broker.cash_balance()
        except Exception as e:
            self.state.log(f"[live] balance check failed: {e}")
            return
        if bal + 0.01 < self.state.cash:
            self.state.log(f"[live] wallet has ${bal:.2f}, bot thought ${self.state.cash:.2f}; using wallet")
            self.state.cash = bal

    def run_once(self, trade: bool = True) -> None:
        st = self.state
        st.log(f"=== run start ({self.s.MODE} mode) cash ${st.cash:.2f}, "
               f"{len(st.positions)} open ===")
        self.reconcile_live_cash()
        self.settle()
        st.save()
        if trade:
            self.find_and_trade()
        st.save()
        write_report(st, self.s)

"""Offline tests: no network, no API keys, no money.  Run:  python -m pytest -q"""
from datetime import datetime, timedelta, timezone

import pytest

from polybot.brokers import PaperBroker
from polybot.config import Settings
from polybot.engine import Engine
from polybot.research import Forecast, extract_json, validate
from polybot.strategy import decide, kelly_fraction, taker_fee, walk_book
from polybot.venues.base import Book, Market, Resolution
from polybot.venues.polymarket import (detect_topics, parse_book, parse_market,
                                       parse_resolution, passes_filters)

NOW = datetime.now(timezone.utc)


def settings(tmp_path, **kw):
    s = Settings()
    s.DATA_DIR = str(tmp_path)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def market(id="m1", yes=0.50, days=5, event="e1", tags=None, q="Will X happen?"):
    return Market("polymarket", id, q, "Resolves YES if X.", NOW + timedelta(days=days),
                  f"{id}-yes", f"{id}-no", yes, 50000, 20000, 0.01, event, "Event", tags or [],
                  "0xcond", "https://polymarket.com/event/x")


def book(bid, ask, depth=500):
    return Book(bid, ask, depth, [(ask, depth), (ask + 0.01, depth)])


# ---------------------------------------------------------------- parsing
def test_parse_market_and_filters(tmp_path):
    raw = {"id": "123", "question": "Will the Fed cut rates?", "outcomes": '["Yes","No"]',
           "outcomePrices": '["0.4","0.6"]', "clobTokenIds": '["111","222"]',
           "endDate": (NOW + timedelta(days=3)).isoformat(), "liquidityNum": 20000,
           "volume24hr": 9000, "bestBid": 0.39, "bestAsk": 0.41, "events": [{"id": 9, "title": "Fed"}]}
    mk = parse_market(raw)
    assert mk and mk.yes_token == "111" and mk.no_token == "222" and mk.yes_price == 0.4
    assert passes_filters(mk, settings(tmp_path))[0]
    raw["outcomes"] = '["Up","Down"]'
    assert parse_market(raw) is None


def test_topic_exclusion(tmp_path):
    assert "crypto" in detect_topics("Bitcoin above $100k on Friday?")
    assert "sports" in detect_topics("Lakers vs. Celtics")
    mk = market(tags=["crypto"])
    ok, why = passes_filters(mk, settings(tmp_path))
    assert not ok and "crypto" in why


def test_parse_book_orders_correctly():
    # API sends bids ascending and asks DESCENDING; we must not trust order
    b = parse_book({"bids": [{"price": "0.40", "size": "10"}, {"price": "0.45", "size": "5"}],
                    "asks": [{"price": "0.60", "size": "3"}, {"price": "0.48", "size": "7"}]})
    assert b.best_bid == 0.45 and b.best_ask == 0.48 and b.ask_size == 7


def test_resolution():
    assert parse_resolution({"closed": False}).resolved is False
    r = parse_resolution({"closed": True, "outcomePrices": '["1","0"]', "umaResolutionStatus": "resolved"})
    assert r.resolved and r.yes_payout == 1.0
    assert parse_resolution({"closed": True, "outcomePrices": '["0","1"]'}).yes_payout == 0.0
    assert parse_resolution({"closed": True, "outcomePrices": '["1","0"]',
                             "umaResolutionStatus": "proposed"}).resolved is False


# ------------------------------------------------------------- AI output
def test_extract_json_takes_last_object():
    txt = 'Thinking {"a":1} ... final: {"probability": 0.7, "confidence": "medium", "summary": "s"}'
    fc = validate(extract_json(txt))
    assert fc.probability == 0.7 and fc.confidence == "medium"
    assert extract_json("no json here") is None
    assert validate({"probability": 1.5}) is None


# ------------------------------------------------------------------ math
def test_fee_and_kelly():
    assert taker_fee(100, 0.5, 0.05) == pytest.approx(1.25)
    assert kelly_fraction(0.6, 0.5) == pytest.approx(0.2)
    assert kelly_fraction(0.4, 0.5) == 0


def test_walk_book_respects_price_cap():
    shares, spent = walk_book([(0.50, 2), (0.52, 100)], 5.0, 0.50)
    assert spent == pytest.approx(1.0) and shares == pytest.approx(2)


# --------------------------------------------------------------- decisions
def test_no_trade_when_ai_agrees(tmp_path):
    d = decide(market(), Forecast(0.55, "high", ""), book(0.49, 0.51), book(0.49, 0.51),
               20, 20, 0.05, settings(tmp_path))
    assert not d.trade and "agrees" in d.reason


def test_no_trade_on_low_confidence(tmp_path):
    d = decide(market(), Forecast(0.9, "low", ""), book(0.49, 0.51), book(0.49, 0.51),
               20, 20, 0.05, settings(tmp_path))
    assert not d.trade


def test_buys_yes_when_ai_much_higher(tmp_path):
    s = settings(tmp_path)
    d = decide(market(), Forecast(0.85, "high", ""), book(0.49, 0.51), book(0.49, 0.51), 20, 20, 0.05, s)
    assert d.trade and d.side == "YES"
    assert s.MIN_STAKE_USD <= d.stake_usd <= s.MAX_STAKE_USD
    assert d.edge >= s.MIN_EDGE


def test_buys_no_when_ai_much_lower(tmp_path):
    d = decide(market(yes=0.6), Forecast(0.2, "high", ""), book(0.59, 0.61), book(0.39, 0.41),
               20, 20, 0.05, settings(tmp_path))
    assert d.trade and d.side == "NO" and d.token_id == "m1-no"


def test_thin_book_blocks(tmp_path):
    d = decide(market(), Forecast(0.85, "high", ""), book(0.49, 0.51, depth=0.5),
               book(0.49, 0.51), 20, 20, 0.05, settings(tmp_path))
    assert not d.trade


# -------------------------------------------------------------- end to end
class FakeVenue:
    def __init__(self, markets, books, results=None):
        self.markets, self.books, self.results = markets, books, results or {}

    def list_candidate_markets(self, s):
        return self.markets

    def get_book(self, token):
        return self.books[token]

    def get_resolution(self, mid):
        return self.results.get(mid, Resolution(False))


class FakeResearcher:
    def __init__(self, probs):
        self.probs, self.calls = probs, 0

    def forecast(self, mk):
        self.calls += 1
        return Forecast(self.probs[mk.id], "high", "test"), 0.10


def test_full_cycle_trade_then_settle(tmp_path):
    s = settings(tmp_path)
    mk = market(days=2)
    venue = FakeVenue([mk], {"m1-yes": book(0.49, 0.51), "m1-no": book(0.49, 0.51)})
    eng = Engine(s, venue, FakeResearcher({"m1": 0.85}), PaperBroker())
    eng.run_once()
    assert len(eng.state.positions) == 1
    pos = next(iter(eng.state.positions.values()))
    cash_after_buy = eng.state.cash
    assert cash_after_buy == pytest.approx(20 - pos["cost"])

    # second run: same market isn't researched again (saves money)
    eng.run_once()
    assert eng.researcher.calls == 1

    # market ends and resolves YES -> paid $1/share
    pos["end_date"] = (NOW - timedelta(hours=1)).isoformat()
    eng.state.data["forecasts"][0]["end_date"] = pos["end_date"]
    venue.results["m1"] = Resolution(True, 1.0)
    eng.run_once(trade=False)
    assert not eng.state.positions
    c = eng.state.data["closed"][0]
    assert c["pnl"] == pytest.approx(pos["shares"] - pos["cost"], abs=1e-3) and c["pnl"] > 0
    assert eng.state.data["forecasts"][0]["yes_payout"] == 1.0
    assert (tmp_path / "paper" / "REPORT.md").exists()


def test_risk_limits(tmp_path):
    s = settings(tmp_path, MAX_OPEN_POSITIONS=2, FORECASTS_PER_RUN=10)
    mks = [market(id=f"m{i}", event=f"e{i}") for i in range(5)]
    books = {}
    for m in mks:
        books[m.yes_token] = book(0.49, 0.51)
        books[m.no_token] = book(0.49, 0.51)
    eng = Engine(s, FakeVenue(mks, books), FakeResearcher({m.id: 0.85 for m in mks}), PaperBroker())
    eng.run_once()
    assert len(eng.state.positions) == 2  # stopped at the cap


def test_one_bet_per_event(tmp_path):
    s = settings(tmp_path, FORECASTS_PER_RUN=10)
    mks = [market(id="a", event="same"), market(id="b", event="same")]
    books = {t: book(0.49, 0.51) for m in mks for t in (m.yes_token, m.no_token)}
    eng = Engine(s, FakeVenue(mks, books), FakeResearcher({"a": 0.85, "b": 0.85}), PaperBroker())
    eng.run_once()
    assert len(eng.state.positions) == 1


def test_ai_budget_stops_research(tmp_path):
    s = settings(tmp_path, DAILY_AI_BUDGET_USD=0.15, FORECASTS_PER_RUN=10)
    mks = [market(id=f"m{i}", event=f"e{i}") for i in range(5)]
    books = {t: book(0.49, 0.51) for m in mks for t in (m.yes_token, m.no_token)}
    r = FakeResearcher({m.id: 0.5 for m in mks})
    Engine(s, FakeVenue(mks, books), r, PaperBroker()).run_once()
    assert r.calls == 1


def test_drawdown_halts(tmp_path):
    s = settings(tmp_path)
    eng = Engine(s, FakeVenue([], {}), FakeResearcher({}), PaperBroker())
    eng.state.cash = 11.0  # lost $9 of $20
    eng.run_once()
    assert eng.state.data["halted"]


def test_kill_switch(tmp_path, monkeypatch):
    s = settings(tmp_path)
    (tmp_path / "STOP").write_text("")
    mk = market()
    r = FakeResearcher({"m1": 0.85})
    Engine(s, FakeVenue([mk], {}), r, PaperBroker()).run_once()
    assert r.calls == 0


def test_live_refuses_on_ci(tmp_path, monkeypatch):
    from polybot.brokers import LiveBroker, LiveBrokerRefused
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(LiveBrokerRefused):
        LiveBroker(settings(tmp_path, LIVE_TRADING_CONFIRMED=True, POLYMARKET_PRIVATE_KEY="x"))


def test_min_order_size_bumps_within_cap(tmp_path):
    s = settings(tmp_path)
    b = Book(0.29, 0.30, 500, [(0.30, 500)], min_order_size=5)  # 5 sh * 0.30 = $1.50 <= $2
    d = decide(market(yes=0.3), Forecast(0.65, "high", ""), b, book(0.69, 0.71), 20, 20, 0.05, s)
    assert d.trade and d.shares >= 5


def test_min_order_size_too_expensive_skips(tmp_path):
    s = settings(tmp_path)
    no = Book(0.67, 0.68, 500, [(0.68, 500)], min_order_size=5)  # 5 * 0.68 = $3.40 > $2
    d = decide(market(yes=0.32), Forecast(0.05, "high", ""), book(0.31, 0.33), no, 20, 20, 0.05, s)
    assert not d.trade and "minimum" in d.reason


def test_search_blocks_betting_sites():
    from types import SimpleNamespace as N
    from polybot.research import Researcher
    seen = {}

    class C:
        class messages:
            @staticmethod
            def create(**kw):
                seen.update(kw)
                return N(usage=N(input_tokens=1, output_tokens=1),
                         content=[N(type="text", text='{"probability":0.4,"confidence":"low"}')])
    Researcher(Settings(), C()).forecast(market())
    assert "polymarket.com" in seen["tools"][0]["blocked_domains"]
    assert "Do NOT use prediction-market prices" in seen["messages"][0]["content"]

"""Polymarket public data (no account needed): markets, order books, results."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone

import requests

from .base import Book, Market, Resolution, Venue

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

TOPIC_KEYWORDS = {
    "crypto": [
        "bitcoin", "btc", "ethereum", "eth ", "solana", "crypto", "xrp", "dogecoin",
        "memecoin", "up or down", "token", "stablecoin", "binance", "coinbase",
    ],
    "sports": [
        " vs. ", " vs ", "nba", "nfl", "nhl", "mlb", "premier league", "champions league",
        "la liga", "serie a", "bundesliga", "ufc", "grand prix", "f1 ", "tennis",
        "atp", "wta", "world cup", "super bowl", "o/u", "spread:", "match", "game ",
        "playoffs", "championship", "fc ", "cricket", "golf", "boxing",
    ],
}

# Taker fee rates (docs.polymarket.com/trading/fees). We assume the HIGHER rate
# when unsure so paper results never look better than reality.
FEE_RATES = {"crypto": 0.07, "sports": 0.05, "default": 0.05}


def detect_topics(text: str) -> list[str]:
    t = f" {text.lower()} "
    return [topic for topic, words in TOPIC_KEYWORDS.items() if any(w in t for w in words)]


def fee_rate_for(market: Market) -> float:
    rates = [FEE_RATES[t] for t in market.tags if t in FEE_RATES]
    return max(rates) if rates else FEE_RATES["default"]


def _json_field(value, default):
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return default
    return value


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_market(m: dict) -> Market | None:
    """Turn a raw Gamma API market into a Market, or None if it isn't a clean Yes/No market."""
    outcomes = [str(o).lower() for o in _json_field(m.get("outcomes"), [])]
    tokens = _json_field(m.get("clobTokenIds"), [])
    prices = _json_field(m.get("outcomePrices"), [])
    if outcomes != ["yes", "no"] or len(tokens) != 2 or len(prices) != 2:
        return None
    if not m.get("enableOrderBook", True) or m.get("acceptingOrders") is False:
        return None
    end = _parse_date(m.get("endDate") or m.get("endDateIso"))
    if end is None:
        return None
    try:
        yes_price = float(prices[0])
    except (TypeError, ValueError):
        return None

    events = m.get("events") or [{}]
    ev = events[0] if events else {}
    text = " ".join([m.get("question", ""), ev.get("title", ""), m.get("category") or ""])
    best_bid, best_ask = m.get("bestBid"), m.get("bestAsk")
    spread = m.get("spread")
    if spread is None and best_bid is not None and best_ask is not None:
        spread = float(best_ask) - float(best_bid)

    return Market(
        venue="polymarket",
        id=str(m.get("id")),
        question=m.get("question", ""),
        description=(m.get("description") or "")[:2500],
        end_date=end,
        yes_token=str(tokens[0]),
        no_token=str(tokens[1]),
        yes_price=yes_price,
        liquidity=float(m.get("liquidityNum") or m.get("liquidity") or 0),
        volume_24h=float(m.get("volume24hr") or 0),
        spread=float(spread) if spread is not None else 1.0,
        event_id=str(ev.get("id", "")),
        event_title=ev.get("title", ""),
        tags=detect_topics(text),
        condition_id=m.get("conditionId", ""),
        url=f"https://polymarket.com/event/{ev.get('slug') or m.get('slug', '')}",
    )


def passes_filters(mk: Market, s, now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.now(timezone.utc)
    days = (mk.end_date - now).total_seconds() / 86400
    if days < s.MIN_DAYS_TO_END:
        return False, "ends too soon"
    if days > s.MAX_DAYS_TO_END:
        return False, "ends too late"
    if not (s.MIN_PRICE <= mk.yes_price <= s.MAX_PRICE):
        return False, "price outside range"
    if mk.liquidity < s.MIN_LIQUIDITY_USD:
        return False, "low liquidity"
    if mk.volume_24h < s.MIN_VOLUME_24H_USD:
        return False, "low volume"
    if mk.spread > s.MAX_SPREAD:
        return False, "spread too wide"
    blocked = set(mk.tags) & set(s.EXCLUDED_TOPICS)
    if blocked:
        return False, f"excluded topic: {','.join(sorted(blocked))}"
    return True, "ok"


class Polymarket(Venue):
    name = "polymarket"

    def __init__(self, session: requests.Session | None = None):
        self.http = session or requests.Session()
        self.http.headers.update({"User-Agent": "polybot/2.0"})

    def _get(self, url, params=None, tries=3):
        for i in range(tries):
            try:
                r = self.http.get(url, params=params, timeout=15)
                if r.status_code == 429:
                    time.sleep(2 * (i + 1))
                    continue
                r.raise_for_status()
                return r.json()
            except requests.RequestException:
                if i == tries - 1:
                    raise
                time.sleep(1.5 * (i + 1))
        raise RuntimeError(f"GET {url} failed")

    def list_candidate_markets(self, s) -> list[Market]:
        now = datetime.now(timezone.utc)
        raw: list[dict] = []
        for offset in range(0, 500, 100):
            page = self._get(f"{GAMMA}/markets", {
                "closed": "false", "active": "true", "limit": 100, "offset": offset,
                "order": "volume24hr", "ascending": "false",
                "end_date_min": (now + timedelta(days=s.MIN_DAYS_TO_END)).isoformat(),
                "end_date_max": (now + timedelta(days=s.MAX_DAYS_TO_END)).isoformat(),
            })
            if not page:
                break
            raw.extend(page)
            if len(page) < 100:
                break
        out, seen = [], set()
        for m in raw:
            mk = parse_market(m)
            if mk and mk.id not in seen and passes_filters(mk, s, now)[0]:
                seen.add(mk.id)
                out.append(mk)
        return out

    def get_book(self, token_id: str) -> Book:
        data = self._get(f"{CLOB}/book", {"token_id": token_id})
        return parse_book(data)

    def get_resolution(self, market_id: str) -> Resolution:
        m = self._get(f"{GAMMA}/markets/{market_id}")
        return parse_resolution(m)


def parse_book(data: dict) -> Book:
    bids = [(float(b["price"]), float(b["size"])) for b in data.get("bids", [])]
    asks = sorted(((float(a["price"]), float(a["size"])) for a in data.get("asks", [])))
    best_bid = max((p for p, _ in bids), default=None)
    best_ask = asks[0][0] if asks else None
    ask_size = asks[0][1] if asks else 0.0
    return Book(best_bid, best_ask, ask_size, asks, float(data.get("min_order_size") or 0))


def parse_resolution(m: dict) -> Resolution:
    if not m.get("closed"):
        return Resolution(False)
    status = (m.get("umaResolutionStatus") or "").lower()
    if status and status not in {"resolved", "settled"}:
        return Resolution(False)  # closed for trading but not finalized yet
    prices = _json_field(m.get("outcomePrices"), [])
    try:
        yes = float(prices[0])
    except (TypeError, ValueError, IndexError):
        return Resolution(False)
    if yes >= 0.99:
        return Resolution(True, 1.0)
    if yes <= 0.01:
        return Resolution(True, 0.0)
    return Resolution(True, round(yes, 4))  # 50/50 or other split


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]

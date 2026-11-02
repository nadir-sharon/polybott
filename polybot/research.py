"""The AI forecaster: Claude researches a market on the web and estimates a probability.

Claude is NOT shown the market price. It forms its own view, and the strategy
then decides how much (if at all) to trust that view over the market's.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .venues.base import Market

PROMPT = """You are a careful, calibrated forecaster. Estimate the probability that this \
prediction market resolves YES.

Today (UTC): {today}
Market closes: {end} ({days:.1f} days from now)

QUESTION: {question}

RESOLUTION RULES (read carefully, the exact wording decides the outcome):
{rules}

IMPORTANT: Do NOT use prediction-market prices, betting odds, or bookmaker lines
(Polymarket, Kalshi, PredictIt, sportsbooks, "markets give X%"). If a search result
quotes them, ignore those numbers. We already know the market price; your value is an
INDEPENDENT estimate built from primary evidence (official results, polls, filings,
schedules, statements, expert models that are not betting markets).

How to work:
1. Search the web for the most recent, authoritative information (official sources, \
   major outlets). Prefer facts from the last few days.
2. Start from a base rate: how often do things like this happen in a window this short? \
   The status quo usually holds over days-to-weeks.
3. Adjust for specific evidence. Note anything that would already decide the outcome.
4. Check the resolution rules for traps (exact dates, thresholds, which source counts).

Confidence:
- "high" ONLY if you found recent, verifiable facts that largely determine the outcome.
- "medium" if evidence clearly leans one way but real uncertainty remains.
- "low" if information is thin, stale, or conflicting.

Finish with ONE JSON object and nothing after it:
{{"probability": <0.01-0.99>, "confidence": "low|medium|high", \
"summary": "<2-3 sentences>", "key_facts": ["..."], "sources": ["<url>", "..."]}}"""


BETTING_DOMAINS = [
    "polymarket.com", "kalshi.com", "manifold.markets", "predictit.org",
    "metaculus.com", "oddschecker.com", "polymarketanalytics.com", "betfair.com",
]


@dataclass
class Forecast:
    probability: float
    confidence: str
    summary: str
    key_facts: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    cost_usd: float = 0.0
    searches: int = 0


def extract_json(text: str) -> dict | None:
    """Find the last {...} block in the text that parses as JSON with a probability."""
    decoder = json.JSONDecoder()
    found = None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict) and "probability" in obj:
            found = obj  # keep going: we want the LAST one
    return found


def validate(obj: dict) -> Forecast | None:
    try:
        p = float(obj["probability"])
    except (KeyError, TypeError, ValueError):
        return None
    if not 0.0 < p < 1.0:
        return None
    conf = str(obj.get("confidence", "low")).lower()
    if conf not in {"low", "medium", "high"}:
        conf = "low"
    return Forecast(
        probability=min(max(p, 0.01), 0.99),
        confidence=conf,
        summary=str(obj.get("summary", ""))[:600],
        key_facts=[str(x)[:300] for x in obj.get("key_facts", [])][:6],
        sources=[str(x) for x in obj.get("sources", [])][:8],
    )


class Researcher:
    def __init__(self, settings, client=None):
        self.s = settings
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client

    def estimate_cost(self, usage) -> tuple[float, int]:
        searches = 0
        stu = getattr(usage, "server_tool_use", None)
        if stu is not None:
            searches = int(getattr(stu, "web_search_requests", 0) or 0)
        cost = (
            (getattr(usage, "input_tokens", 0) or 0) / 1e6 * self.s.PRICE_INPUT_PER_MTOK
            + (getattr(usage, "cache_read_input_tokens", 0) or 0) / 1e6 * self.s.PRICE_INPUT_PER_MTOK
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0) / 1e6 * self.s.PRICE_INPUT_PER_MTOK
            + (getattr(usage, "output_tokens", 0) or 0) / 1e6 * self.s.PRICE_OUTPUT_PER_MTOK
            + searches * self.s.PRICE_PER_SEARCH
        )
        return cost, searches

    def forecast(self, mk: Market) -> tuple[Forecast | None, float]:
        """Returns (forecast or None, dollars spent)."""
        now = datetime.now(timezone.utc)
        prompt = PROMPT.format(
            today=now.strftime("%Y-%m-%d %H:%M"),
            end=mk.end_date.strftime("%Y-%m-%d %H:%M"),
            days=(mk.end_date - now).total_seconds() / 86400,
            question=mk.question,
            rules=mk.description or "(none given)",
        )
        resp = self.client.messages.create(
            model=self.s.RESEARCH_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": self.s.MAX_SEARCHES_PER_FORECAST,
                # Keep the AI independent: no peeking at betting odds.
                "blocked_domains": BETTING_DOMAINS,
            }],
        )
        cost, searches = self.estimate_cost(resp.usage)
        text = "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        obj = extract_json(text)
        fc = validate(obj) if obj else None
        if fc:
            fc.cost_usd, fc.searches = cost, searches
        return fc, cost

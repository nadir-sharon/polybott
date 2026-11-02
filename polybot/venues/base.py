"""Venue interface.

A venue is anywhere the bot can read markets and (optionally) trade. Polymarket
is the only one wired up today; another venue (e.g. Manifold for play-money
testing) only needs to implement this class. Strategy, risk, and reporting
never talk to a venue's API directly, so the same rules apply everywhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Market:
    venue: str
    id: str
    question: str
    description: str
    end_date: datetime
    yes_token: str
    no_token: str
    yes_price: float          # mid / last displayed price for YES
    liquidity: float
    volume_24h: float
    spread: float
    event_id: str = ""
    event_title: str = ""
    tags: list = field(default_factory=list)
    condition_id: str = ""
    url: str = ""


@dataclass
class Book:
    """Top of the order book for ONE outcome token."""
    best_bid: Optional[float]
    best_ask: Optional[float]
    ask_size: float             # shares available at best_ask
    asks: list                  # [(price, size)] cheapest first
    min_order_size: float = 0.0


@dataclass
class Resolution:
    resolved: bool
    yes_payout: Optional[float] = None   # $ paid per YES share (1.0, 0.0, or 0.5 for a split)


class Venue:
    name = "base"

    def list_candidate_markets(self, settings) -> list[Market]:
        raise NotImplementedError

    def get_book(self, token_id: str) -> Book:
        raise NotImplementedError

    def get_resolution(self, market_id: str) -> Resolution:
        raise NotImplementedError

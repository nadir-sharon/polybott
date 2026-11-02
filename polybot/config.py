"""All tunable settings in one place.

Every value can be overridden with an environment variable of the same name
(for example `MAX_STAKE_USD=3`), or in your `.env` file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional
    pass


def _env(name: str, default, cast):
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    if cast is bool:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if cast is list:
        return [x.strip().lower() for x in raw.split(",") if x.strip()]
    return cast(raw)


@dataclass
class Settings:
    # ---- mode -------------------------------------------------------------
    MODE: str = "paper"                 # "paper" or "live"
    LIVE_TRADING_CONFIRMED: bool = False  # must ALSO be true for live orders
    DATA_DIR: str = "data"

    # ---- money ------------------------------------------------------------
    STARTING_BANKROLL_USD: float = 20.0
    MIN_STAKE_USD: float = 1.0          # Polymarket market orders need >= $1
    MAX_STAKE_USD: float = 2.0          # hard cap per trade
    KELLY_FRACTION: float = 0.25        # quarter-Kelly: deliberately timid
    MAX_OPEN_POSITIONS: int = 8
    MAX_EXPOSURE_PCT: float = 0.70      # never have more than 70% of bankroll at risk
    DAILY_LOSS_LIMIT_USD: float = 4.0   # stop opening trades for the day after this
    MAX_DRAWDOWN_USD: float = 8.0       # halt completely (needs manual reset)
    MAX_SLIPPAGE: float = 0.02          # won't pay more than ask + 2c

    # ---- which markets are allowed -----------------------------------------
    MIN_DAYS_TO_END: float = 0.5
    MAX_DAYS_TO_END: float = 14.0       # results must land inside the test window
    MIN_PRICE: float = 0.10             # skip long shots / near-certainties
    MAX_PRICE: float = 0.90
    MIN_LIQUIDITY_USD: float = 5000.0
    MIN_VOLUME_24H_USD: float = 2000.0
    MAX_SPREAD: float = 0.03
    EXCLUDED_TOPICS: list = field(default_factory=lambda: ["crypto", "sports"])

    # ---- the AI forecaster --------------------------------------------------
    RESEARCH_MODEL: str = "claude-sonnet-5-5"
    MAX_SEARCHES_PER_FORECAST: int = 4
    FORECASTS_PER_RUN: int = 3
    DAILY_AI_BUDGET_USD: float = 1.00
    REFORECAST_AFTER_HOURS: float = 24.0
    # $ per million tokens / per search, used to track spend
    PRICE_INPUT_PER_MTOK: float = 2.0
    PRICE_OUTPUT_PER_MTOK: float = 10.0
    PRICE_PER_SEARCH: float = 0.01

    # ---- decision rule -----------------------------------------------------
    MIN_EDGE: float = 0.05              # after fees + spread, in probability points
    MIN_DISAGREEMENT: float = 0.10      # AI must differ from market by >= 10 pts
    # How far we move from the market price toward the AI's view, by confidence.
    SHRINK_LOW: float = 0.0             # low confidence = never trade
    SHRINK_MEDIUM: float = 0.35
    SHRINK_HIGH: float = 0.55

    # ---- live wallet (only read in live mode) ------------------------------
    POLYMARKET_PRIVATE_KEY: str = ""
    POLYMARKET_WALLET: str = ""         # optional; SDK defaults to your deposit wallet

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        for f in fields(cls):
            default = getattr(s, f.name)
            cast = type(default) if not isinstance(default, list) else list
            setattr(s, f.name, _env(f.name, default, cast))
        s.MODE = s.MODE.lower()
        return s

    @property
    def state_dir(self) -> Path:
        p = Path(self.DATA_DIR) / self.MODE
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def is_live(self) -> bool:
        return self.MODE == "live"

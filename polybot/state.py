"""Everything the bot remembers, saved as one JSON file per mode (data/paper, data/live)."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class State:
    def __init__(self, path: Path, starting_bankroll: float):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text())
        else:
            self.data = {
                "created": now_iso(),
                "starting_bankroll": starting_bankroll,
                "cash": starting_bankroll,
                "positions": {},      # open positions by id
                "closed": [],         # settled / sold positions
                "forecasts": [],      # every AI forecast, traded or not (for scoring)
                "ai_spend": {},       # date -> usd
                "realized_by_day": {},
                "halted": None,
                "log": [],
            }

    # -- persistence ---------------------------------------------------------
    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(self.data, f, indent=1, default=str)
        os.replace(tmp, self.path)  # atomic: never leaves a half-written file

    # -- shortcuts -----------------------------------------------------------
    @property
    def cash(self) -> float:
        return self.data["cash"]

    @cash.setter
    def cash(self, v: float) -> None:
        self.data["cash"] = round(v, 6)

    @property
    def positions(self) -> dict:
        return self.data["positions"]

    def log(self, msg: str) -> None:
        line = f"{now_iso()}  {msg}"
        print(line, flush=True)
        self.data["log"].append(line)
        self.data["log"] = self.data["log"][-800:]

    def add_ai_spend(self, usd: float) -> None:
        d = today()
        self.data["ai_spend"][d] = round(self.data["ai_spend"].get(d, 0) + usd, 6)

    def ai_spend_today(self) -> float:
        return self.data["ai_spend"].get(today(), 0.0)

    def add_realized(self, pnl: float) -> None:
        d = today()
        self.data["realized_by_day"][d] = round(self.data["realized_by_day"].get(d, 0) + pnl, 6)

    def realized_today(self) -> float:
        return self.data["realized_by_day"].get(today(), 0.0)

    def total_realized(self) -> float:
        return sum(p["pnl"] for p in self.data["closed"])

    def exposure(self) -> float:
        return sum(p["cost"] for p in self.positions.values())

    def last_forecast(self, market_id: str) -> dict | None:
        for f in reversed(self.data["forecasts"]):
            if f["market_id"] == market_id:
                return f
        return None

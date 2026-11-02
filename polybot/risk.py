"""Hard safety rules. These run before EVERY order and cannot be overridden by the AI."""
from __future__ import annotations

from pathlib import Path

from .state import State


def equity(state: State) -> float:
    """Cash plus open positions valued at cost (conservative; no paper gains counted)."""
    return state.cash + state.exposure()


def check_halt(state: State, s) -> str | None:
    """Reasons the bot must not open ANY new trade right now."""
    if Path("STOP").exists() or Path(s.DATA_DIR, "STOP").exists():
        return "STOP file present (manual kill switch)"
    if state.data.get("halted"):
        return f"halted: {state.data['halted']}"
    drawdown = state.data["starting_bankroll"] - (state.cash + state.exposure())
    if drawdown >= s.MAX_DRAWDOWN_USD:
        state.data["halted"] = (f"drawdown ${drawdown:.2f} hit the ${s.MAX_DRAWDOWN_USD:.2f} limit. "
                                "Review, then run `python -m polybot reset-halt` to resume.")
        return state.data["halted"]
    if -state.realized_today() >= s.DAILY_LOSS_LIMIT_USD:
        return f"daily loss limit ${s.DAILY_LOSS_LIMIT_USD:.2f} reached; resumes tomorrow (UTC)"
    if len(state.positions) >= s.MAX_OPEN_POSITIONS:
        return f"max {s.MAX_OPEN_POSITIONS} open positions"
    return None


def check_trade(state: State, s, market_id: str, event_id: str, stake: float,
                fee: float = 0.0) -> str | None:
    """Reasons THIS particular trade is not allowed."""
    for p in state.positions.values():
        if p["market_id"] == market_id:
            return "already holding this market"
        if event_id and p.get("event_id") == event_id:
            return "already holding a market from the same event (correlated)"
    if stake > s.MAX_STAKE_USD + 1e-9:
        return "stake above MAX_STAKE_USD"
    if stake + fee > state.cash + 1e-9:
        return "not enough cash"
    limit = s.MAX_EXPOSURE_PCT * state.data["starting_bankroll"]
    if state.exposure() + stake > limit + 1e-9:
        return f"would exceed max exposure ${limit:.2f}"
    return None

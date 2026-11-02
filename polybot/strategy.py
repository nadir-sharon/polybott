"""Turn an AI forecast + live order book into a trade decision (or a reasoned 'no')."""
from __future__ import annotations

from dataclasses import dataclass

from .research import Forecast
from .venues.base import Book, Market


@dataclass
class Decision:
    trade: bool
    reason: str
    side: str = ""            # "YES" or "NO"
    token_id: str = ""
    stake_usd: float = 0.0
    avg_price: float = 0.0    # expected average fill price per share
    shares: float = 0.0
    fee_usd: float = 0.0
    fair_prob: float = 0.0    # our blended probability for the side we buy
    edge: float = 0.0         # fair_prob - effective cost per share
    market_mid: float = 0.0   # YES mid when decided


def taker_fee(shares: float, price: float, rate: float) -> float:
    """Polymarket taker fee in USDC: C x rate x p x (1-p)."""
    return shares * rate * price * (1 - price)


def walk_book(asks: list, budget_usd: float, max_price: float) -> tuple[float, float]:
    """Simulate buying up to budget_usd from cheapest asks, never above max_price.
    Returns (shares_bought, usd_spent)."""
    shares = spent = 0.0
    for price, size in asks:
        if price > max_price or spent >= budget_usd - 1e-9:
            break
        take_usd = min(price * size, budget_usd - spent)
        shares += take_usd / price
        spent += take_usd
    return shares, spent


def mid_price(book: Book, fallback: float) -> float:
    if book.best_bid is not None and book.best_ask is not None:
        return (book.best_bid + book.best_ask) / 2
    return fallback


def shrink_weight(confidence: str, s) -> float:
    return {"low": s.SHRINK_LOW, "medium": s.SHRINK_MEDIUM, "high": s.SHRINK_HIGH}.get(confidence, 0.0)


def kelly_fraction(prob: float, cost: float) -> float:
    """Full-Kelly fraction of bankroll for a $1-payout bet bought at `cost`."""
    if cost >= 1 or prob <= cost:
        return 0.0
    return (prob - cost) / (1 - cost)


def decide(mk: Market, fc: Forecast, yes_book: Book, no_book: Book,
           equity: float, cash: float, fee_rate: float, s) -> Decision:
    mid = mid_price(yes_book, mk.yes_price)
    w = shrink_weight(fc.confidence, s)
    if w <= 0:
        return Decision(False, f"AI confidence {fc.confidence}: not trading on it", market_mid=mid)
    if abs(fc.probability - mid) < s.MIN_DISAGREEMENT:
        return Decision(False, f"AI {fc.probability:.2f} vs market {mid:.2f}: agrees with market",
                        market_mid=mid)

    fair_yes = mid + w * (fc.probability - mid)
    if fc.probability > mid:
        side, book, token, fair = "YES", yes_book, mk.yes_token, fair_yes
    else:
        side, book, token, fair = "NO", no_book, mk.no_token, 1 - fair_yes

    if book.best_ask is None:
        return Decision(False, f"no sellers for {side}", market_mid=mid)
    ask = book.best_ask
    if not (s.MIN_PRICE <= ask <= s.MAX_PRICE):
        return Decision(False, f"{side} ask {ask:.2f} outside allowed price range", market_mid=mid)

    eff_cost = ask + rate_per_share(ask, fee_rate)
    edge = fair - eff_cost
    if edge < s.MIN_EDGE:
        return Decision(False, f"{side} edge {edge:+.3f} after fees < {s.MIN_EDGE}",
                        side=side, fair_prob=fair, edge=edge, market_mid=mid)

    # --- sizing: quarter-Kelly, clamped to hard limits -----------------------
    full_k = kelly_fraction(fair, eff_cost)
    stake = s.KELLY_FRACTION * full_k * equity
    if stake < s.MIN_STAKE_USD:
        # $20 bankrolls are lumpy: allow the $1 minimum only if half-Kelly supports it
        if 0.5 * full_k * equity >= s.MIN_STAKE_USD:
            stake = s.MIN_STAKE_USD
        else:
            return Decision(False, f"edge too small for minimum ${s.MIN_STAKE_USD:.0f} bet",
                            side=side, fair_prob=fair, edge=edge, market_mid=mid)
    stake = min(stake, s.MAX_STAKE_USD, cash)
    if stake < s.MIN_STAKE_USD:
        return Decision(False, "not enough cash", market_mid=mid)

    # --- can the book actually fill it at a sane price? ----------------------
    max_px = min(ask + s.MAX_SLIPPAGE, fair - s.MIN_EDGE / 2)
    shares, spent = walk_book(book.asks, stake, max_px)
    if spent < stake * 0.95:
        return Decision(False, f"order book too thin (fills ${spent:.2f} of ${stake:.2f})",
                        market_mid=mid)
    avg = spent / shares
    if book.min_order_size and shares < book.min_order_size:
        return Decision(False, "below venue minimum order size", market_mid=mid)
    fee = taker_fee(shares, avg, fee_rate)
    real_edge = fair - (avg + fee / shares)
    if real_edge < s.MIN_EDGE:
        return Decision(False, f"edge after slippage {real_edge:+.3f} too small", market_mid=mid)

    return Decision(True, "edge found", side=side, token_id=token, stake_usd=round(spent, 4),
                    avg_price=avg, shares=shares, fee_usd=fee, fair_prob=fair,
                    edge=real_edge, market_mid=mid)


def rate_per_share(price: float, fee_rate: float) -> float:
    return fee_rate * price * (1 - price)

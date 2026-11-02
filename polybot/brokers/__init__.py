"""Brokers execute an approved Decision. Paper simulates; Live sends real orders."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

import requests


@dataclass
class Fill:
    shares: float
    cost_usd: float       # total cash out, fees included
    avg_price: float
    order_id: str = ""


class PaperBroker:
    """Simulates a taker buy against the real order book, fees included."""

    live = False

    def buy(self, decision, max_price: float) -> Fill | None:
        cost = decision.stake_usd + decision.fee_usd
        return Fill(decision.shares, cost, decision.avg_price, order_id="paper")

    def redeem(self, position: dict) -> None:
        pass

    def cash_balance(self) -> float | None:
        return None


class LiveBrokerRefused(RuntimeError):
    pass


def check_geoblock() -> dict:
    r = requests.get("https://polymarket.com/api/geoblock", timeout=10)
    r.raise_for_status()
    return r.json()


class LiveBroker:
    """Real orders through Polymarket's official SDK (`pip install polymarket-client`).

    Refuses to start unless every safety condition holds.
    """

    live = True

    def __init__(self, s):
        if os.getenv("GITHUB_ACTIONS") or os.getenv("CI"):
            raise LiveBrokerRefused(
                "Live trading is disabled on GitHub Actions/CI: those servers are in the US, "
                "where Polymarket does not allow new orders. Run live mode on your own computer.")
        if not s.LIVE_TRADING_CONFIRMED:
            raise LiveBrokerRefused("Set LIVE_TRADING_CONFIRMED=true in .env to allow real orders.")
        if not s.POLYMARKET_PRIVATE_KEY:
            raise LiveBrokerRefused("POLYMARKET_PRIVATE_KEY is missing from .env.")
        geo = check_geoblock()
        if geo.get("blocked"):
            raise LiveBrokerRefused(
                f"Polymarket reports your location ({geo.get('country', '?')}) as blocked. "
                "Do not use a VPN to get around this; it breaks Polymarket's terms.")

        from polymarket import SecureClient  # imported here so paper mode doesn't need it

        self.client = SecureClient.create(
            private_key=s.POLYMARKET_PRIVATE_KEY,
            wallet=s.POLYMARKET_WALLET or None,
        )

    def cash_balance(self) -> float:
        bal = self.client.get_balance_allowance(asset_type="COLLATERAL")
        return bal.balance / 1e6  # USDC-style collateral has 6 decimals

    def buy(self, decision, max_price: float) -> Fill | None:
        cap = math.floor(max_price * 100) / 100  # whole-cent cap, never above our limit
        resp = self.client.place_market_order(
            token_id=decision.token_id,
            side="BUY",
            amount=f"{decision.stake_usd:.2f}",
            max_price=f"{cap:.2f}",
            order_type="FAK",  # fill what's available now, cancel the rest
        )
        if not getattr(resp, "ok", False):
            raise RuntimeError(f"order rejected: {getattr(resp, 'code', '?')} {getattr(resp, 'message', '')}")
        spent = float(resp.making_amount)   # USDC we gave
        shares = float(resp.taking_amount)  # shares we got
        if shares <= 0:
            return None
        return Fill(shares, spent, spent / shares, order_id=resp.order_id)

    def redeem(self, position: dict) -> None:
        if position.get("condition_id"):
            self.client.redeem_positions(condition_id=position["condition_id"]).wait()

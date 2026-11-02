"""Command line.

  python -m polybot run            one cycle (what GitHub Actions does)
  python -m polybot loop           run forever, every 15 min (on your laptop)
  python -m polybot report         print the scoreboard
  python -m polybot check-live     test your live setup WITHOUT placing an order
  python -m polybot reset-halt     resume after the drawdown limit stopped the bot
"""
from __future__ import annotations

import argparse
import sys
import time

from .config import Settings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="polybot")
    ap.add_argument("command", choices=["run", "loop", "report", "check-live", "reset-halt"])
    ap.add_argument("--interval", type=int, default=900, help="seconds between cycles (loop)")
    ap.add_argument("--settle-only", action="store_true", help="only settle; open no new bets")
    a = ap.parse_args(argv)
    s = Settings.load()

    if a.command == "report":
        from .report import render
        from .state import State

        print(render(State(s.state_dir / "state.json", s.STARTING_BANKROLL_USD), s))
        return 0

    if a.command == "reset-halt":
        from .state import State

        st = State(s.state_dir / "state.json", s.STARTING_BANKROLL_USD)
        st.data["halted"] = None
        st.log("[manual] halt cleared")
        st.save()
        return 0

    if a.command == "check-live":
        from .brokers import LiveBroker, LiveBrokerRefused

        s.MODE = "live"
        try:
            b = LiveBroker(s)
            print(f"OK: connected. Wallet cash: ${b.cash_balance():.2f}. No order was placed.")
            return 0
        except LiveBrokerRefused as e:
            print(f"NOT READY: {e}")
            return 1

    from .engine import Engine

    eng = Engine(s)
    if a.command == "run":
        eng.run_once(trade=not a.settle_only)
        return 0

    while True:  # loop
        try:
            eng.run_once(trade=not a.settle_only)
        except KeyboardInterrupt:
            raise
        except Exception as e:  # keep going; one bad cycle shouldn't kill the bot
            eng.state.log(f"[loop] cycle crashed: {e!r}")
            eng.state.save()
        print(f"\nsleeping {a.interval}s (Ctrl+C to stop)\n", flush=True)
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())

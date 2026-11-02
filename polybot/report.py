"""Writes data/<mode>/REPORT.md: a plain-English scoreboard you can read on GitHub."""
from __future__ import annotations

from .state import State, now_iso


def brier(pairs) -> float | None:
    pairs = list(pairs)
    if not pairs:
        return None
    return sum((p - o) ** 2 for p, o in pairs) / len(pairs)


def summary(st: State) -> dict:
    closed = st.data["closed"]
    wins = [c for c in closed if c["pnl"] > 0]
    realized = st.total_realized()
    ai_spend = sum(st.data["ai_spend"].values())
    scored = [f for f in st.data["forecasts"] if f.get("yes_payout") in (0.0, 1.0)]
    return {
        "starting": st.data["starting_bankroll"],
        "cash": st.cash,
        "open_cost": st.exposure(),
        "open_count": len(st.positions),
        "realized": realized,
        "ai_spend": ai_spend,
        "net": realized - ai_spend,
        "closed": len(closed),
        "wins": len(wins),
        "win_rate": len(wins) / len(closed) if closed else None,
        "scored": len(scored),
        "brier_ai": brier((f["ai_prob"], f["yes_payout"]) for f in scored),
        "brier_market": brier((f["market_mid"], f["yes_payout"]) for f in scored),
    }


def _fmt(x, pct=False, money=False, digits=3):
    if x is None:
        return "–"
    if pct:
        return f"{x:.0%}"
    if money:
        return f"${x:,.2f}" if x >= 0 else f"-${-x:,.2f}"
    return f"{x:.{digits}f}"


def render(st: State, s) -> str:
    m = summary(st)
    lines = [
        f"# Polybot report: {s.MODE.upper()} mode",
        "",
        f"_Updated {now_iso()} UTC_" + (f"  \n**HALTED:** {st.data['halted']}" if st.data.get("halted") else ""),
        "",
        "## Scoreboard",
        "",
        "| | |",
        "|---|---|",
        f"| Starting bankroll | {_fmt(m['starting'], money=True)} |",
        f"| Cash now | {_fmt(m['cash'], money=True)} |",
        f"| In open bets (at cost) | {_fmt(m['open_cost'], money=True)} ({m['open_count']} bets) |",
        f"| Realized profit/loss | **{_fmt(m['realized'], money=True)}** |",
        f"| AI research spent | {_fmt(m['ai_spend'], money=True)} |",
        f"| Profit after AI costs | **{_fmt(m['net'], money=True)}** |",
        f"| Settled bets | {m['closed']} ({m['wins']} won, win rate {_fmt(m['win_rate'], pct=True)}) |",
        "",
        "## Is the AI better than the market?",
        "",
        "Brier score on every resolved market the AI studied (lower is better; 0.25 = coin flip).",
        "This is the number that matters: if the AI isn't beating the market here, wins are luck.",
        "",
        f"- Resolved forecasts: **{m['scored']}**",
        f"- AI Brier: **{_fmt(m['brier_ai'])}**",
        f"- Market Brier: **{_fmt(m['brier_market'])}**",
    ]
    if m["scored"] < 20:
        lines.append(f"- _Too few results to judge yet (need roughly 20+)._")

    lines += ["", "## Open bets", ""]
    if st.positions:
        lines += ["| Opened | Side | Cost | Price | AI / market | Ends | Market |",
                  "|---|---|---|---|---|---|---|"]
        for p in sorted(st.positions.values(), key=lambda p: p["opened_at"], reverse=True):
            lines.append(
                f"| {p['opened_at'][:16]} | {p['side']} | ${p['cost']:.2f} | {p['avg_price']:.2f} | "
                f"{p['ai_prob']:.2f} / {p['market_mid']:.2f} | {p['end_date'][:10]} | "
                f"[{p['question'][:70]}]({p['url']}) |")
    else:
        lines.append("_None._")

    lines += ["", "## Settled bets (latest 20)", ""]
    closed = st.data["closed"][-20:][::-1]
    if closed:
        lines += ["| Closed | Side | Cost | P/L | Market |", "|---|---|---|---|---|"]
        for c in closed:
            lines.append(f"| {c['closed_at'][:16]} | {c['side']} | ${c['cost']:.2f} | "
                         f"{_fmt(c['pnl'], money=True)} | {c['question'][:70]} |")
    else:
        lines.append("_None yet. Bets settle when their market resolves._")

    lines += ["", "## Latest AI research (10)", ""]
    for f in st.data["forecasts"][-10:][::-1]:
        lines.append(f"- **{f['question'][:90]}**  \n  AI {f['ai_prob']:.2f} ({f['confidence']}) "
                     f"vs market {f['market_mid']:.2f} → {f['decision']}  \n  _{f['summary'][:240]}_")

    lines += ["", "## Activity log (latest 40)", "", "```"]
    lines += st.data["log"][-40:]
    lines += ["```", ""]
    return "\n".join(lines)


def write_report(st: State, s) -> None:
    (s.state_dir / "REPORT.md").write_text(render(st, s))

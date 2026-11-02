# Polybot

A small, cautious Polymarket bot. Claude researches markets on the web and makes its own
probability estimate without seeing the price. The bot bets only when that estimate
disagrees with the market by a wide margin, after fees and spread, and only within hard
money limits.

> **Be realistic.** Most prediction-market bots lose money. This one is built to *find out*
> cheaply whether its AI forecasts beat the market, and to cap the damage if they don't.
> Only use money you're fine losing.

## How a cycle works

1. **Settle.** Check bets whose markets have ended, collect winnings, and record the result.
   Also score every past AI forecast, including ones it didn't bet on.
2. **Scan.** List open Yes/No markets that end within 14 days, are priced between 10¢ and
   90¢, and have enough liquidity and volume and a tight spread. Crypto-price and sports
   markets are skipped by default: fast bots dominate them, and AI research gives no edge there.
3. **Research.** Claude searches the web for up to 3 new markets, without seeing the price.
   It returns a probability and a confidence level. Each forecast costs about $0.08, and
   total AI spend is capped at $1/day.
4. **Decide.**
   - Low confidence means no bet.
   - Otherwise the bot moves only part way from the market price toward Claude's view
     (35% at medium confidence, 55% at high).
   - It bets only if the remaining edge is at least 5 points after taker fees and the real
     order book.
5. **Size.** Quarter-Kelly, $1 minimum and $2 maximum per bet.
6. **Hard limits that the AI can't override:**
   - At most 8 open bets.
   - At most 70% of the bankroll at risk.
   - One bet per event.
   - Stop for the day after a $4 loss.
   - **Full stop after an $8 drawdown.**
   - Kill switch: create a file called `STOP` and the bot opens no new bets.

The scoreboard is written to `data/paper/REPORT.md` (or `data/live/`). It shows profit
after AI costs and, most importantly, the **Brier score: AI vs market**. If the AI's
score isn't lower than the market's after 20 or more resolved markets, any profit is luck.

## 1. Paper trading on GitHub Actions (free, runs 24/7)

1. Get an Anthropic API key from console.anthropic.com and add about $10 of credit.
2. In this repo on GitHub, go to **Settings → Secrets and variables → Actions → New repository
   secret**. Name it `ANTHROPIC_API_KEY` and paste the key.
3. Go to **Actions** and enable workflows if GitHub asks. Then open **polybot-paper** and
   click **Run workflow** to test it.
4. It then runs about every 30 minutes. Check `data/paper/REPORT.md` on GitHub. Each run's
   full log is on the Actions tab.

GitHub's servers are in the US, where Polymarket blocks new orders. The bot therefore
refuses to trade real money there; GitHub Actions is for paper trading only.

## 2. On your laptop (see it working, and trade live)

```bash
git clone https://github.com/nadir-sharon/polybott && cd polybott
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env        # then put your ANTHROPIC_API_KEY in it
python -m pytest -q         # offline tests, should all pass
```

To watch it think in paper mode, use a separate folder so it doesn't clash with the
GitHub copy:

```bash
DATA_DIR=data-local python -m polybot run      # one cycle
DATA_DIR=data-local python -m polybot loop     # every 15 min until Ctrl+C
python -m polybot report                       # scoreboard (git pull first to see GitHub's)
```

On Windows PowerShell, set the folder first with `$env:DATA_DIR="data-local"`.

## 3. Going live with real money

Polymarket can be used from Ghana. Never use a VPN to get around a location block: it
breaks Polymarket's terms and can freeze your funds.

1. Create a Polymarket account. Deposit your test amount (e.g. $20) in USDC on Polygon,
   plus a little extra for safety.
2. Export the account's private key (Polymarket settings) and put it in `.env` as
   `POLYMARKET_PRIVATE_KEY`.
   - Treat this key like cash: anyone with it can take the money.
   - Never commit `.env`, and never paste the key into chats.
   - Keep only test money in this account.
3. Test the setup without placing an order:
   ```bash
   python -m polybot check-live
   ```
   It should print your wallet balance. If it shows $0 but Polymarket shows funds, put the
   wallet address from your Polymarket deposit page in `POLYMARKET_WALLET` and try again.
4. In `.env`, set `MODE=live`, `LIVE_TRADING_CONFIRMED=true` and `STARTING_BANKROLL_USD=20`.
5. Start it:
   ```bash
   python -m polybot loop
   ```
   It trades only while your laptop is on and awake. That's fine: bets sit on Polymarket
   until they resolve, and the bot settles them the next time it runs.

The live order code uses Polymarket's official SDK (`polymarket-client`). The SDK is still
in beta, and this code couldn't be tested against real money before you run it. Watch
your first live cycle, and confirm the first bet on polymarket.com.

## Settings

All settings are in `polybot/config.py`, and any of them can be overridden in `.env`. The
ones you're most likely to change:

| Setting | Default | Meaning |
|---|---|---|
| `STARTING_BANKROLL_USD` | 20 | What the bot treats as its money |
| `MAX_STAKE_USD` | 2 | Largest single bet |
| `DAILY_AI_BUDGET_USD` | 1.00 | Max Claude spend per day |
| `MAX_DRAWDOWN_USD` | 8 | Full stop after losing this much |
| `MIN_EDGE` | 0.05 | Required edge after costs |
| `EXCLUDED_TOPICS` | crypto,sports | Topics the bot never trades |
| `MAX_DAYS_TO_END` | 14 | Only markets that resolve within this many days |

## Layout

```
polybot/
  venues/       market data per venue (Polymarket now; add others here)
  research.py   Claude forecaster with web search + cost tracking
  strategy.py   edge after fees/slippage, sizing
  risk.py       hard limits, kill switch
  brokers/      paper (simulated) and live (official SDK) execution
  engine.py     one full cycle
  report.py     REPORT.md scoreboard
tests/          offline tests
```

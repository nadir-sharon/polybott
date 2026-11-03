# Polybot report: PAPER mode

_Updated 2026-11-03T20:55:46+00:00 UTC_

## Scoreboard

| | |
|---|---|
| Starting bankroll | $20.00 |
| Cash now | $20.00 |
| In open bets (at cost) | $0.00 (0 bets) |
| Realized profit/loss | **$0.00** |
| AI research spent | $1.10 |
| Profit after AI costs | **-$1.10** |
| Settled bets | 0 (0 won, win rate –) |

## Is the AI better than the market?

Brier score on every resolved market the AI studied (lower is better; 0.25 = coin flip).
This is the number that matters: if the AI isn't beating the market here, wins are luck.

- Resolved forecasts: **0**
- AI Brier: **–**
- Market Brier: **–**
- _Too few results to judge yet (need roughly 20+)._

## Open bets

_None._

## Settled bets (latest 20)

_None yet. Bets settle when their market resolves._

## Latest AI research (10)

- **Israel x Iran ceasefire continues through November 7?**  
  AI 0.82 (medium) vs market 0.81 → AI 0.82 vs market 0.81: agrees with market  
  _No direct Israel-Iran strikes appear to have occurred since June, and Trump is signalling a preference for a deal. But a post-midterm US-Israeli strike is actively being planned and Netanyahu is pushing for it, so there is meaningful tail r_
- **Will the Republicans win the Florida governor race in 2026?**  
  AI 0.82 (medium) vs market 0.67 → YES edge +0.038 after fees < 0.05  
  _Election Day is today, so there are no results yet. Donalds (R) leads Jolly (D) by about 4 points in the polling average, and the race is rated Lean Republican by the major forecasters. He also has a large money advantage, though a tighteni_
- **Will the Republicans win the Texas governor race in 2026?**  
  AI 0.73 (medium) vs market 0.64 → AI 0.73 vs market 0.64: agrees with market  
  _Abbott leads polling averages by about 2 points, though the final NYT/Siena and AtlasIntel polls showed Hinojosa slightly ahead. Texas polls have tended to understate Republicans, and Abbott has a large money advantage, so he is a moderate _
- **2026 Balance of Power: R Senate, D House**  
  AI 0.18 (medium) vs market 0.17 → AI 0.18 vs market 0.17: agrees with market  
  _Election Day forecasts give Democrats about 84–99% to win the House and about 65–88% to win the Senate. A Republican Senate with a Democratic House is therefore roughly a 10–21% outcome, and I estimate about 18%. No results were available y_
- **Will the Republicans win the Michigan Senate race in 2026?**  
  AI 0.20 (medium) vs market 0.20 → AI 0.20 vs market 0.20: agrees with market  
  _El-Sayed (D) leads Rogers (R) by about 4-6 points in polling averages entering Election Day, with most late polls showing him ahead. Polling error and some late tightening leave Rogers a real chance, but he is a clear underdog._
- **Will Republicans win Iowa, and lose Alaska, Kansas, Maine, Michigan, Ohio, and Texas?**  
  AI 0.04 (medium) vs market 0.11 → AI 0.04 vs market 0.11: agrees with market  
  _Final polls show Democrats leading in Alaska, Kansas, Maine, Michigan, Ohio and Texas, with Iowa a tie. The market needs Republicans to win only Iowa while losing all six others, which is a narrow and unlikely combination because the races _
- **Will the Democrats win the Texas Senate race in 2026?**  
  AI 0.68 (medium) vs market 0.74 → AI 0.68 vs market 0.74: agrees with market  
  _Final polls show Talarico (D) ahead of Paxton (R) by about 2.5 to 4 points on average, in a favorable midterm environment for Democrats and against a weak GOP nominee. Texas's Republican lean and a history of polls overstating Democrats kee_
- **Will the Democrats win the Michigan Senate race in 2026?**  
  AI 0.79 (medium) vs market 0.79 → AI 0.79 vs market 0.79: agrees with market  
  _El-Sayed (D) leads Rogers (R) by about 5 points in the final polling average, and Cook moved the race to Lean D on Nov 2. Decision Desk HQ gives El-Sayed 75%. Polling error and a close-race possibility keep this short of near-certainty._
- **Will the Republicans win the Texas Senate race in 2026?**  
  AI 0.42 (medium) vs market 0.27 → YES edge +0.039 after fees < 0.05  
  _Final polls show Talarico (D) ahead by roughly 2.5–4 points on average, with a few ties and one Paxton lead. Texas polls have tended to overstate Democrats, and the state is still Republican-leaning, so the result is close to a toss-up with_
- **Will the Democratic Party control the Senate after the 2026 Midterm elections?**  
  AI 0.68 (medium) vs market 0.76 → AI 0.68 vs market 0.76: agrees with market  
  _Final model forecasts (DDHQ about 65%, Poliwave 78%) and late polls show Democrats leading all key Senate toss-ups, but mostly by narrow margins. Democrats need a net gain of four seats for 51, because Vance breaks a 50–50 tie. Correlated p_

## Activity log (latest 40)

```
2026-11-02T17:29:00+00:00  === run start (paper mode) cash $20.00, 0 open ===
2026-11-02T17:29:08+00:00  [scan] 136 markets pass filters, 136 not recently researched
2026-11-02T17:29:08+00:00  [research] Will the Republican Party control the Senate after the 2026 Midterm elections?
2026-11-02T17:29:21+00:00  [decide] AI 0.27 (medium) vs market 0.28 -> skip: AI 0.27 vs market 0.28: agrees with market
2026-11-02T17:29:21+00:00  [research] Will Republicans lose the Alaska, Iowa, Kansas, Maine, Michigan, Ohio, and Texas Senate se
2026-11-02T17:29:34+00:00  [decide] AI 0.12 (medium) vs market 0.32 -> skip: below venue minimum order size
2026-11-02T17:29:34+00:00  [research] 2026 Balance of Power: D Senate, D House
2026-11-02T17:29:44+00:00  [decide] AI 0.69 (medium) vs market 0.72 -> skip: AI 0.69 vs market 0.72: agrees with market
2026-11-03T00:02:06+00:00  === run start (paper mode) cash $20.00, 0 open ===
2026-11-03T00:02:17+00:00  [scan] 138 markets pass filters, 135 not recently researched
2026-11-03T00:02:17+00:00  [research] Will the Democratic Party control the Senate after the 2026 Midterm elections?
2026-11-03T00:02:34+00:00  [decide] AI 0.68 (medium) vs market 0.76 -> skip: AI 0.68 vs market 0.76: agrees with market
2026-11-03T00:02:34+00:00  [research] Will the Republicans win the Texas Senate race in 2026?
2026-11-03T00:02:47+00:00  [decide] AI 0.42 (medium) vs market 0.27 -> skip: YES edge +0.039 after fees < 0.05
2026-11-03T00:02:47+00:00  [research] Will the Democrats win the Michigan Senate race in 2026?
2026-11-03T00:02:58+00:00  [decide] AI 0.79 (medium) vs market 0.79 -> skip: AI 0.79 vs market 0.79: agrees with market
2026-11-03T06:33:46+00:00  === run start (paper mode) cash $20.00, 0 open ===
2026-11-03T06:33:53+00:00  [scan] 136 markets pass filters, 130 not recently researched
2026-11-03T06:33:53+00:00  [research] Will the Democrats win the Texas Senate race in 2026?
2026-11-03T06:34:05+00:00  [decide] AI 0.68 (medium) vs market 0.74 -> skip: AI 0.68 vs market 0.74: agrees with market
2026-11-03T06:34:05+00:00  [research] Will Republicans win Iowa, and lose Alaska, Kansas, Maine, Michigan, Ohio, and Texas?
2026-11-03T06:34:18+00:00  [decide] AI 0.04 (medium) vs market 0.11 -> skip: AI 0.04 vs market 0.11: agrees with market
2026-11-03T06:34:18+00:00  [research] Will the Republicans win the Michigan Senate race in 2026?
2026-11-03T06:34:28+00:00  [decide] AI 0.20 (medium) vs market 0.20 -> skip: AI 0.20 vs market 0.20: agrees with market
2026-11-03T14:37:45+00:00  === run start (paper mode) cash $20.00, 0 open ===
2026-11-03T14:37:53+00:00  [scan] 162 markets pass filters, 155 not recently researched
2026-11-03T14:37:53+00:00  [research] 2026 Balance of Power: R Senate, D House
2026-11-03T14:38:07+00:00  [decide] AI 0.18 (medium) vs market 0.17 -> skip: AI 0.18 vs market 0.17: agrees with market
2026-11-03T14:38:07+00:00  [research] Will the Republicans win the Texas governor race in 2026?
2026-11-03T14:38:22+00:00  [decide] AI 0.73 (medium) vs market 0.64 -> skip: AI 0.73 vs market 0.64: agrees with market
2026-11-03T14:38:22+00:00  [research] Will the Republicans win the Florida governor race in 2026?
2026-11-03T14:38:34+00:00  [decide] AI 0.82 (medium) vs market 0.67 -> skip: YES edge +0.038 after fees < 0.05
2026-11-03T20:55:16+00:00  === run start (paper mode) cash $20.00, 0 open ===
2026-11-03T20:55:24+00:00  [scan] 38 markets pass filters, 38 not recently researched
2026-11-03T20:55:24+00:00  [research] Israel x Iran ceasefire continues through November 7?
2026-11-03T20:55:46+00:00  [decide] AI 0.82 (medium) vs market 0.81 -> skip: AI 0.82 vs market 0.81: agrees with market
2026-11-03T20:55:46+00:00  [budget] daily AI budget $1.00 reached (spent $0.91)
```

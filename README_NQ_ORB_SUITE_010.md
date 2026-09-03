# NQ ORB Research Suite 010

One run. Ten ORB research families. Every configuration in the predeclared finite grids is attempted exactly once.

## The ten models

1. Modern 5-minute formed ORB: opening-range direction + daily trend alignment.
2. 09:30-10:05 value-area/order-flow ORB: OHLCV proxy because current mirror has no MBO/aggressor side.
3. Delayed 25-minute MNQ ORB: immediate vs delayed breakout confirmation family.
4. Tsai timely ORB: direct E-mini Nasdaq-100 1/2/3/4/5-minute probe ranges.
5. Volatility-state ORB: activate ORB only in ex-ante low/high volatility regimes.
6. Distribution-threshold ORB: volatility/statistical breakout thresholds rather than only fixed time-range boundaries.
7. GAORB full grid: threshold-adjusted ORB + protective closing. We brute-force the grid instead of using a genetic algorithm.
8. Neural-network threshold ORB: MLP confidence gate trained on 2023 only and applied forward.
9. Predicted-True-Range ORB: causal forecast of daily range used to gate ORB; HGBR surrogate for the 2026 LSTM paper mechanism.
10. NQ prior-day/overnight-state ORB: continuation/reversal gates inspired by direct Nasdaq-100 futures intraday research.

## What “every combination” means

The mathematical strategy space is infinite. This suite therefore defines a finite grid before looking at results and exhaustively evaluates its full Cartesian product. No random sampling and no evolutionary shortcut is used for the final test.

The generated `grid_manifest.csv` contains every configuration. `grid_completion.json` records the manifest count and attempted count so we can verify that the run did not silently skip configurations.

The current grid contains about 55k unique strategy configurations across the ten families.

## Common execution grid

Where a model supports the parameter:

- entry: intrabar touch or confirmed close/next-bar open
- direction: both / long / short
- stop: opposite ORB boundary, ORB midpoint, 0.5x range, 1.0x range, 1.0x prior daily ATR, 1.5x prior daily ATR
- target: 1R / 1.5R / 2R / 3R / no fixed target
- time exit: 11:30 / 13:00 / 15:59 ET
- primary Strategy Tester risk: $300/trade
- slippage stress: 1 NQ tick per side (0.50 point round trip)
- NQ/MNQ quantity selected from actual stop distance
- maximum 4 NQ / 40 MNQ
- same-bar stop + target ambiguity: stop first

## TradingView-style output

For every valid configuration:

- net profit $
- net R
- profit factor
- win rate
- average trade $
- average R
- average winner / loser
- max drawdown $ / R
- largest win / loss
- max and average winning streak
- max and average losing streak
- daily Sharpe / Sortino
- 2023 / 2024 / 2025 net $, R and PF

Top three configurations from each model also receive:

- complete trade logs
- yearly and monthly Strategy Tester statistics
- full $50/$75/$100/$125/$150/$175/$200/$250/$300 risk grid
- Lucid-style target / trailing-drawdown replay with DLL on and off

## Causality rules

- opening-range values cannot be traded before the range is complete
- previous-session variables are shifted
- opening-volume baselines use prior days only
- ML gates train on 2023 and are used forward
- no trade is held beyond the intraday cutoff
- same-bar ambiguity is pessimistic

2025 has already been inspected elsewhere in this project and is not described as pristine untouched OOS.

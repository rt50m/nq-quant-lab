# Research 6 — High-Density Scale Search

R6 is explicitly built around the project's actual scale objective, not a fixed $300/trade convention.

## Hard development objective

A configuration is `PASS_SCALE` only when, on the existing 2023-01-01 through 2025-12-11 development sample:

- modeled net profit is **at least $50,000**, and
- conservative intratrade maximum drawdown stays **strictly below $2,000**.

The sizing method is part of the search. For every execution path R6 evaluates:

1. fixed NQ quantity, scaled from 1 to the 4-NQ cap subject to the drawdown constraint;
2. fixed MNQ quantity, scaled from 1 to the 40-MNQ cap subject to the drawdown constraint; and
3. fixed-dollar risk budgets from $50 through $2,000, choosing the NQ or MNQ quantity that gives the greatest point-value exposure without exceeding the frozen risk budget.

The retained result is whichever sizing mode generates the most profit while remaining inside the $2,000 drawdown cap. There is **no preference for $300 risk**.

A useful scale-free intuition is profit / |MDD|. With linear fixed-contract sizing, $50k under $2k requires roughly **25x profit-to-drawdown** before contract caps bind.

## Why these families

R5's one-trade/day state rules were too sparse to approach the requested dollars. R6 only tests trigger mechanisms capable of repeated intraday opportunities while allowing one open position at a time and up to 12 completed episodes per day:

- trend pullback continuation;
- rolling breakout continuation;
- failed-breakout reversal;
- VWAP stretch reversal;
- impulse continuation;
- impulse reversal;
- compression breakout; and
- VWAP trend reclaim; and
- VXN implied-volatility-band reversion using the previous available CBOE VXN close from FRED.

Every signal is generated from completed information and enters at the next minute open. A new signal can enter again after the prior trade exits. Opposite signals on the same minute are skipped.

## Execution search

For each signal group R6 freezes a finite grid across:

- ATR stops: 0.20 / 0.35 / 0.55 prior-day ATR;
- target: no fixed target / 1R / 1.5R / 2.5R / 4R;
- maximum hold: 15 / 30 / 60 / 120 minutes;
- trading window: early / core / full RTH; and
- direction: both / long-only / short-only.

That is **390 signal groups × 540 execution settings = 210,600 execution configurations**. Sizing optimization is performed after each trade path rather than redundantly rerunning the price simulation for every risk number.

## Conservative mechanics

- same-minute stop + target -> stop first;
- stop gap-through -> opening price plus adverse slippage, not the stop price;
- next-bar entries and time exits pay 0.25 point slippage per side;
- tick-rounded stops/targets;
- NQ/MNQ commission assumptions match the existing lab reference;
- no overlapping positions;
- hard intraday flat; and
- drawdown includes modeled worst open-trade liquidation, not only closed-trade equity.

## Running

Use **Actions → Research 006 - High Density Scale Search → Run workflow**, enable the full search, and leave the resume ID empty on the first run. Results are uploaded as `r6-results`. Incomplete shards retain resumable checkpoints.

This is still development research on already-examined 2023–2025 data. A $50k/$2k pass is the project's scale hurdle, not proof of future profitability.


### External VXN note
The VXN family uses only the previous available daily VXN close, never the same-day close. The workflow records the downloaded FRED/CBOE source hash and aligned-array hash in `r6_external.json`. The direct NQ motivation is Seeck (2026), which reports regime-dependent reversion after NQ breaches a ±VXN/16 daily band; R6 tests the source band plus nearby multipliers and breach-vs-reclaim entries rather than assuming the paper transfers perfectly to this dataset.

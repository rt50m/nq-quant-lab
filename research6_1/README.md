# Research 6.1 — Impulse Continuation Enhancement

Purpose: determine whether R6's unusually stable Impulse Continuation result (2023 +$4,348 / 2024 +$5,375 / 2025 +$5,094.5; 1,264 funded trades; $14,817.5 net; -$1,881 MDD) contains a stronger conditional edge that can approach the actual project objective: **$50,000+ net across the 35.5-month development set while conservative intratrade MDD remains strictly under $2,000**.

This is not a broad R7 search. It freezes the R6 family, reproduces the exact published R6 baseline, writes a full enriched trade ledger, diagnoses where expectancy comes from, searches only a neighborhood of impulse definitions and causal entry-state filters, then tests static and dynamic management around the rules that survive chronological selection.

## Leakage discipline

- Predicate pair construction is ranked using 2023 only.
- A retained rule must remain positive with PF > 1 and minimum sample in both 2023 and 2024.
- Sizing is chosen on 2023+2024 only and then frozen.
- 2025 is diagnostic only and never selects a filter or sizing.
- A separate full-period `oracle` sizing result is retained only as an explicitly labeled upper bound.
- None of this restores pristine OOS status because 2023–2025 have already been examined in prior research.

## Credible scale hurdle

A `CREDIBLE_SCALE` pass requires all of:

- net >= $50,000,
- conservative intratrade MDD > -$2,000,
- >= 300 funded trades total,
- >= 60 funded trades in each of 2023, 2024, 2025,
- every year profitable,
- no single year contributes more than 60% of total profit.

The looser mathematical `PASS_SCALE` is also reported, but tiny-sample lottery results are not treated as credible.

## New diagnostics

The exact R6 baseline is enriched with MFE, MAE, exit reason, time, side, impulse size, volume z-score, side-adjusted VWAP distance/slope, session move, session range position, 15/30-minute range, gap state, previous-day move, VXN, actual funded symbol/quantity, and sizing skips.

## Management search

Static stop/target/hold neighborhoods plus causal completed-bar management:
- breakeven activation,
- MFE-based trailing stop,
- progress-failure exit,
- cooldown and max-trades/day controls.

All stops/targets remain tick-rounded and adverse same-bar stop/target ambiguity is stop-first.

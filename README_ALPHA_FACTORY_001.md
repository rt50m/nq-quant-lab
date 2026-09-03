# NQ Alpha Factory 001

This is an automated alpha-discovery pipeline, not a hand-written strategy test.

It creates a causal NQ feature library (VWAP, returns, ATR, realized volatility, volume, leak-free intraday volume seasonality, ORB/prior-day geometry, EMA state, time/session structure), generates a large threshold condition pool, screens 220,000 random multi-condition rules, evolves the strongest rules through 3,000-member populations for 16 generations, then rechecks survivors on full sequential data.

It also fits Ridge, HistGradientBoosting and ExtraTrees predictive models on 5/15/30/60-minute forward returns.

Validation discipline:

- 2023 = discovery/search
- 2024 = validation/model selection
- 2025 = already-seen secondary evidence only, not untouched OOS
- horizon-spaced events on the full recheck
- day-clustered t-statistics
- 0.5/1/2/3-point cost stress
- BH-FDR q-values
- day bootstrap on top rules
- threshold-neighborhood robustness tests
- next-bar-open execution conversion for strongest rules
- Lucid-style prop replay across $50/$200 through $250/$1000 risk profiles

A high score is not proof of live alpha. The search is intentionally huge, so false-discovery controls matter more, not less.

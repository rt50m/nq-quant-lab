# VWAP Paper-Inspired Research Sweep 002

This is a **predictive event study**, deliberately different from the first VWAP strategy sweep.

## Why

The core academic VWAP literature is primarily about:
- intraday volume curves and volume forecasting,
- VWAP execution / tracking,
- market impact and transaction costs,
- dynamic adaptation during the trading day,
- intraday seasonality in volume and volatility.

So this sweep uses those ideas as feature families rather than assuming VWAP itself must be traded with a fixed 1R stop/target.

## Research split

- 2023: discovery
- 2024: validation
- 2025: untouched final out-of-sample
- 2025 is never used in the ranking score.

## Scale

The script generates thousands of VWAP/volume/volatility conditions and evaluates each at 5, 15, 30 and 60-minute forward horizons.

## Main families

- trend-state / persistence around VWAP,
- normalized VWAP deviation mean reversion,
- normalized VWAP deviation breakout,
- cumulative-volume surprise + trend,
- dual-anchor alignment,
- pullback/reclaim conditions.

## Important

This is not a finished trading strategy. It is a factor-discovery layer.
Survivors should be turned into separate execution backtests only after they survive OOS and robustness checks.

## Multiple testing

Because the run evaluates over ten thousand condition/horizon hypotheses, it also computes Benjamini-Hochberg FDR q-values for 2023 and 2024. A strict survivor file requires q <= 0.05 in both periods.

# NQ Quant Lab

## Model 001 — VWAP Pullback Continuation

Baseline research specification:

- NQ 1-minute bars
- VWAP source: HLC3
- Primary Session VWAP reset: 18:00 America/New_York (CME Globex session)
- Trend acceptance: at least 8 of last 10 closes on trade side of VWAP
- Pullback: literal touch of VWAP
- Invalidate: 2 consecutive closes on opposite side before confirmation
- Displacement: directional candle, body >= 60% of total range, close in outer 25%, breaks previous bar high/low, closes back on trend side of VWAP
- Confirmation must occur after the touch bar
- Entry: next 1-minute bar open
- Stop: pullback extreme +/- one NQ tick (0.25)
- Target: 1R
- One position at a time
- Conservative same-minute ambiguity: if stop and target are both touched in the same bar, stop is scored first
- Baseline friction: 0.50 NQ points round-trip (one tick each way); commission excluded

The workflow also runs a 09:30 ET reset variant only as a diagnostic for chart-session/VWAP anchoring differences. The 18:00 ET version is the baseline.

The workflow clones the public `MeNameek/AnooReplay` repository, whose daily JSON files were generated from the Kaggle `Dataset_NQ_1min_2022_2025.csv` source, then writes trade-level and summary outputs to a GitHub Actions artifact.

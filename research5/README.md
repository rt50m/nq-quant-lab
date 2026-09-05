# Research 5 — NQ Conditional Edge Discovery

Research 5 changes the question from “which named strategy wins a giant grid?” to:

> **Under which causally observable NQ market states is forward expectancy unusually strong and repeatable?**

The pipeline builds a compact feature matrix once, discovers interpretable state clusters on 2023 only, ranks them on 2024, uses 2025 as an already-examined forward diagnostic, and only then converts surviving state rules into executable strategies.

## Design

- Data: the same timestamp-audited NQ one-minute OHLCV preparation used by Research 4.
- Decision snapshots: every 5 minutes from 10:00 through 15:00 ET.
- Features: prior-session state, gap/overnight state, multi-horizon momentum and realized volatility, VWAP distance/slope, opening-range structure, volume surprise, trend efficiency, compression and location within the current session.
- Forward labels: 15m / 30m / 60m return plus MFE/MAE.
- Discovery: shallow decision-tree leaves plus univariate quantile edge maps. Trees are fit on 2023 only.
- Candidate ranking: 2024 only. 2025 is a diagnostic, not pristine OOS.
- Strategy extraction: next-bar market entry, one trade/day, fixed ATR-normalized stops/targets, conservative stop-first same-bar handling, NQ-first/MNQ-fallback sizing, commissions and slippage.
- No macro-event flags are included in v1 because a verified event calendar is not yet in the repository.

## Run

Open **Actions → Research 005 - Conditional Edge Discovery → Run workflow** and enable **Run full discovery and extracted-strategy backtest**.

The workflow first verifies the implementation, downloads the frozen NQ mirror, rebuilds the audited R4 arrays, then runs R5. The final artifact is `r5-results` and the GitHub job summary prints the top discovered rules and extracted strategies.

## Interpretation

A high-scoring R5 rule is a **development finding**, not a deployable edge. 2023–2025 has already been examined in prior research. Promotion requires new data or another genuinely independent sample, plus execution/cost/parameter-neighbor stress.

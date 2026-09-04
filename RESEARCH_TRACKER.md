# NQ Quant Lab — Research Tracker

This is the canonical status page for the project. Update it whenever a research stage, model audit, stress test, shortlist decision, or execution/data issue changes.

## Current stage

**Research #1 — 10-family NQ ORB exhaustive screen**

- Final exhaustive suite: **55,260 / 55,260 configurations completed — PASS**.
- Test period: 2023–2025 NQ 1-minute OHLCV.
- Primary full-grid sizing: **$300 intended risk/trade**.
- Prop reference: LucidPro 50K, especially the **$2,000 max-loss limit**.
- Mechanical prop screen: minimum 80 trades, historical max drawdown better than -$2,000, then maximize net profit.
- ORB01 is the exception because no $300-risk configuration survives the drawdown constraint.

This is an early screening stage, **not final strategy selection**.

## Core reproducibility files

- `nq_orb_research_suite_010.py`
- `nq_orb_parallel_suite_011.py`
- `.github/workflows/run_nq_orb_research_suite_010.yml`
- `.github/workflows/run_nq_orb_parallel_suite_011.yml`
- `.github/workflows/run_nq_orb_recovery_012.yml`
- `orb_suite_config.json`
- `orb_parallel_suite_011_config.json`
- `source_notes.json`
- `lucid_50k_reference.json`
- `README_NQ_ORB_SUITE_010.md`
- `README_NQ_ORB_PARALLEL_SUITE_011.md`

Recovery 012 final state: **55,260 / 55,260 PASS**.

## Research #1 — best prop-compatible variants

| Model | Variant | Risk | Net P&L | PF | Max DD | Execution/data status |
|---|---|---:|---:|---:|---:|---|
| ORB01 Modern 5m | `C000786` | $75 | +$5,012 | 1.205 | -$1,439.50 | Clean; no $300 variant survives $2k DD cap |
| ORB02 Value/Flow proxy | `C002665` | $300 | +$9,738.25 | 1.949 | -$1,613.25 | Clean CLOSE-entry replacement |
| ORB03 Delayed 25m | `C003740` | $300 | +$14,357 | 1.426 | -$1,902 | Clean |
| ORB04 Tsai/TORB 1R | `C005940/C005942` | $300 | +$87,776.50* | 2.999* | -$1,111* | **UNRESOLVED — tick/sub-minute data required** |
| ORB04 Tsai/TORB 1.5R | `C005945` | $300 | +$113,166* | 2.791* | -$1,835.25* | **UNRESOLVED — tick/sub-minute data required** |
| ORB05 Vol-State | `C013131` | $300 | +$14,893 | 1.617 | -$1,657 | Clean |
| ORB06 Stat-Threshold | `C021672` | $300 | +$14,965.75 | 1.296 | -$1,807.50 | Clean; CLOSE + LONG-only |
| ORB07 GAORB | `C027304` | $300 | +$17,114.13 | 1.313 | -$1,928.13 | Clean; thin DD cushion |
| ORB08 NN Threshold | `C041735` | $300 | +$17,919 | 1.424 | -$1,992 | Clean; ~$8 DD cushion |
| ORB09 Predicted TR | `C048391` | $300 | +$20,562.50 | 1.508 | -$1,656.25 | Clean; mechanical max-P&L winner |
| ORB10 Gap-State | `C051005` | $300 | +$10,963 | 1.579 | -$1,470 | Clean |

\* ORB04 baseline numbers are **not accepted as validated performance** until intrabar ordering is resolved.

## ORB04 execution-integrity finding

The current TOUCH entry code historically ignored a 1-minute bar that hit both upper and lower entry levels and could take a later clean entry.

For the selected 1-minute ORB04 family:

- **436 / 760 trading days (57.4%)** had ambiguous dual-side first-touch ordering.
- Worst-case stress rule: first ambiguous bar = forced losing trade, no later entry.
- 1R stress: **-$58,306**, PF **0.505**, max DD about **-$58.5k**.
- 1.5R stress: **-$37,449**, PF **0.695**, max DD about **-$37.8k**.

**Decision: ORB04 = needs-data / unresolved.**

Resolve the 436 affected dates using tick/sub-minute data before ranking ORB04 as a validated winner.

## Other execution findings

### ORB02 same-bar confirmation

Earlier ORB02 TOUCH configurations could enter intrabar and then use the same breakout candle's closing location to accept/reject that entry.

This is an execution/lookahead problem, but **does not require better data**.

Current clean mechanical replacement: **`C002665`**, which uses CLOSE confirmation before next-bar execution.

### Post-entry same-bar TP/SL

If the same 1-minute bar touches both stop and target after entry, the simulator assumes **stop first**.

That is intentionally conservative.

### Hard data-granularity blockers

Among the currently selected variants, **ORB04 is the only hard data-granularity blocker** found so far.

## Provisional clean shortlist

### 1. ORB09 — preferred robust variant `C047761`

- 291 trades
- +$18,823.50
- PF **1.774**
- Max DD **-$1,339**
- Yearly PF **1.74 / 1.76 / 1.91**

Preferred over mechanical max-P&L `C048391` because of stronger year-to-year stability.

### 2. ORB05 — `C013131`

- 248 trades
- +$14,893
- PF **1.617**
- Max DD **-$1,657**
- Yearly PF **1.45 / 1.78 / 1.72**

### 3. ORB10 — `C051005`

- 192 trades
- +$10,963
- PF **1.579**
- Max DD **-$1,470**
- Yearly PF **1.36 / 1.67 / 1.80**

### Wildcard

**ORB04 1R / 1.5R** — potentially exceptional, but excluded from the clean ranking until tick validation.

### ORB06 decision

`C021672` does **not** displace ORB09/ORB05/ORB10 on current evidence. It produces similar P&L to ORB05 with almost twice the trades, lower PF, lower average R, weaker Sharpe, and larger drawdown.

## Research fidelity

- ORB01 — reconstruction.
- ORB02 — OHLCV proxy; exact MBO/aggressive-flow data unavailable.
- ORB03 — mechanism reconstruction.
- ORB04 — high-fidelity paper family; current 1m execution unresolved from OHLC.
- ORB05 — transfer.
- ORB06 — transfer/reconstruction.
- ORB07 — transfer/full-grid.
- ORB08 — transfer/reconstruction.
- ORB09 — transfer/reconstruction; HGBR surrogate for predicted TR.
- ORB10 — NQ-conditional reconstruction.

See `source_notes.json` and suite source for exact definitions.

## Next research queue

1. **ORB04 tick validation**
   - Resolve the 436 ambiguous dates.
   - Re-run both 1R and 1.5R.

2. **Full execution-integrity audit**
   - Entry lookahead.
   - Impossible same-bar knowledge.
   - Intrabar ambiguity.
   - Session boundaries.
   - Causality.

3. **Robustness / overfit**
   - Parameter-neighbor stability.
   - Rolling yearly/monthly windows.
   - Walk-forward / held-out periods.
   - Regime tests.
   - Outlier dependence.

4. **Execution stress**
   - Wider slippage.
   - Higher commissions.
   - Entry delay / missed fills.
   - Gap-through-stop assumptions.

5. **Path / prop risk**
   - Monte Carlo trade-sequence stress.
   - Drawdown distributions.
   - Lucid 50K trailing-MDD simulations.
   - Funded payout-cycle simulations.
   - Risk-budget optimization only after robustness is established.

6. **Portfolio research**
   - Correlations between surviving models.
   - Simultaneous signals.
   - Portfolio / hedge construction.
   - Shared prop drawdown usage.

7. **Research #2+**
   - Expand beyond these 10 ORB families.
   - Register every new experiment here.

## Tracking convention

Every new experiment should record:

- Research ID and date.
- Hypothesis and source.
- Data and required granularity.
- Causal/execution assumptions.
- Search space and config count.
- Primary ranking criterion.
- Best result.
- Robustness result.
- Prop compatibility.
- Known limitations.
- Decision: **promote / hold / reject / needs-data**.
- Next test.

## Changelog

### 2026-09-04

- Recovery 012 completed Suite 011: **55,260 / 55,260 PASS**.
- ORB06 integrated; did not displace the clean shortlist.
- ORB04 dual-touch ambiguity stress-tested; marked **needs tick data**.
- ORB02 same-bar confirmation issue identified; clean CLOSE alternative selected.
- Repository cleanup plan prepared around the current ORB research program.

# NQ Quant Lab — Research Tracker

Canonical project state. Update this file whenever an experiment, audit finding, shortlist, or data requirement changes.

> Research #1 finds promising edges. Research #2+ tries aggressively to kill them.

## Current stage

**Research #2 grid completed (2026-09-04): 568,296 / 568,296 configurations.**
Five ORB and five non-ORB mechanism reconstructions plus a plain-ORB control.
[Run 33845113018](https://github.com/rt50m/nq-quant-lab/actions/runs/33845113018) succeeded
in 6m 24s. A downloaded-result audit found exact ID coverage; 138 samples and one full
17,760-configuration shard reproduced locally. A separate trade calculator matched
9,462 complete, unambiguous trades across 22 configurations.

See the [Research #2 results and limitations](research2/RESULTS_2026-09-04.md),
[specification](research2/README.md) and [paper register](research2/SOURCES.md).
Provisional further-research candidates: ORB_GAP R2-0283165, CLOSE_MOMENTUM R2-0467854,
and ORB_OPEN_TREND R2-0446464. They do not displace Research #1 without common-engine
and independent-data validation. SURVIVED can include an account unable to size more
trades; the results report excludes this pitfall. All noise-momentum configurations
have data-gap flags. The 2023-2025 interval remains already-examined development data.

**Research #1 — exhaustive 10-family NQ Opening Range Breakout screen: 55,260 / 55,260 configurations completed — PASS.**

This is completion of the research grid, not validation of a deployable strategy. Results and completed research findings below are carried forward from the user-approved handover dated **2026-09-04**; the repository cleanup did not rerun backtests or independently reproduce those results.

- Instrument/data: NQ futures, one-minute OHLCV; NQ/MNQ position sizing.
- Primary evaluated period: 2023–2025, with earlier supporting history for lagged features/training.
- Sessions: Eastern Time; regular trading session approximately 09:30–16:00.
- One-minute OHLCV does not reveal event ordering within each candle.
- 2025 has already been examined and is **not an untouched holdout**.
- Current clean shortlist: **ORB09 C047761 → ORB05 C013131 → ORB10 C051005**.
- ORB04 remains **NEEDS-DATA**, outside the clean shortlist.

## Prop selection rules

For this stage, “prop compatible” means passing a historical drawdown screen against the **$2,000 max-loss reference**. It does not establish future account survival or compliance with an EOD trailing account path.

Mechanical selection for Models 2–10:

1. $300 intended risk per trade.
2. At least 80 trades overall.
3. Sufficient 2024 trades; the historical selection code used at least 20.
4. Historical maximum drawdown strictly better than -$2,000.
5. Maximize net profit among qualifying configurations, subject to execution-integrity exclusions.

ORB01 has no qualifying $300 variant; its recorded exception uses $75 intended risk.

**Do not drive the current shortlist with evaluation pass rates, payout optimization, or funded consistency rules.** Prefer stronger stability and edge quality over a small increase in in-sample profit. Prop-account path simulation and risk-budget optimization come later, after robustness testing.

### Historical suite assumptions

These are research settings, not a fresh verification of current firm terms. Re-verify external LucidPro rules before future decisions that depend on them.

| Setting | Recorded value |
|---|---:|
| Starting equity | $50,000 |
| Profit target | $3,000 |
| Max-loss limit | $2,000 |
| Daily loss limit when enabled | $1,200 |
| EOD trailing loss-floor lock | $50,100 |
| Maximum position | 4 NQ / 40 MNQ |
| Primary intended risk | $300/trade |
| NQ / MNQ point value | $20 / $2 |
| NQ / MNQ round-trip commission | $3.50 / $1.00 per contract |
| Round-trip slippage | 0.50 NQ points |
| Risk grid | $50, $75, $100, $125, $150, $175, $200, $250, $300 |

The simulator sizes NQ where possible, otherwise MNQ. Intended risk is not necessarily identical to realized risk after contract rounding and costs. See [the reference](lucid_50k_reference.json) and suite source.

## Core reproducibility files

| Role | Files |
|---|---|
| Backtest and parallel runner | [Suite 010](nq_orb_research_suite_010.py), [Suite 011](nq_orb_parallel_suite_011.py) |
| Workflows | [Suite 010](.github/workflows/run_nq_orb_research_suite_010.yml), [Suite 011](.github/workflows/run_nq_orb_parallel_suite_011.yml), [Recovery 012](.github/workflows/run_nq_orb_recovery_012.yml) |
| Configurations | [Suite 010 config](orb_suite_config.json), [Suite 011 config](orb_parallel_suite_011_config.json) |
| Sources and account reference | [Source/fidelity notes](source_notes.json), [Lucid reference](lucid_50k_reference.json) |
| Suite documentation | [Suite 010 guide](README_NQ_ORB_SUITE_010.md), [Suite 011 guide](README_NQ_ORB_PARALLEL_SUITE_011.md) |
| Project entry and state | [README](README.md), this tracker |

Suite 010 contains the backtest logic. Suite 011 imports it and adds shared preparation, deterministic shards, checkpoints, and aggregation. Recovery 012 completed ORB03 with 6 recovery shards and ORB06 with 20 after original shards exceeded runtime.

The suite guides describe the original implementation and intended audits. The execution findings in this tracker supersede broad historical claims that all same-bar ambiguity or causality issues have been resolved.

### Final run and artifact references

Use completed recovery outputs, not old partial ORB03/ORB06 artifacts.

| Purpose | Reference |
|---|---|
| Original Suite 011 run | [33754805257](https://github.com/rt50m/nq-quant-lab/actions/runs/33754805257) |
| Final Recovery 012 run | [33829775573](https://github.com/rt50m/nq-quant-lab/actions/runs/33829775573) |
| Final recovered artifact | `nq-orb-parallel-suite-011-recovered-final-a1` — ID `9923398832` |
| ORB06 complete artifact | `recovery012-a1-model-orb06-complete` — ID `9923385731` |
| ORB03 complete artifact | `recovery012-a1-model-orb03-complete` — ID `9922295286` |

Final outputs include `all_configuration_results_011.csv` (reported 55,260 rows), `model_completion_overview.csv`, `summary_011.md`, `top_10_per_model_011.csv`, and `top_500_011.csv`. Artifact references are recorded provenance; availability and contents were not revalidated during this documentation cleanup.

## Model registry

Fidelity describes the relationship to source research, separately from whether the encoded strategy is executable. ORB02 lacks MBO/aggressive-flow inputs and is an OHLCV proxy. ORB07 exhaustively grids its encoded family instead of using genetic selection. ORB09 uses a HistGradientBoostingRegressor surrogate rather than the source's LSTM architecture.

| Model | Family | Fidelity | Configs |
|---|---|---|---:|
| ORB01 | Modern 5m Formed | RECONSTRUCTION | 1,080 |
| ORB02 | Value Area / Flow | OHLCV_PROXY | 2,160 |
| ORB03 | Delayed 25m | MECHANISM_RECONSTRUCTION | 2,700 |
| ORB04 | Tsai / TORB | HIGH conceptual paper fidelity; execution unresolved | 2,700 |
| ORB05 | Volatility-State | TRANSFER | 6,480 |
| ORB06 | Statistical Threshold | TRANSFER_RECONSTRUCTION | 9,720 |
| ORB07 | GAORB Full Grid | TRANSFER_FULL_GRID | 4,500 |
| ORB08 | Neural Network Threshold | TRANSFER_RECONSTRUCTION | 16,200 |
| ORB09 | Predicted True Range | TRANSFER_RECONSTRUCTION | 3,240 |
| ORB10 | NQ Gap-State | NQ_CONDITIONAL_RECONSTRUCTION | 6,480 |
| **Total** | | | **55,260** |

### Mechanical prop screen and decisions

All monetary results use $300 intended risk except ORB01 at $75. Annual PF columns are 2023 / 2024 / 2025. “Clean” means no identified blocker in the recorded checks under stated simulation assumptions, not full production validation or exact paper replication.

**PROMOTE means advance to robustness research only.** HOLD means retain without advancing to the current shortlist. NEEDS-DATA means a material data blocker; NEEDS-RETEST means a new test is required; REJECT means do not advance on current evidence.

| Model | Mechanical reference | Preferred if different | Net P&L | PF | Max DD | Annual PF | Execution/data status | Decision |
|---|---|---|---:|---:|---:|---|---|---|
| ORB01 | C000786 @ $75 | — | +$5,012 | ~1.21 | -$1,439.50 | Not supplied at $75 | Clean in recorded checks; no $300 qualifier | HOLD |
| ORB02 | C002514, clean replacement | — | +$9,132.25 | 1.826 | -$1,671.25 | 1.68 / 2.05 / 1.77 | CLOSE, close_loc=0 | HOLD |
| ORB03 | C003740 | — | +$14,357 | 1.426 | -$1,902 | 1.25 / 1.82 / 1.23 | Clean; thin DD cushion | HOLD |
| ORB04 1R | C005940 / C005942 | — | +$87,776.50* | 2.999* | -$1,111* | 3.05 / 2.77 / 3.21* | First-touch ordering unresolved | NEEDS-DATA |
| ORB04 1.5R | C005945 | — | +$113,166* | 2.791* | -$1,835.25* | 2.77 / 2.79 / 2.81* | First-touch ordering unresolved | NEEDS-DATA |
| ORB05 | C013131 | — | +$14,893 | 1.617 | -$1,657 | 1.45 / 1.78 / 1.72 | Clean in recorded checks | PROMOTE |
| ORB06 | C021672 | — | +$14,965.75 | 1.296 | -$1,807.50 | 1.24 / 1.35 / 1.32 | CLOSE + LONG-only | HOLD |
| ORB07 | C027304 | — | +$17,114.13 | 1.313 | -$1,928.13 | 1.38 / 1.34 / 1.17 | Clean; ~$72 DD cushion | HOLD |
| ORB08 | C040380 | — | +$17,919 | 1.424 | -$1,992 | 1.61 / 1.45 / 1.13 | Clean; ~$8 DD cushion | HOLD |
| ORB09 | C048391 | **C047761** | +$20,562.50 | 1.508 | -$1,656.25 | 1.90 / 1.32 / 1.21 | Clean CLOSE mechanical winner; preferred stats below | PROMOTE preferred variant |
| ORB10 | C051005 | — | +$10,963 | 1.579 | -$1,470 | 1.36 / 1.67 / 1.80 | Clean in recorded checks | PROMOTE |

\* **ORB04 baseline performance is optimistic and is not accepted as validated.** It is retained for comparison with a future high-resolution replay.

### Canonical IDs and recorded settings

Times below are ET. CLOSE refers to confirmed-close / next-bar execution in the encoded suite.

| Model / variant | ORB | Entry / direction | Stop / target | Exit cap | Filter / condition |
|---|---|---|---|---|---|
| ORB01 C000786 | 5m | CLOSE / BOTH | WIDTH_0.5 / 3R | 15:59 | Opening-direction filter |
| ORB02 C002514 | 35m | CLOSE / BOTH | MID / none | 15:59 | volz=1.0; close_loc=0 |
| ORB03 C003740 | 25m | TOUCH / LONG | OPPOSITE / 3R | 13:00 | delay=0 |
| ORB04 C005940 / C005942 | 1m | TOUCH / BOTH | OPPOSITE / 1R | 11:30 / 15:59 | No additional filter |
| ORB04 C005945 | 1m | TOUCH / BOTH | OPPOSITE / 1.5R | 15:59 | No additional filter |
| ORB05 C013131 | 30m | TOUCH / BOTH | OPPOSITE / none | 15:59 | vol_lb=10; LOW33 |
| ORB06 C021672 | 1m statistical structure | CLOSE / LONG | OPPOSITE / 1.5R | 13:00 | stat lookback=20; k=0.25 |
| ORB07 C027304 | 30m | TOUCH / BOTH | OPPOSITE / 2R | 15:59 | eps_up=0; eps_dn=+1 |
| ORB08 C040380 | 30m | TOUCH / BOTH | OPPOSITE / 2R | 15:59 | NN=8; alpha=.0001; probability=.50 |
| ORB09 C048391 mechanical | 30m | CLOSE / BOTH | MID / 3R | 13:00 | HGBR_SHALLOW; q=.67 |
| ORB09 C047761 preferred | 30m | TOUCH / BOTH | OPPOSITE / 3R | 13:00 | HGBR_SHALLOW; q=.67 |
| ORB10 C051005 | 15m | TOUCH / BOTH | OPPOSITE / 1.5R | 15:59 | REVERSAL; gap threshold=.005 |

Recorded exact-performance ties do not automatically establish robustness:

- ORB03: C003740 / C003965; track C003740.
- ORB04 1R: C005940 / C005942 differ in time cap; historical trades resolve before either cap. Retain the 1R family and the separate 1.5R variant pending data.
- ORB05: C013131 / C013671; track C013131.
- ORB08: C040380 / C040385 / C041730 / C041735; track C040380.
- ORB09 mechanical: C048391 / C048394; track C048391.
- **ORB02 correction:** C002514 is the intended clean reference. The earlier tracker used C002665; that entry and its statistics are superseded by this handover.
- Never replace ORB09's preferred C047761 with C048391 merely because the latter has greater total profit.

### Original research-rank winners

These are historical score winners, not the current prop shortlist. The score was approximately `log(PF) * sqrt(trades) + 0.25 * avg_R * sqrt(trades)`, with minimum-trade constraints.

| Model | Original winner | Net P&L | PF | Max DD |
|---|---|---:|---:|---:|
| ORB01 | C000798 | +$29,305 | 1.20 | -$16,843.50 |
| ORB02 | C001225 | +$6,806.50 | 2.01 | -$757.50 |
| ORB03 | C003309 | +$18,797 | 1.36 | -$2,979 |
| ORB04 | C005954 | +$290,146* | 2.77* | -$7,222* |
| ORB05 | C010259 | +$31,680.75 | 1.50 | -$9,675.50 |
| ORB06 | C024018 | +$86,609.25 | 1.71 | -$16,386 |
| ORB07 | C027424 | +$20,373.94 | 1.42 | -$2,387.19 |
| ORB08 | C035090 | +$29,276 | 1.45 | -$4,694 |
| ORB09 | C047761 | +$18,823.50 | 1.77 | -$1,339 |
| ORB10 | C051005 | +$10,963 | 1.58 | -$1,470 |

These figures preserve research history without endorsing execution validity. ORB02 TOUCH/close-location candidates need the exclusion described below; ORB04 figures remain unvalidated.

## Execution and data findings

### ORB04: ambiguous first entry, not merely a skipped day

The TOUCH entry logic detects whether a candle hits the upper and lower entry levels. When both are hit, the historical code skips **that bar** and can take a later clean entry. It does not necessarily skip the whole day.

For the selected 1m ORB04 variants, **436 / 760 trading days (57.4%)** had ambiguous dual-side first-touch ordering. Ignoring that first eligible entry can bias the backtest by substituting a later opportunity.

One-minute OHLC cannot establish which boundary occurred first. Tick/transaction data or sufficiently granular sub-minute data must resolve the actual entry and subsequent stop/target sequence. Finer bars that remain ambiguous will still require better ordering data.

### Completed ORB04 adverse stress

Rule: the first eligible candle touching both entry levels becomes an immediate losing trade, with no later entry that day. Losses use the actual stop, position sizing, commission, and slippage; they are not synthetic fixed -$300 amounts. All 436 affected days replace baseline trades.

| Variant | Baseline net | Baseline PF | Baseline DD | Adverse-stress net | Stress PF | Stress DD |
|---|---:|---:|---:|---:|---:|---:|
| 1R | +$87,776.50* | 2.999* | -$1,111* | -$58,305.50 | 0.505 | -$58,522 |
| 1.5R | +$113,166* | 2.791* | -$1,835.25* | approximately -$37,449 | 0.695 | approximately -$37,780 |

The 1R stress had 760 trades, 38.42% win rate, -0.317 average R, -5.37 Sharpe, and a 9-trade maximum losing streak. About 1/36 months remained profitable. The 1.5R stress had approximately 35.66% win rate, -0.198 average R, -2.82 Sharpe, and a 13-trade maximum losing streak; about 7/36 months remained profitable.

This is a deliberately adverse scenario under the stated assumptions, not a measurement of actual tick execution or proof that ORB04 must lose. Neither the optimistic baseline nor this scenario establishes the true performance.

**Decision: NEEDS-DATA.** The handover reports 436 identified dates; obtain the date-level audit output and high-resolution data for those dates, replay both target families, and reassess. Do not rank ORB04 as validated before this work.

### ORB02: same-candle close-location knowledge

Old candidate **C001345** combines TOUCH entry with `close_loc > 0`, so a full candle's eventual closing location determines whether an earlier intrabar entry counts. That information is unavailable at the touch.

This is an execution/lookahead issue, separate from missing tick data. Current clean reference **C002514** uses CLOSE and `close_loc=0`, disabling the problematic block. Its settings/statistics above supersede the previous C002665 tracker entry. A future causal code fix is a separate research change; this cleanup leaves the backtest logic untouched.

### Other candidates and post-entry ambiguity

The recorded first-trigger audit found zero equivalent dual-side ambiguous days for ORB01 C000786, old ORB02 C001345, ORB03 C003740, ORB05 C013131, ORB07 C027304, ORB08 C040380, ORB09 C047761, and ORB10 C051005. ORB06 C021672 is CLOSE + LONG-only; ORB09 C048391 is CLOSE. Zero first-touch ambiguity does not clear ORB02's separate closing-location flaw.

When an entered trade's candle touches both stop and target, the simulator assumes **stop first**. This conservative exit convention does not fix skipped ambiguous entries.

ORB04 is the only hard first-touch data-granularity blocker identified among the currently selected candidates. A full execution-integrity audit remains necessary for every survivor.

## Provisional clean shortlist

| Rank | Model / configuration | Trades | Net P&L | PF | Max DD | Annual PF | Avg R | Sharpe |
|---|---|---:|---:|---:|---:|---|---:|---:|
| 1 | ORB09 C047761 | 291 | +$18,823.50 | 1.774 | -$1,339 | 1.74 / 1.76 / 1.91 | +0.287 | 3.70 |
| 2 | ORB05 C013131 | 248 | +$14,893 | 1.617 | -$1,657 | 1.45 / 1.78 / 1.72 | +0.240 | 2.79 |
| 3 | ORB10 C051005 | 192 | +$10,963 | 1.579 | -$1,470 | 1.36 / 1.67 / 1.80 | +0.239 | 3.36 |

ORB09 has 29 profitable / 35 active months and a maximum loss streak of 4. It is preferred over C048391 because yearly PF is more stable, with lower DD and higher PF/Sharpe. ORB05 has a stronger edge per trade than ORB06. ORB10 has improving annual PF and more drawdown cushion than several mechanical competitors.

ORB06 C021672 records 465 trades, +$14,965.75, PF 1.296, average R +0.117, DD -$1,807.50, and Sharpe 1.88. It earns only about $73 more than ORB05 with almost twice the trades and weaker edge/risk statistics. **It does not displace the clean top three.**

The earlier conceptual research board was ORB04* / ORB09 / ORB05. Keep that historical distinction visible, but the actionable research shortlist excludes ORB04. Only ORB04 intentionally retains both 1R and 1.5R target families as a needs-data wildcard.

## Research #2+ queue

Work in this order where data availability permits; register each new experiment.

1. **ORB04 high-resolution validation:** recover the 436-date list; obtain sufficient event ordering; reconstruct true entries and exits; rerun 1R and 1.5R; reassess P&L, PF, DD, yearly stability, and shortlist eligibility.
2. **Execution-integrity audit:** same-bar future knowledge, unavailable high/low/close inputs, next-bar execution, timestamp alignment, session boundaries, gap-through stops, causal features/training, position sizing, commissions, and slippage.
3. **Parameter-neighbor stability:** opening length, stops, targets, exit times, filters, thresholds, and ML settings. Seek broad stable regions rather than isolated winners.
4. **Rolling performance and regimes:** 3-, 6-, and 12-month windows, annual/monthly results, high/low volatility, bull/bear conditions, and alternate periods.
5. **Out-of-sample / walk-forward:** train/test separation, expanding-window selection, and an untouched final holdout. Research #1 selected configurations on already-examined data.
6. **Outlier dependence:** concentration in the top 1/5/10 trades, best month, and best year.
7. **Trade-path and Monte Carlo stress:** loss clustering, losing streaks, DD duration, recovery time, sequence risk, DD distributions, and breaches of the $2,000 reference.
8. **Cost and execution stress:** 0.75 / 1.0 / 1.5+ points round-trip slippage, higher commissions, opening fills, delayed entries, and missed fills.
9. **Prop-account path simulation, later:** EOD trailing MLL, DLL, start-date effects, risk budgets/scaling, target timing, and payout cycles after robustness is established. Historical rolling-start replay frequencies are not literal future probabilities.
10. **Portfolio / hedge research:** correlations, simultaneous signals, common loss days, regime diversification, portfolio DD, and shared account limits for surviving models.
11. **New strategy families:** expand beyond ORB; keep Research #2, #3, and later hypotheses distinct and traceable.

## Experiment tracking convention

Use the following fields for each new research entry. Mark unperformed tests as pending rather than implying completion.

| Field | Record |
|---|---|
| Identity | Research ID, date, hypothesis, source/paper/inspiration, fidelity |
| Data | Instrument, dataset/version, evaluated dates, required granularity, session |
| Method | Causal/execution assumptions, search space, configuration count, selection criterion |
| Provenance | Code commit, run IDs, artifact IDs/names, result paths |
| Results | Best raw result, best prop-compatible result, preferred variant and rationale |
| Validation | Robustness, OOS/walk-forward, cost/slippage stress |
| Limitations | Known methodological issues, execution assumptions, data blockers |
| Decision | PROMOTE / HOLD / REJECT / NEEDS-DATA / NEEDS-RETEST |
| Follow-up | Next test and evidence required to change the decision |

## Changelog

### 2026-09-04

- Recovery 012 reported completion of all 55,260 Suite 011 configurations; ORB06 integrated without displacing the clean shortlist.
- Recorded ORB04's 436/760 ambiguous first-touch days and adverse stress outcomes; retained both target families as NEEDS-DATA.
- Recorded ORB02's close-location execution issue; corrected canonical clean reference to C002514 per the final handover.
- Standardized ORB08 tracking on C040380; retained its exact-performance alternatives.
- Preserved ORB09 C048391 as the mechanical maximum and C047761 as the preferred robustness candidate.
- Clarified that the current shortlist is driven by drawdown compatibility and edge stability, not pass-rate or payout optimization.
- Expanded this existing tracker with the full model registry, assumptions, run/artifact provenance, decisions, and future research convention.
- Consolidated the root README around active ORB research and removed remaining obsolete experiments and redundant root documents; superseded files remain recoverable through Git history. Active ORB Python, workflows, configs, references, and suite guides are preserved.

# Research #3 — NQ edge discovery

**Ten models, 14,229 frozen configurations including controls.** This is a new
development study on the already examined NQ history, not an untouched holdout.
See [research rationale](RESEARCH_PLAN.md), [37-source register](SOURCES.md), and
the executable parameter contract [grid.json](grid.json).

## Run on GitHub

1. Open **Actions → Research 003 - NQ edge discovery → Run workflow**.
2. Keep branch **main**. Check **Run all ten models and automatic analysis after verification**.
3. Leave the previous run ID blank for the first run. Click **Run workflow**.

GitHub verifies execution and signal causality, downloads frozen public NQ data,
runs all 32 shards (up to eight concurrently), then builds the all-ten breakdown,
chronological selection report, controls and finalist execution stresses. Your laptop,
browser and Codex can be closed. The workflow calls no AI API and has no Codex monitor.

Full completion must say **14,229 / 14,229** in the aggregate job. A successful
verification job alone does not mean the research ran. Download **r3-results** and
share the run link after completion. Results expire after 90 days; checkpoints after 30.

GitHub-hosted jobs have time limits: these search jobs allow 350 minutes, with six
40-minute work windows and an artifact upload after each. Completed configuration
groups are saved atomically. If a runner dies, work since its last successful upload
can need repeating; preservation of every second is not guaranteed. A partial run
cannot publish a complete leaderboard. To resume, run the same workflow/code again
with full search checked and the prior run ID supplied. Missing prior shard artifacts
or a changed code/data identity produce an explicit error, not a silent fresh start.

## Frozen model implementations

| Model | Executable mechanism | Candidate rows | Control rows |
|---|---|---:|---:|
| M01 | Prior-RTH-close standardized momentum; 15/30/60-minute decisions, hysteresis, optional strength sizing; trade only resize deltas | 1,296 | 18 |
| M02 | Prior-session/gap/lagged-volatility/Monday ridge forecast; optional sign and magnitude interactions; next-open morning trade | 864 | 108 |
| M03 | Previous-close-to-10:00 signal predicts 15:30–15:59; sign or rolling ridge forecast | 216 | 72 |
| M04 | Opening-gap forecast of 15:30–15:59 using one/two regression states; prior-only filtering | 144 | 18 |
| M05 | Gap-adjusted historical same-clock noise bands; band or band/VWAP trailing exits and one/three entries | 1,728 | 18 |
| M06 | VWAP direction with ATR-scaled entry/exit bands, 5/15-minute decisions, one/three entries | 432 | 18 |
| M07 | Overnight-inclusive empirical RV/BV jump score; gap fade with optional five-minute confirmation | 864 | 432 |
| M08 | 5/15/30-minute ORB, later completed retest/rejection, next-open entry, boundary/retest stop | 1,944 | 81 |
| M09 | Trailing confirmed extrema; prior bounce count and level aging; delayed rejection entry | 2,916 | 18 |
| M10 | Shrunk prior same-half-hour returns; equal/exponential weights, 20/40/60-session history | 2,808 | 234 |
| **Total** | **Ten hypotheses plus labeled controls** | **13,212** | **1,017** |

The executable grid supersedes the proposal's open-ended menus. Every valid product
in grid.json is enumerated before testing. These are deliberately bounded settings,
not every continuous value or every cross-model combination. Opening lengths are
settings within M08, not additional models. Control rows are excluded from candidate
rankings. Risk is $50/75/100/125/150/175/200/250/300. Protective stops are 0.1/0.2 of
lagged 14-session daily ATR except M08, which uses its observed structural stop.
Model-specific targets and exits remain in place; there is no generic shared TP grid.

Important implementation boundaries:

- M01 follows a disclosed bank mechanism with our own thresholds and risk sizing;
  it is not an exact Goldman or Morgan Stanley replica. Same-side resizing keeps
  the current NQ/MNQ instrument until flat, updates weighted entry for additions,
  realizes reductions, and charges only the quantity actually traded.
- M02/M03/M04 forecast thresholds include a 1.5-point expected-cost allowance plus
  the declared uncertainty gate where applicable. The execution simulator separately
  charges the actual contract-dependent costs; this forecast gate is an approximation.
- M04 uses Gaussian regression-state EM, a 20-observation minimum expected state
  membership, at most 100 iterations and a coefficient-change tolerance of 1e-6.
  Fits are refreshed every 21 sessions. States advance between observed complete
  closing windows; shortened/missing closing windows have no state observation.
  Failed fits produce no forecast and are counted, not substituted with an oracle.
- M05 is the one explicit fuller reconstruction of an R2 family. It uses scheduled
  direction changes; an unchanged signal cannot reopen every minute after a stop.
- M07's unequal overnight/intraday durations prevent claiming a calibrated BNS
  p-value. Thresholds 2.3263/3.0902 apply to an **empirical jump score**. The gap must
  be the largest sampled component. Its fixed-gap control estimates a comparably
  selective threshold using prior event frequency only.
- M08 never infers break/retest order inside one candle. Stops use the known boundary
  or retest extreme, adjusted one tick. Nominal targets are fixed from the executable
  opening quote and base slippage; stress tests preserve those price levels.
- M09 confirms a pivot two bars later, merges nearby active levels, counts only
  earlier completed bounces, and exits at twice the frozen zone half-width or the
  holding deadline. The opposite-zone target discussed in the proposal is not in v1.
- M10's 09:30 slot enters at 09:31, and the last slot ends at 15:59. Its static-clock
  control freezes the first 126 observations rather than selecting a clock interval
  using future returns. Each interval is counted in the search universe.

## Execution and account path

All signals use **NQ OHLCV only**. Completed-bar decisions execute at a later minute
open with adverse slippage. Whole NQ contracts are preferred; MNQ is used when no NQ
fits. There is no upward rounding to hit intended risk. Base slippage is 0.25 point
per side; NQ commission $1.75 per side and MNQ $0.50 per side.

The named reference is the project's LucidPro 50K evaluation, DLL ON profile recorded
on 4 September 2026: $50,000 starting equity, $2,000 EOD trailing floor capped at
$50,100, $1,200 firm daily loss limit, stricter $1,000 personal daily stop, a $25
protection buffer, and at most 4 NQ or 40 MNQ. All normal-session positions close by
**15:59 ET**. Shortened cash sessions are excluded by the calendar before trading;
their completed data may still enter lagged features. This is not a universal firm
rules engine, funded/payout simulator or evaluation-pass calculation.

Daily protection includes realized P&L, entry fees and open liquidation P&L. A loss
does not reset when re-entering. Protective exits lock the day. Open gaps are handled
before intrabar ranges and their actual losses are preserved. Stop and target touched
in one bar means stop first with an ambiguity flag. Time exits use the open, not the
later bar extreme. Dynamic stop updates apply only after their source bar completes.

Missing observations required by a signal or an active trade mark an unknown path.
Account replay stops there; future account equity is not fabricated. Missing unrelated
flat-period bars do not invalidate fixed-time models. Independent-strategy summaries
exclude unknown-day P&L and label the omissions; they cannot qualify an unresolved
account as a survivor. Few trades, zero-size inactivity and protection exits are visible.

## Automatic outputs and interpretation

- **ALL_10_BREAKDOWN.md / model_breakdown.json:** best historical net-profit variant,
  best qualifying account variant (or NONE), evidence status and decision for all ten.
- **all_results.csv / all_daily.npz:** every configuration, daily P&L, event-day and
  missing-path masks; preserve the entire trial count for later analysis.
- **chronological_choices.json / chronological_daily.csv:** month-start selection
  using only preceding 126–252 sessions, at least 20 prior event days, positive training
  profit and training drawdown above -$2,000. This is reused-data development selection,
  not a pristine holdout or a continuously replayed account switching models.
- **matched_date_controls.csv:** comparisons restricted to common eligible known dates.
- **finalist_cost_stress.csv:** base/double/triple slippage and a one-minute execution
  delay, with fees, quantities and account paths recomputed.
- **model_daily_correlation.csv:** descriptive dependence between chronological model
  streams, not a claim that the ten hypotheses are independent.
- **finalist_configs.json / selected daily CSVs:** reproducible chosen configurations
  and their equity-path inputs. **data_quality.json** retains raw coverage limitations.

The provisional prop screen requires an unbreached known account path, positive account
profit, at least 80 distinct account event days, and independent closed-equity drawdown
above -$2,000. Survival by inactivity is disclosed through event counts and size skips;
this screen is not final approval. The best profit variant can fail that screen.

Uncertainty uses a 20-day circular block bootstrap (500 draws) and an approximate
deflated-Sharpe diagnostic with the full candidate-row count as a conservative trial
bound. Dependence and reused history limit interpretation. No significance statistic
turns 2023–2025 into unseen data. Independent prices, roll verification and prospective
or genuinely unexamined dates remain required before trading or replacing R1 leaders.

## Local execution

Use Python 3.12 and the pinned requirements. From the repository root:

```sh
pip install -r research3/requirements.txt
python -m unittest discover -s research3 -p 'test_*.py' -v
python research3/run.py download --out data_r3
python research3/run.py prepare --data data_r3 --out prepared_r3
python research3/run.py smoke --prepared prepared_r3 --out smoke_r3
python research3/run.py shard --prepared prepared_r3 --out checkpoint --index 0 --count 32
python research3/run.py aggregate --prepared prepared_r3 --parts all_checkpoints --out results_r3
```

Run each shard index 0–31 before aggregation. Checkpoints are tied to code, exact grid,
data hash and assignment. Each committed block has a checked SHA-256 payload. Interrupted
blocks are recomputed; changed or corrupt completed blocks are rejected. The data loader
reuses R2's public pinned mirror and raw-validation logic, independently frozen in R3.
It does not use Git authentication or contact an AI service.

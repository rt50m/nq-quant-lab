# Research #4 coverage contract

Status: research design, 2026-09-04. User requests 30 ORB variants plus model 31, an inside-range target strategy, all valid combinations within each variant, and no repetition of earlier tested strategies. No full run has been started.

## What Research #2 actually tested for ORB + VWAP

Source of truth: research2/grid.json, run.py signal_specs/all_configs/signals, and RESULTS_2026-09-04.md.

Signal: completed close beyond the opening high/low AND on the same directional side of cumulative RTH typical-price VWAP, with a minimum gap in lagged daily-ATR units. First qualifying signal only; next-minute market entry; one trade per session.

| Axis | Values |
|---|---|
| Opening range | 5, 15, 30 minutes |
| Qualifying-close confirmation | 1 or 2 bars |
| Direction | Both, long only, short only |
| Price-to-VWAP minimum buffer | 0, 0.01, 0.025 times lagged daily ATR |
| Risk budget | $50, 75, 100, 125, 150, 175, 200, 250, 300 |
| Initial stop distance | 0.05, 0.1, 0.2 times lagged daily ATR |
| Target | 1R, 1.5R, 3R, no target |
| Trailing | None, breakeven after a completed 1R favorable close |
| Time exit | 11:30, 13:00, 15:59 ET |

3 x 2 x 3 x 3 x 9 x 3 x 4 x 2 x 3 = **34,992 configurations**. The archived completion report records this count. These are not 34,992 independent entry hypotheses. The signal axes produce 54 specifications before risk/exit combinations.

Fixed boundaries included RTH VWAP anchor, typical-price VWAP approximation, entry cutoff, next-open entry, one trade daily and the execution/account model. The search did NOT enumerate every VWAP anchor, slope condition, reclaim sequence, exit use, continuous threshold, stop scheme or cross-indicator combination. R3's VWAP/noise models also do not exhaust VWAP or imply that every ORB/VWAP interaction was tested.

## Meaning of exhaustive for R4

Every valid combination of a declared, versioned finite set of choices will be evaluated for each selected variant. The phrase "every possible setting" must not be used without that finite scope. Indicator formulas, real-valued thresholds, time resolution and arbitrary rule combinations have no finite endpoint.

Before launch:

1. Enumerate each model's mandatory novel mechanism, tunable axes, fixed boundaries and invalid combinations. Include opening windows, direction, confirmation/entry schedule, relevant stop and target choices, relevant management rules, risk, entry deadline and forced exit. Model-specific exceptions are explicit: volume-clock ranges, nested ranges, resting limits, midpoint targets, partial positions and staged entry must not be forced into contradictory generic settings.
2. Freeze the menu before seeing results. Current values in CANDIDATES.md are drafts, not the executable manifest. Do not claim full coverage until that manifest exists.
3. Form the Cartesian product of all compatible selected axes per model; remove only documented invalid combinations and semantically duplicated configurations. Do not use a performance screen, random search, early stopping, or coarse-to-fine selection to claim all-combination completion.
4. Exclude prior R1-R3 rule sets and neutral settings that reduce a new model to an old one. Reuse archived results as historical references. A new engine alone must not be used to rebrand an old strategy as a new candidate.
5. Share causal feature calculations and identical signals. Deduplicate complete execution policies only when equivalent, preserving aliases. Identical entries with different stops/management/risk are not duplicate outcome tests. Partial trade overlap is not strategy duplication.
6. Publish expected raw combinations, invalid combinations, prior duplicates, within-study duplicates, unique configurations and completed count per model. Every expected configuration must receive a terminal classification such as evaluated, no trades, insufficient data or invalid, with the reason preserved. Missing-data cases are not successful account replays.
7. Run base execution/account evaluation for every unique valid configuration. Predeclare which execution stresses apply to every row and which are finalist diagnostics; never claim exhaustive stress coverage if only finalists receive it. Account-rule profiles are frozen study assumptions, not another hidden optimization axis.

An example of combinatorial growth: 8 independent axes with 5 choices each give 390,625 configurations for ONE model, before adding other dimensions. Twenty such grids give 7,812,500 rows. This is an illustration, not an estimated R4 count.

More combinations increase selection bias as well as computational demand. All trials must be counted; rankings need chronology, uncertainty and data-quality disclosures. The shared 2023-2025 history remains development data even when a rule is newly invented.

The earlier roughly six-minute elapsed run used a particular finite grid and parallel execution. R4 runtime must be estimated from its actual unique manifest and representative timed execution. Preserve checkpoints and provide user-run GitHub instructions once the workflow is implemented and validated. Do not promise six minutes, unlimited runtime or guaranteed profitability.

## Expansion to 31

R4-21..30 are paper-method adaptations. R4-31 contains ten A-J entry families under one fixed-target model, as specified in MODEL31_ENTRIES.md. Models 1-30 remain unchanged. Model 31 now includes IFVG, displacement, ordinary FVG retest, wick recovery, double test, VWAP reclaim and internal-box entries in addition to A-C. Count their actual applicable products separately; do not multiply irrelevant parameters across families. The high/low target is fixed from 09:30-09:44 bars, and all entries must execute strictly inside the range after 09:45. No outside-to-boundary branch is authorized by the clarified design.

Paper evidence, event counts and implementation readiness must be reported separately. Some variants change risk/execution selection rather than the directional signal; shared entries must be cached without treating distinct exits as duplicate outcomes. No exact unique count or runtime is claimed until the executable registry is frozen and checked.

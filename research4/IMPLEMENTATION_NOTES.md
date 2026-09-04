# R4 executable definitions and limits

Opening bars and all decision events are indexed in normalized minute-open ET time. A close signal at array index t executes no earlier than t+1. Signals use lagged daily ATR(14), prior-only same-clock estimates and no future-selected pivots. Normal NYSE cash sessions are the trading subset, not a claim that NYSE defines the CME calendar. Missing overnight features disable affected model signals; missing active trade paths stop account qualification.

The model mechanisms in CANDIDATES.md remain the registry's design comparison with actual R1-R3 source rules. R4-10/13/18/19/20/25/26 reuse ordinary ORB entry computation but have distinct management policies. No neutral OFF settings recover the old full strategies. Full settings, not names alone, determine cutoff/deadline aliases. Equal individual trades across models do not establish identical strategies; no claim of 31 independent edges is made.

Additional choices fixed before the full run:

- R4-21 uses trailing linearly weighted local-linear fits and observed delayed extrema. It never backdates a pivot or uses a centered future smoother.
- R4-22 uses prior-session same-clock mean/std and prior daily maximum CUSUM quantiles. Thresholds are research scores, not nominal false-alarm probabilities.
- R4-23 uses standardized opening return and opening-return times volume-surprise interaction in a ridge fit to completed prior sessions. Volume surprise uses prior mean/std. It forecasts a fixed opening-plus-horizon endpoint; the predicted remaining move must exceed conservative MNQ point costs. Exit cannot extend beyond that endpoint. Prior labels are next-open endpoint prices.
- R4-24 uses finite-sample-adjusted bipower variation, prior 60-session same-clock ranks, a later complete rebuilding block and frozen observed excursion clearance. No formal asymptotic jump-test significance is claimed.
- R4-25 compares adverse squared-return share and prior 60-session same-clock magnitude quantiles. Reductions require feasible whole contracts and never re-add.
- R4-26 uses Gaussian known observation variance after prior same-clock normalization, N(0,1) mean prior, and all possible within-session run lengths. Exit uses joint posterior mass on positive recent run lengths and an adverse mean; it excludes the constant reset mass. This is a specified BOCPD adaptation, not the paper's neural system.
- R4-27 uses a heteroskedasticity-adjusted small-lag variance-ratio score, scaled by its prior same-clock standard deviation. Two adjacent nonoverlapping blocks must change from negative to positive evidence before a later ORB.
- R4-28 uses close-confirmed directional-change events at two lagged-ATR amplitudes. Event availability is the reversal confirmation time, never the preceding extremum.
- R4-29 uses mean absolute return per notional turnover and a prior log-impact residual z-score. It is a proxy, not observed book impact.
- R4-30 uses two completed adjacent 15-minute blocks. Negative estimates are invalid, and premature direction breaks are canceled. Zero-event outcomes are retained.
- R4-31 uses original fixed opening boundaries as targets and checks strict inside-range entry, location, actual whole-contract feasibility, costs and minimum reward/risk at the executable open. FVG/IFVG and displacement are precisely defined OHLC patterns; they do not observe actual liquidity or participant intent.

Within a configured day/direction, ordinary ORB candidates keep the first qualifying close. Model-31 setup candidates can be canceled at execution and a later independent setup considered; no future best-entry selection occurs. Any simultaneous opposing model-31 confirmations cancel that timestamp. One actual entry episode per session is allowed. Partial exits/additions stay within that episode.

Accounting uses actual fees and unclipped gap losses. The prop profile is a frozen research assumption from the earlier studies, not a live firm-rule guarantee. No all-grid walk-forward selection, unseen-data validation or portfolio optimization is claimed in this release. Those are distinct future validation stages, not silently embedded performance promises.

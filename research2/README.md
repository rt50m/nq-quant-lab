# Research #2 — five ORB and five non-ORB hypotheses

Status: implementation verified locally; GitHub execution pending publication.
The frozen grid contains **568,296 configurations** across ten models and one control.

This is a finite, exhaustive development search, with a separate plain-ORB control.
Research #1 remains unchanged. Its recorded top three (C047761, C013131, C051005)
are historical comparison references, not directly comparable fresh replays.

## Evidence and model definitions

See [SOURCES.md](SOURCES.md) for original papers, affiliations and transfer limitations.
The model names describe our implementations, not proprietary fund strategies.

| Family | Frozen signal definition |
|---|---|
| ORB_BASE | Completed candle closes beyond completed opening range; benchmark |
| ORB_VWAP | ORB signal also beyond cumulative RTH typical-price VWAP by configured lagged-ATR buffer |
| ORB_RVOL | ORB with opening volume / previous 14 or 28 sessions' opening-volume mean above threshold |
| ORB_VOL | ORB gated on prior daily-return volatility relative to an expanding-history rolling quantile |
| ORB_GAP | ORB follows/fades overnight return, optionally conditional on prior RTH return sign |
| ORB_OPEN_TREND | ORB direction agrees with completed opening candle; optional body/range-strength gate |
| CLOSE_MOMENTUM | At 15:00/15:15/15:30, follow return from previous RTH close to last completed minute |
| NOISE_MOMENTUM | After 10:00, close outside time-of-day historical absolute-return bands and on same side of VWAP |
| GAP_REVERSAL | At specified morning time fade overnight return above threshold, optionally conditioned on prior RTH sign |
| OPEN_SHOCK_REVERSAL | Fade opening 5/15/30-minute move exceeding a fraction of lagged daily ATR |
| OVERNIGHT_DRIFT | Long at 02:00/02:30 ET, out at 03:00/04:00, optionally conditional on previous RTH selloff |

All signals enter at the **next minute's open** with adverse slippage. Two-bar
confirmation requires consecutive same-direction qualifying closes. Fixed-time signals
use the completed minute immediately preceding entry. Latest ORB/noise entry is 15:00.
One position and one trade per date; no re-entry, pyramiding or mixed NQ/MNQ positions.
Opening lengths are settings, not counted as independent research families.

The fifth ORB slot narrows the proposed generic trend filter to opening-direction
confirmation, which is explicitly present in the source paper. It does not invent an
institutional endorsement of arbitrary moving-average filters. VWAP+ORB is a synthesis
of two papers, not an exact replication of either.

## Finite search contract

[grid.json](grid.json) is the sole parameter registry. `manifest` enumerates its Cartesian
products and writes exact per-family counts, IDs and exclusions before evaluation.
Directions: both/long/short (overnight drift is long-only). Stops: 5/10/20% of prior
14-session daily ATR; targets: 1/1.5/3R or none; trailing: none or move to entry after a
completed candle reaches 1R; risk: $50/75/100/125/150/175/200/250/300. RTH time exits:
11:30/13:00/15:59. Close momentum exits 15:59; overnight drift uses its own morning exits.

The one-trade limit, fixed next-bar entry, ATR stop family, and grid endpoints are
deliberate boundaries. Touch entries, all conceivable stops, cross-family filter
combinations, re-entry and infinite continuous parameter choices are **not** covered.
Opening-range-opposite stops from Research #1 are not equivalent to this ATR grid.
Changing these boundaries creates a new version, rather than rewriting a completed study.

## Execution and prop-account model

Reference: LucidPro 50K **evaluation, DLL ON**, public rules checked September 4, 2026.
Starts $50,000, EOD trailing $2,000 floor capped at $50,100, $1,200 DLL and maximum
4 NQ or 40 MNQ. Our stricter personal daily limit is $1,000. Trading stops at 15:59 ET,
well before the regular 16:45 firm cutoff. Holiday/short cash sessions are excluded
in advance using the NYSE calendar; they remain in lagged daily-price history.
This restriction is intentional, not a claim that NYSE is the CME trading calendar.

The research does not simulate funded LucidScale, payouts, evaluation targets or
consistency qualification. Account outputs measure trading-risk paths for the named
reference only. DLL OFF and other firm products need their own versioned profiles.

Every configuration has an independent-strategy P&L stream and a separate account
path. Risk sizing includes round-trip commission and modeled exit slippage. Protective
levels use current account buffer and include a $25 margin above the hard loss floor.
Daily/account protection is evaluated during the trade. Gap losses are preserved;
no loss is capped after the event. Account replay stops after breach or an unknown path.
Only prior session closing equity advances the EOD floor; intraday unrealized gains
do not ratchet it. One trade per date makes daily-lockout/re-entry cancellation trivial.
Pending next-bar entries expire at their configuration's time exit; nothing carries over.

The bar open is processed first, then time exits, then stop/target touches. Both touched
inside a bar => stop first and explicit ambiguity count. Target limit fills never
receive favorable gap improvement. Trailing updates become active on the following
bar. A missing forced-exit quote is unresolved; no earlier/fabricated close is inserted.
Protective orders do not guarantee survival through a gap.

## Data and interpretation

Public Anooreplay NQ mirror pinned by commit; downloads are anonymous and hashed.
UTC timestamps are interpreted as minute-open timestamps and converted to America/New_York.
Raw validation checks duplicate conflicts, minute alignment, OHLC and finite values.
The study freezes 2023 through December 11, 2025, the mirror's last complete date; earlier rows
are feature warmup only. This is already-examined development data, **not pristine OOS**.
The mirror's file named December 12 contains only part of the preceding evening,
so December 12 is not represented as an evaluated trading session.
No 2026 data is searched. Independent exchange provenance, continuous-contract roll
treatment and NQ-price/MNQ-fill equivalence are still validation requirements.

Missing bars and insufficient lagged history can reduce eligible observations. Prepared
artifacts expose incomplete dates. Missing active-trade paths flag NEEDS_DATA, never
validated profitability. Days lost to data quality can bias a screen; inspecting the
coverage report and independent-data replay is required before promoting a finalist.

Historical comparison screen: $300 intended risk, >=80 trades, >=20 in 2024 and closed
P&L drawdown strictly above -$2,000, with no observed missing trade paths. Account path,
intrabar uncertainty, parameter stability and costs are reported separately. No winner
is selected by evaluation-pass frequency or payout optimization.

## Run and resume

Use Python 3.12 and [requirements.txt](requirements.txt).

```sh
python -m unittest discover -s research2 -p 'test_*.py' -v
python research2/run.py download --out data_r2
python research2/run.py prepare --data data_r2 --out prepared_r2
python research2/run.py shard --prepared prepared_r2 --out parts_r2 --index 0 --count 32
python research2/run.py aggregate --parts parts_r2 --prepared prepared_r2 --out results_r2
```

Shards use deterministic manifest-index modulo partitioning. Each periodically flushes
JSONL checkpoints; rerunning against the same directory resumes missing IDs. Code,
grid, data hash, shard assignment and smoke/full settings must match. Aggregation rejects
foreign versions and conflicting duplicates and only declares full completion when every
manifest ID is present. A partial/missing shard cannot produce a complete leaderboard.
Recovered runs must download the previous run's artifacts before rerunning shards.

GitHub's workflow first runs tests and an all-family smoke batch, then optionally runs
the full matrix. The full phase never runs if verification fails. Artifacts and compact
summaries allow occasional monitoring; no AI API calls are used by the backtest.

## Required work after development completion

Freeze finalists before independent/forward data. Audit neighbors, annual/monthly
stability, outlier concentration, doubled/tripled slippage, intrabar-sensitive trades,
account start dates and overlap with the existing shortlist. Distinguish model selection
from untouched testing, and retain the full number of tried configurations for
multiple-testing analysis. Grid completion is not strategy validation.

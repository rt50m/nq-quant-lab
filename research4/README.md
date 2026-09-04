# Research 4 preparation

Status: **NOT READY FOR FULL BACKTEST**. No Research 4 models have been executed. The first 30 selected designs remain unchanged; model 31 contains ten entry families. See CANDIDATES.md, MODEL31_ENTRIES.md and COVERAGE_CONTRACT.md.

The draft grid contains 5,065,092 raw parameter combinations, including 2,716,254 for model 31. These are raw finite products, not unique executable configurations. Semantic duplicates, incompatible settings and unavailable-data cases still need classification. Strategy implementations and execution validation remain pending. Do not treat the grid file or a successful preparation job as a completed engine.

## Timestamp issue and current interpretation

The frozen public mirror was previously interpreted as minute-open timestamps. A full raw-hash audit found no complete 18:00-09:29 overnight window under that interpretation (732 normal study sessions). In representative winter and summer observations, the dataset contains 18:01 as its first evening bar and a 17:00 bar at the maintenance boundary; the cash-open volume increase occurs at 09:31. This is strong evidence for close-stamped bars, but does not establish source semantics by itself.

Interpreting timestamps as candle closes produces 649 complete overnight windows and changes the 15-minute opening high or low on 279 development sessions. The raw data and earlier research remain unchanged. No earlier strategy profit has been recomputed or invalidated by this audit alone.

The [source import script](https://github.com/MeNameek/AnooReplay/blob/2628f7ac1da4e83591391889db426208a2985556/scripts/ingest.js) reads Dataset_NQ_1min_2022_2025.csv and converts ET timestamps to UTC without documenting bar labeling. Merely being divisible by 60 does not prove minute-open labeling.

The original source is now identified: [NQ Futures - 1min Bar 2022 2025](https://www.kaggle.com/datasets/tgtanalytics/nq-futures-1min-bar-2022-2025/data), uploader **tgtanalytics / TGT Analytics - Fernando**, version 1. All 1,048,462 cached mirror timestamp/OHLCV rows match the original CSV exactly. The CSV has 1,048,575 rows; the additional 113 are after the final cached UTC date, starting 2025-12-11 19:00 ET, beyond the research trading window. No unexplained row mismatch was found.

In the original CSV, all 764 zero-to-positive RTH VWAP initializations occur at 09:31 ET. This reinforces the close-stamp interpretation independently of the mirror's removed VWAP columns. See DATA_PROVENANCE.json for archive/CSV hashes and observed examples. The uploader still does not explicitly declare timestamp labeling, the original market-data vendor or the rollover method.

R4's explicit working policy for this frozen dataset is therefore **empirically inferred close stamps**. Normalize UTC timestamps by subtracting 60 seconds when indexing bar opens, while completed information becomes available at the original raw timestamp. Thus the 09:30-09:45 opening range uses raw-labeled 09:31 through 09:45 candles and is known at 09:45. Do not subtract another minute when ordering signals. Nine preparation/timestamp tests currently pass, including summer/winter offsets and information availability. This addresses the implementation decision without claiming exchange certification. Independent source confirmation remains a documented validation limitation.

## Optional GitHub preparation audit

Open Actions > **Research 004 - preparation audit only** > Run workflow > main > Run workflow. This downloads the same frozen public mirror, verifies raw hashes, checks the 31-model menus and produces `r4-preparation-only` with the coverage audit, normalized RTH/full-overnight arrays and explicit readiness status. It does not backtest any model, rerun an earlier grid or call an AI API. A green check means the audit completed; read `readiness.json`, which currently says NOT_READY_FOR_BACKTEST.

The full research workflow and its launch instructions cannot be supplied until the implementations, policy deduplication, execution tests, checkpoint recovery and aggregation checks are complete. The preparation workflow has no custom timeout; platform job limits still apply. This small audit can be rerun, but the unimplemented full search has no checkpoint guarantees yet.

## Local reproduction

From the repository root, install research3/requirements.txt, then run:

```text
python -m unittest discover -s research4 -p 'test_*.py' -v
python research3/run.py download --out data_r4
python research4/prepare.py --data data_r4 --out preparation_r4
```

The preparation report preserves original data hashes and reports the two timing interpretations separately. The normalized output explicitly records the close-stamp inference. It never fills missing observations or replaces the approved overnight models to manufacture complete coverage.

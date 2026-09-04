# Research 4 preparation

Status: **NOT READY FOR FULL BACKTEST**. No Research 4 models have been executed. The first 30 selected designs remain unchanged; model 31 contains ten entry families. See CANDIDATES.md, MODEL31_ENTRIES.md and COVERAGE_CONTRACT.md.

The draft grid contains 5,065,092 raw parameter combinations, including 2,716,254 for model 31. These are raw finite products, not unique executable configurations. Semantic duplicates, incompatible settings and unavailable-data cases still need classification. Strategy implementations and execution validation remain pending. Do not treat the grid file or a successful preparation job as a completed engine.

## Concrete timestamp blocker found during preparation

The frozen public mirror was previously interpreted as minute-open timestamps. A full raw-hash audit found no complete 18:00-09:29 overnight window under that interpretation (732 normal study sessions). In representative winter and summer observations, the dataset contains 18:01 as its first evening bar and a 17:00 bar at the maintenance boundary; the cash-open volume increase occurs at 09:31. This is strong evidence for close-stamped bars, but does not establish source semantics by itself.

Interpreting timestamps as candle closes would produce 649 complete overnight windows and change the 15-minute opening high or low on 279 sessions. This alternative is a diagnostic only. The raw data and earlier research remain unchanged. No earlier strategy profit has been recomputed or invalidated by this audit alone.

The [source import script](https://github.com/MeNameek/AnooReplay/blob/2628f7ac1da4e83591391889db426208a2985556/scripts/ingest.js) reads Dataset_NQ_1min_2022_2025.csv, converts ET timestamps to UTC, and does not explicitly say whether timestamps mark bar opens or closes. Confirm the original feed/export convention or match sample candles to a trusted feed before fixing a normalization policy. Merely being divisible by 60 does not prove minute-open labeling.

## Optional GitHub preparation audit

Open Actions > **Research 004 - preparation audit only** > Run workflow > main > Run workflow. This downloads the same frozen public mirror, verifies raw hashes, checks the 31-model menus and produces `r4-preparation-only` with the coverage audit and explicit readiness status. It does not backtest any model, rerun an earlier grid or call an AI API. A green check means the audit completed; read `readiness.json`, which currently says NOT_READY_FOR_BACKTEST.

The full research workflow and its launch instructions cannot be supplied until the implementations, timestamp handling, policy deduplication, execution tests, checkpoint recovery and aggregation checks are complete. The preparation workflow has no custom timeout; platform job limits still apply. This small audit can be rerun, but the unimplemented full search has no checkpoint guarantees yet.

## Local reproduction

From the repository root, install research3/requirements.txt, then run:

```text
python -m unittest discover -s research4 -p 'test_*.py' -v
python research3/run.py download --out data_r4
python research4/prepare.py --data data_r4 --out preparation_r4
```

The preparation report preserves original data hashes and reports the two timing interpretations separately. Do not silently shift timestamps or replace the approved overnight models to manufacture complete coverage.

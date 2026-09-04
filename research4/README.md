# Research 4 — full 31-model development search

The implementation is prepared for manual GitHub execution. No full R4 search has been run as part of setup. The 23 local tests, all-family real-data smoke/causality checks, and reduced all-model interruption/resume/aggregation fixture passed. Those checks are not research results or a guarantee of profitable strategies.

## Start the full search

1. Open [Research 004 - 31 models](https://github.com/rt50m/nq-quant-lab/actions/workflows/run_research_004.yml).
2. Click **Run workflow**, keep branch **main**, and check **Run all 31 models and automatic analysis after verification**.
3. Leave the previous run ID blank on your first run and click **Run workflow**.

GitHub verifies the code/data, runs 64 shards (up to eight concurrently), and produces **r4-results**. The completed report must show **4,399,758 / 4,399,758** configurations. The artifact includes all configuration rows, the best historical-profit and qualifying prop-account variant for each model, annual statistics, and higher-cost diagnostics plus daily paths for finalists. No AI API calls or monitoring are part of this workflow. You can close your laptop after dispatch.

## Coverage

There are 5,065,092 raw products in the declared grid and 4,399,758 unique configurations after collapsing 665,334 equivalent cutoff/deadline settings. This includes 2,716,254 model-31 configurations across ten entry families. All compatible declared settings are evaluated; no performance-based early stopping or old benchmark searches are included. This is a finite study, not every conceivable strategy or setting. Candidate designs are in CANDIDATES.md and MODEL31_ENTRIES.md; the executable grid is grid.json.

Some parameter settings produce no trades. Their rows remain visible as NO_TRADES; missing active paths are NEEDS_DATA. A failed prop screen has no qualifying variant. Highest historical profit is a development selection statistic, not an independently validated edge. Higher-cost stress (0.5 and 1 point per side) is finalist-only, not a claim of all-row stress coverage. This release does not estimate evaluation-pass or payout probabilities or claim a pristine holdout.

## Execution and source details

Whole NQ-first/MNQ-fallback sizing, per-contract fees, daily protection, continuous end-of-day trailing account floor and hard 15:59 ET liquidation are modeled. No overnight positions. Resting limits require one-tick trade-through; target-before-fill ambiguity is treated conservatively and prevents a resting-limit prop qualification. Stops and targets are tick-rounded. Unknown minute ordering remains a limitation of OHLCV.

DATA_PROVENANCE.json records the exact Kaggle source, original CSV/archive hashes and the full mirror comparison. R4 uses empirically inferred close-stamped bars: normalized open time is raw UTC minus 60 seconds and observation availability remains raw UTC. All 1,048,462 cached mirror rows match Kaggle version 1 exactly. Original vendor, rollover treatment and explicit uploader labeling remain unverified. R1-R3 code/results and raw timestamps are unchanged.

Operational definitions are documented in IMPLEMENTATION_NOTES.md. These strategies adapt paper methods; they are not replications of proprietary fund systems or proven NQ edges.

## Recovery

Each shard saves partial groups atomically and uploads checkpoints after each of six 40-minute compute windows. Code, data, shard assignment and exact configuration identity must match on resume. If a run stops incomplete, launch the same workflow on the same code and paste its numeric run ID into **Optional previous Research 004 run ID with matching code and data**. Completed groups are reused. Do not select different code when resuming.

Runner or upload failures can lose work since the last successful artifact upload; zero loss under every interruption is not guaranteed. The search job has a 350-minute ceiling to leave upload time before GitHub's runner limit. Final results retain for 90 days; checkpoints retain for 30. Download before expiration. The earlier preparation-only workflow is not the full search.

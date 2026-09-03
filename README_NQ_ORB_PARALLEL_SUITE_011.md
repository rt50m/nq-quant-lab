# NQ ORB Parallel Research Suite 011

This is the resumable/parallel replacement for Suite 010.

## What stays identical

The research universe remains the same **55,260 exhaustive configurations** across the same 10 ORB model families, same $300 primary risk, same NQ/MNQ sizing, same stops/targets/time exits, same slippage/commission assumptions, and same TradingView-style statistics.

Suite 011 is an infrastructure rewrite, not a smaller search.

## What changes

### 1. Shared preparation
One job loads the NQ data, builds daily/ORB features, trains the shared ML/TR gates, creates the exact 55,260-row manifest, and writes a reusable compressed prepared-state artifact.

### 2. 62 deterministic shard jobs
Each model is divided into small shards of roughly 540–1,080 configs. Shards can run in parallel. Each shard writes a disk checkpoint every **25 configurations**.

### 3. Failure/cancellation recovery
Each shard uploads its own artifact. Completed shard artifacts survive even if other jobs fail or the workflow is later cancelled.

If a shard itself is interrupted, its `if: always()` artifact step is designed to upload the latest checkpoint available on that runner. On GitHub, a hard infrastructure failure can still prevent a final upload, which is why shards are deliberately small.

Use GitHub's **re-run failed jobs** rather than re-running the entire workflow. Successful shards remain successful and do not need to be recomputed.

### 4. Progressive model results
Every ORB family has its own aggregation job. As soon as that model's shards finish, GitHub publishes:

`orb011-model-orbXX-complete`

That artifact includes:
- every recovered configuration for the model
- exact completion status/count
- top 100 and top 10 configurations
- top-3 full trade logs
- top-3 equity curves
- monthly/yearly statistics
- $50/$75/$100/$125/$150/$175/$200/$250/$300 risk grid
- prop replay
- TradingView-style model summary

You do **not** need to wait for all 10 models to finish to inspect a completed model.

### 5. Final aggregation
When the ten model aggregators finish, `nq-orb-parallel-suite-011-final` merges the exhaustive search into one overall leaderboard.

## Shard layout

| Model | Configs | Shards | Approx configs/shard |
|---|---:|---:|---:|
| ORB01 | 1,080 | 2 | 540 |
| ORB02 | 2,160 | 3 | 720 |
| ORB03 | 2,700 | 3 | 900 |
| ORB04 | 2,700 | 3 | 900 |
| ORB05 | 6,480 | 7 | 926 |
| ORB06 | 9,720 | 10 | 972 |
| ORB07 | 4,500 | 5 | 900 |
| ORB08 | 16,200 | 18 | 900 |
| ORB09 | 3,240 | 4 | 810 |
| ORB10 | 6,480 | 7 | 926 |

Total: **55,260 configs / 62 shard jobs**.

## Causality

Preparation runs the original Suite-010 audit plus additional Suite-011 checks:
- exact manifest and per-model counts
- lagged previous-session fields
- future-bar mutation tests proving bars after an ORB cannot alter the completed opening range
- post-open mutation tests for state variables intended to depend only on prior information

The search does not begin unless the enhanced audit passes.

## Important

The historical data source is still the same public NQ one-minute mirror used in Suite 010. This architecture solves compute/recovery problems; it does not upgrade the underlying market-data provenance.

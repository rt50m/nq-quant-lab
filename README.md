# NQ Quant Lab

Research repository for systematic NQ futures strategy discovery, stress testing, and prop-firm-compatible model development.

**Current focus: Research #2 — five ORB and five non-ORB hypotheses, plus a plain-ORB control.**

See [Research #2](research2/README.md) for the 568,296-configuration finite grid,
paper/fidelity register, execution controls, verification and workflow. Research #2
uses a separate engine; Research #1 files and recorded results remain unchanged.

## Start Research #2 on GitHub

1. Open **Actions → Research 002 - ORB and non-ORB → Run workflow**.
2. Select branch **main** and check **Run the entire frozen grid after verification**.
3. Leave **Optional prior full run ID** blank for the first run, then click **Run workflow**.

GitHub runs verification, 32 search shards (up to eight concurrently), and aggregation.
No local process or open Codex session is needed. No AI API calls or Codex monitoring
are part of the workflow. The full search runs only when manually requested.
When it finishes, share the run link for review. Download the **r2-results** artifact;
it contains the coverage report, all results and development rankings and expires
after 90 days. A complete result must report **568,296 / 568,296**, not just a green
verification job. Failed or partial runs retain checkpoints for 30 days; share the
failed run link before retrying so recovery can reuse matching checkpoints.

**Research #1 reference:**

- **55,260 / 55,260 configurations completed**, as recorded in the final research handover.
- NQ one-minute OHLCV; primary evaluated period 2023–2025.
- Current mechanical screen: $300 intended risk, minimum trade counts, and historical drawdown strictly below $2,000, then profit ranking. ORB01 uses a lower-risk exception.
- Preferred candidates emphasize stability and execution integrity. Evaluation pass rates and payout optimization do not drive the current shortlist.
- Research #1 is a discovery screen, **not final strategy selection**.

Start with **[RESEARCH_TRACKER.md](RESEARCH_TRACKER.md)** for the canonical model registry, settings, results, fidelity labels, completed stress findings, decisions, artifact references, and next experiments.

The provisional clean shortlist is **ORB09 C047761, ORB05 C013131, and ORB10 C051005**. **ORB04 remains NEEDS-DATA** because one-minute candles cannot resolve its ambiguous first-entry ordering; its original performance is not accepted as validated.

## Active research stack

- [Suite 010 guide](README_NQ_ORB_SUITE_010.md) and [backtest source](nq_orb_research_suite_010.py)
- [Suite 011 guide](README_NQ_ORB_PARALLEL_SUITE_011.md) and [parallel runner](nq_orb_parallel_suite_011.py)
- Workflows: [Suite 010](.github/workflows/run_nq_orb_research_suite_010.yml), [Suite 011](.github/workflows/run_nq_orb_parallel_suite_011.yml), [Recovery 012](.github/workflows/run_nq_orb_recovery_012.yml)
- Configurations: [Suite 010](orb_suite_config.json), [Suite 011](orb_parallel_suite_011_config.json)
- [Source/fidelity notes](source_notes.json) and [historical Lucid 50K reference](lucid_50k_reference.json)

The next research priorities are ORB04 tick/sub-minute validation and a full execution-integrity and robustness audit. The tracker records later walk-forward, cost, sequence-risk, prop-account, portfolio/hedge, and new-family research.

The repository intentionally keeps the active research surface small. Superseded experiments remain recoverable through Git history.

# NQ Quant Lab

Research repository for systematic NQ futures strategy discovery, stress testing, and prop-firm-compatible model development.

**Current focus: Research #1 — exhaustive 10-family Opening Range Breakout screen.**

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

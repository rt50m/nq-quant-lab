# NQ Quant Lab

Research repository for systematic NQ futures strategy discovery, stress testing, and prop-firm-compatible model development.

## Current focus

**Research #1: exhaustive 10-family Opening Range Breakout (ORB) screen**

- **55,260 / 55,260 configurations completed**
- NQ 1-minute data, 2023–2025 research period
- LucidPro 50K drawdown compatibility considered during model selection
- Current work emphasizes execution integrity, robustness, and avoiding false edges before expanding into Research #2+

## Start here

See **`RESEARCH_TRACKER.md`** for:

- best current variant from every model,
- current clean shortlist,
- Model 4 tick-data blocker,
- known execution / research-fidelity caveats,
- completed stress tests,
- next research queue,
- decision history.

## Core suite

- `nq_orb_research_suite_010.py`
- `nq_orb_parallel_suite_011.py`
- `.github/workflows/run_nq_orb_research_suite_010.yml`
- `.github/workflows/run_nq_orb_parallel_suite_011.yml`
- `.github/workflows/run_nq_orb_recovery_012.yml`
- `orb_suite_config.json`
- `orb_parallel_suite_011_config.json`
- `source_notes.json`
- `lucid_50k_reference.json`

This repository intentionally keeps the active research surface small. Superseded pre-ORB experiments remain recoverable through Git history rather than cluttering the working tree.

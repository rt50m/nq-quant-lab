# NQ Alpha Factory 002 — Causality-Hardened

Factory 001 is invalidated and is NOT used as a seed. Factory 002 reruns the search from scratch.

## Search scale

- 300,000 random rule attempts
- 4,000-member evolutionary population × 18 generations
- 5/15/30/60-minute horizons
- Ridge, HistGradientBoosting and ExtraTrees ML models
- 0.5/1/2/3-point cost stresses
- day-clustered statistics
- locked-block bootstrap and parameter-neighborhood tests
- next-bar-open execution + real stop simulation
- eight Lucid-style risk profiles ($50-$250 risk)

## Anti-leakage gates

The search is aborted before hypothesis generation unless all causality tests pass.

- RTH open unavailable before 09:30 ET.
- 15-minute ORB unavailable before 09:45 ET.
- RTH VWAP state is NaN outside RTH.
- Previous levels use only the previous completed RTH session.
- Same-minute volume seasonality uses prior sessions only.
- Forward labels must be exactly H minutes later, same ET date, before 16:45 ET.
- A future-mutation invariance audit changes all future prices/volume and recomputes features. Any feature at the signal timestamp that changes causes the entire run to fail.

## Validation firewall

- 2023: discovery/search
- Jan-Jun 2024: GATE / model selection
- Jul-Dec 2024: LOCKED validation, excluded from ranking
- 2025: already-seen secondary evidence only

The locked block is evaluated only after candidates are chosen using 2023 + 2024 H1.

## Prop risk profiles

$50/$200, $75/$300, $100/$400, $125/$500, $150/$600, $175/$700, $200/$800, $250/$1,000.

Both DLL-on and DLL-off are reported.

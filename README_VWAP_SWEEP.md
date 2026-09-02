# VWAP Research Sweep 001

This sweep tests ~400 common systematic VWAP variants across six families:

1. VWAP cross / reclaim
2. Trend pullback / rejection
3. ATR-normalized VWAP deviation mean reversion
4. ATR-normalized VWAP deviation breakout
5. VWAP slope momentum
6. Dual-anchor VWAP alignment

Anchors:
- CME-style 18:00 ET daily anchor
- 09:30 ET daily anchor

Research discipline:
- 2023 = discovery
- 2024 = validation
- 2025 = final out-of-sample
- 2025 is NOT used to rank variants

All variants use the same execution assumptions for screening:
- next-bar-open entry
- 1 ATR(14) stop
- 1R target
- 60-minute timeout
- 0.50 NQ points round-trip friction
- stop-first assumption when stop and target are both touched in the same minute

This is a broad factor screen, not a final production strategy.

# Research 7 — Multi-Strategy Hedge / Portfolio Optimization

R7 does **not** invent another entry family. It tests whether the project’s best serious survivors can be combined into the actual design objective: **at least $50,000 net across the 2023-2025 development interval while conservative combined intratrade MDD remains strictly under $2,000**.

## Frozen candidate set

- R6.1 Stable Impulse Continuation
- R1 ORB09 C047761
- R1 ORB05 C013131
- R1 ORB10 C051005
- R1 ORB02 C002514
- R1 ORB03 C003740
- R6 Compression Breakout
- R6 VWAP Trend Reclaim
- R6 Trend Pullback
- R6 Rolling Breakout

ORB04 is excluded because one-minute data cannot resolve its first-touch ordering. Tiny-sample R6 jackpot configurations are excluded.

## Critical common-engine rule

Older R1 rules are replayed on the same **R4 close-stamp-normalized minute arrays** used by R6/R6.1. R7 therefore does not blindly combine historical equity curves produced under incompatible timestamp semantics. R1’s old headline results are retained only as provenance; the common-engine replay is what enters R7.

R6 and R6.1 published sizing must regress exactly before the sleeve artifact is accepted.

## Sizing / hedge search

Each strategy can be OFF, a fixed MNQ quantity, a fixed NQ quantity, or a fixed-dollar-risk sleeve. The portfolio search chooses one sizing option per strategy. Exact finalists enforce a maximum simultaneous exposure of 40 MNQ-equivalents (4 NQ-equivalents).

The search reports two leaderboards:

1. **Disciplined:** portfolio allocation is ranked using 2023+2024 only, then frozen into 2025.
2. **Oracle upper bound:** uses the full development interval only to answer whether the frozen strategy set is mathematically capable of the target.

2025 is not pristine OOS because it has been repeatedly inspected in prior research.

## Conservative combined MDD

At every one-minute bar, each open sleeve is marked at its own adverse liquidation extreme and the sleeves are summed before drawdown is measured. Opposing long/short sleeves can therefore be treated more harshly than their true synchronized tick path. This is intentional: one-minute OHLC cannot prove which intrabar extremes occurred together.

## Result standards

`PASS_SCALE` requires >= $50k net, MDD > -$2k, and <=40 MNQ-equivalent simultaneous exposure.

`PROP_STRICT` also requires worst day > -$1,200.

`CREDIBLE_SCALE` additionally requires at least two active strategies, adequate trade count in every year, every year profitable, no year >60% of total profit, and no one sleeve >70% of portfolio profit.

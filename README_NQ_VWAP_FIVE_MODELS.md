# NQ VWAP Five-Model Replication Suite

Runs all five research models in one GitHub Actions job against the same NQ 1-minute dataset.

## Models

A. Noise-area momentum + VWAP confirmation  
B. Simple RTH VWAP flip / trend  
C. Noise-area entry + VWAP exit engine  
D. VWAP exhaustion + ADX rollover mean reversion  
E. NQ ORB break/retest + dual VWAP regime  

## Research window

2023-2025 NQ 1-minute bars.

## Standardized prop compatibility layer

- Intraday only
- Hard EOD flattening
- No averaging down / martingale
- Bounded per-trade risk
- NQ -> MNQ scaling if one NQ contract exceeds risk budget
- 0.50 NQ point round-trip friction stress
- Default allowed drawdown used for sizing: $2,500
- Per-trade risk budget: 6% of allowed drawdown
- Max three trades per day where the model supports multiple entries
- Daily kill threshold: -2R

The prop layer is generic. Actual firm rules vary and must be checked separately before live use.

## Fidelity

Models A/B are closest to the published mechanisms. C is a frozen exit-engine variant. D and E are research reconstructions because the public sources do not specify every production parameter needed for exact reproduction.

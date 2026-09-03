# NQ Institutional Paper Suite 003

This suite runs all five NQ/MNQ-specific research families in one GitHub Actions job.

## Five model families

A. Baltussen et al. — NQ last-half-hour market intraday momentum  
B. Rosa — threshold-gated overnight return -> last-half-hour momentum  
C. Yu, Rentzler & Wolf — previous-day / overnight conditional NQ regression  
D. Mesfin — MNQ RTH Confluence positive control (GMM reconstruction)  
E. Mesfin — MNQ London R0 -> R2 positive control (GMM reconstruction)  

## Research discipline

Paper-mechanism results are kept separate from the prop wrapper.

Models C, D and E are explicitly marked as reconstructions where public sources do not reveal enough implementation detail. The code does not label them exact replications.

2025 is not described as untouched out-of-sample because this project has already inspected 2025 results in earlier research.

## Prop risk profiles

Every underlying trade is replayed under:

| Profile | Risk/trade | Personal daily stop |
|---|---:|---:|
| Very conservative | $50 | $200 |
| Conservative | $75 | $300 |
| Balanced | $100 | $400 |
| Balanced+ | $125 | $500 |
| Aggressive | $150 | $600 |
| Aggressive+ | $175 | $700 |
| High aggression | $200 | $800 |
| Stress test | $250 | $1,000 |

Both LucidPro DLL-ON and DLL-OFF cases are reported.

## LucidPro 50K reference encoded

- $50,000 starting balance
- $3,000 profit target
- $2,000 EOD-trailing Max Loss Limit
- $1,200 DLL when enabled
- 4 NQ or 40 MNQ maximum size
- MLL locks at $50,100
- NQ commission $1.75/side
- MNQ commission $0.50/side
- 1.0 NQ-point round-trip slippage stress in the prop wrapper

## Outputs

- paper_pure_trades.csv
- paper_pure_summary.csv
- prop_wrapped_trades_all_profiles.csv
- prop_profile_summary.csv
- prop_historical_start_replays.csv
- best_prop_profiles_per_variant.csv
- model_fidelity.csv
- summary.md

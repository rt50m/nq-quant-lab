# Research #2 evidence register

Checked 2026-09-04. Evidence supports research hypotheses, not the profitability of
our NQ implementation. No claim that these are proprietary institutional strategies.

| Source | Provenance | Encoded use and limits |
|---|---|---|
| [Zarattini, Barbon & Aziz, A Profitable Day Trading Strategy for the U.S. Equity Market](https://concretumgroup.com/wp-content/uploads/2026/02/A-Profitable-Day-Trading-Strategy-For-The-U.S.-Equity-Market.pdf) | Concretum Research; University of St. Gallen/Swiss Finance Institute; Peak Capital/Bear Bull Traders. Working paper, first version 2024. | Opening range, opening-direction rule, relative volume and ATR stops motivate BASE/RVOL/OPEN_TREND. Paper uses a cross-section of US stocks and stocks-in-play selection. Single-contract NQ filters, strength gates and parameter grid are our adaptations. |
| [Zarattini & Aziz, Volume Weighted Average Price: The Holy Grail for Day Trading Systems](https://concretumgroup.com/wp-content/uploads/2026/02/Volume-Weighted-Average-Price.pdf) | Practitioner working paper, Concretum/Peak Capital. The title is the authors' wording, not our endorsement. | Directional VWAP trend logic motivates the ORB_VWAP synthesis. Source tests QQQ/TQQQ, not ORB+NQ. Typical-price bar VWAP approximates transaction VWAP; buffer settings are new hypotheses. |
| [Lundstrom, Day Trading Returns Across Volatility States](https://www.econ.umu.se/ueslpnr/ues861.pdf) | Umea University working paper, revised 2017; also IFTA Journal 2019. Academic/practitioner research, not major-fund authorship. | Conditional ORB performance in crude oil/S&P futures motivates ORB_VOL. Our lagged close-return standard deviation and prior rolling quantiles are a causal reconstruction; not certified identical state classification. |
| [Yu, Rentzler & Wolf, Nasdaq-100 Index Futures: Intraday Momentum or Reversal?](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=712168) | Academic research, 2005. Direct Nasdaq-100 futures relevance. Author abstract accessible; full specification was not accessible during this implementation. | Prior-day and overnight conditional relationships motivate ORB_GAP/GAP_REVERSAL. Sign gates and thresholds replace the paper's regression specification; these are mechanism reconstructions. They share economic exposure and are not assumed independent. |
| [Baltussen, Da, Lammers & Martens, Hedging Demand and Market Intraday Momentum](https://academicweb.nd.edu/~zda/intramom.pdf) | Journal of Financial Economics 142 (2021), 377-403. Erasmus/Notre Dame and **Robeco Asset Management** affiliations. | CLOSE_MOMENTUM follows previous-close-to-entry return. Source studies 62 futures, centered on the final half hour. Earlier 15:00/15:15 entries, thresholds, stops and one-minute-before-cash-close exits are explicit adaptations. No options gamma data or proprietary positioning is inferred. |
| [Zarattini, Aziz & Barbon, Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)](https://concretumgroup.com/wp-content/uploads/2026/02/Beat-the-Market.pdf) | Concretum/academic/practitioner working paper. | NOISE_MOMENTUM uses previous-session mean absolute moves at each clock minute, gap-adjusted bounds and VWAP direction. Fixed risk, one trade per day, ATR protective stops, starting after 10:00 and our exits differ from the source's repeated trades/dynamic sizing. |
| [Grant, Wolf & Yu, Intraday Price Reversals in the US Stock Index Futures Market: A 15-Year Study](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=689282) | Journal of Banking & Finance 29 (2005), 1311-1327. Academic. Abstract available; complete methodology remains to be independently reproduced. | OPEN_SHOCK_REVERSAL investigates the opening-reversal mechanism. Our 5/15/30-minute ATR-normalized shocks are a new specification. Transaction costs weaken the original findings; this is a falsification candidate, not established net alpha. |
| [Boyarchenko, Larsen & Whelan, The Overnight Drift](https://www.newyorkfed.org/research/staff_reports/sr917) | New York Fed Staff Report 917, revised August 2022. Central-bank research, not a hedge-fund paper. | OVERNIGHT_DRIFT tests the 02:00-03:00 ET window with adjacent time variations and previous-return filters. Source is S&P futures, NQ is a transfer. Fixed ET windows do not track every European daylight-saving mismatch; no dealer inventory data is fabricated. |
| [Bailey, Borwein, Lopez de Prado & Zhu, The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) | Academic/institutional methodological research; Lopez de Prado affiliated with Guggenheim Partners in the paper. | Motivates retaining all trials, avoiding isolated historical winners and separating selection from validation. This version does not claim to have completed PBO/CSCV analysis. |

## Account reference sources

The reference is specifically LucidPro 50K evaluation with DLL ON. It does not
automatically describe the user's purchased account or a different provider.

- [Drawdown](https://support.lucidtrading.com/en/articles/12890136-lucidpro-drawdown): EOD trailing floor, $2,000 allowance, $50,100 locked floor.
- [Daily loss](https://support.lucidtrading.com/en/articles/12890122-lucidpro-daily-loss-limit): $1,200 evaluation DLL; funded LucidScale differs and is outside v1.
- [Customization](https://support.lucidtrading.com/en/articles/16226068-lucidpro-customization): DLL ON/OFF are separate account choices.
- [Account position limits](https://support.lucidtrading.com/en/articles/12890069-lucidpro-funded-account): 4 mini or 40 micro reference. Research uses this cap conservatively.
- [Allowed times](https://support.lucidtrading.com/en/articles/11404729-allowed-trading-times): 16:45 normal flat deadline, 18:00 reopen, holiday closures override.
- [Automated trading](https://support.lucidtrading.com/en/articles/11404728-other-trading-activities): permitted subject to all trading rules. This backtest is not live automation.

One-minute research cannot certify venue execution, microscalping-duration compliance,
or discretionary conduct rules. Subminute exits can occur inside a candle; finalists
with such trades require transaction-level review. Trading-risk controls and full
contractual compliance are separate conclusions.

## Data source

[AnooReplay NQ mirror](https://github.com/MeNameek/AnooReplay/tree/2628f7ac1da4e83591391889db426208a2985556/public/data/NQ), pinned at
`2628f7ac1da4e83591391889db426208a2985556`. Retain file hashes and snapshot identity.
The mirror is public, but independent exchange provenance, redistribution rights and
roll adjustments are not established here. Do not republish raw price files with code.

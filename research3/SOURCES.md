# Research #3 literature register

As of 4 September 2026. **35 research works and 2 official bank methodologies.** Conference abstracts, working papers and peer-reviewed articles are distinguished below. Working and published versions of the same work count once. Search results unrelated to the task, trading advertisements and unverified performance posts do not count.

This is a screened register, not a claim that all full texts were accessible or every result was independently reproduced. Access depth is recorded for each item. Selection means a research hypothesis deserves testing, never that an NQ edge has been established.

The selected ten and their original NQ specifications are in [RESEARCH_PLAN.md](RESEARCH_PLAN.md). Machine-readable copies: [CSV](source_register.csv), [JSON](source_register.json).

## P01 — Nasdaq-100 Index Futures: Intraday Momentum or Reversal?

Yu; Rentzler; Wolf · 2005 · Academic; Journal of Investment Management / author SSRN record

- Market: NQ futures
- Access: Author abstract
- Decision: **SELECT**

Prior-session and overnight returns interact with return signs and calendar conditions. Exact full regression specification was not accessible; R3 uses an explicitly new causal reconstruction. R1/R2 used sign filters instead. [Primary source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=712168).

## P02 — Assessing the Profitability of Timely Opening Range Breakout on Index Futures Markets

Tsai et al. · 2019 · IEEE Access

- Market: Includes Nasdaq futures
- Access: Primary conference predecessor full-text search and published DOI metadata
- Decision: **EXISTING**

Already underlies R1 ORB04. A different entry sequence can be studied, but this does not repair unresolved first-touch ordering or validate a retest strategy. [Primary source](https://doi.org/10.1109/ACCESS.2019.2899177).

## P03 — Assessing the profitability of intraday opening range breakout strategies

Holmberg; Lonnbark; Lundstrom · 2013 · Finance Research Letters

- Market: Crude-oil futures
- Access: Publisher abstract and methodology excerpts
- Decision: **EXISTING**

Statistical thresholds and contraction/expansion rationale. Original findings are time-dependent; not direct NQ evidence. R1 ORB06 already reconstructs this family. [Primary source](https://www.sciencedirect.com/science/article/pii/S1544612312000438).

## P04 — Day Trading Returns Across Volatility States

Lundstrom · 2017 revision · Umea University working paper; later IFTA publication

- Market: S&P 500 and crude-oil futures
- Access: Author-institution PDF abstract
- Decision: **EXISTING**

Volatility conditions matter for ORB. Does not establish that any particular observable opening-range filter predicts profit. R1/R2 already test volatility gating. [Primary source](https://www.econ.umu.se/ueslpnr/ues861.pdf).

## P05 — Evolutionary ORB-based model with protective closing strategies

Wu; Syu; Lin; Ho · 2021 · Knowledge-Based Systems

- Market: Taiwan futures
- Access: Bibliographic record; full publisher text unavailable
- Decision: **EXISTING**

Existing R1 ORB07 source. Genetic search is an optimization technique, not an additional economic edge. No new model slot. [Primary source](https://doi.org/10.1016/j.knosys.2021.106769).

## P06 — Neural Network-Based ORB Strategies for Threshold Classification on Taiwan Futures Market

Chen; Syu; Ho · 2020 · IEEE SMC conference

- Market: Taiwan futures
- Access: IEEE presentation record and conference contents
- Decision: **EXISTING**

Existing R1 ORB08 source. Metadata reviewed; full method not newly verified. Neural thresholds do not count as a newly discovered mechanism. [Primary source](https://resourcecenter.smcs.ieee.org/conferences/smc-2020/smcs2020vid42).

## P07 — Enhancing Opening Range Breakout Strategies with LSTM-Based True Range Prediction

Wu et al. · 2026 · ACIIDS conference author presentation/abstract

- Market: ES futures
- Access: Author conference abstract; not full paper
- Decision: **EXISTING**

Predictive volatility improves a threshold strategy in the authors' study. Future-TR oracle results are not executable. R1 ORB09 uses a gradient-boosting surrogate, not the source LSTM. [Primary source](https://easychair.org/smart-slide/slide/Q2fW2).

## P08 — Market Intraday Momentum

Gao; Han; Li; Zhou · 2018 · Journal of Financial Economics

- Market: SPY and other equity ETFs
- Access: Author SSRN abstract and institutional publication record
- Decision: **SELECT**

First-half-hour return measured from the prior close predicts the final half-hour in the source sample. NQ transfer must be tested; opening-only return is a separate ablation. [Primary source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866).

## P09 — Hedging Demand and Market Intraday Momentum

Baltussen; Da; Lammers; Martens · 2021 · Journal of Financial Economics; Robeco / Erasmus / Notre Dame

- Market: 62 futures, including NQ
- Access: Full author-hosted PDF downloaded; relevant methods inspected
- Decision: **BENCHMARK**

Direct futures evidence for late-day momentum. R2 CLOSE_MOMENTUM already uses prior-close-to-entry return, so repeating that signal gets no new discovery slot. Dealer-position data are not available. [Primary source](https://academicweb.nd.edu/~zda/intramom.pdf).

## P10 — Understanding Intraday Momentum Strategies

Rosa · 2022 · Journal of Futures Markets

- Market: Includes S&P 500, Nasdaq 100 and DJIA futures
- Access: Publisher abstract, data statement and author publication record; full model unavailable
- Decision: **SELECT**

Unconditional overnight-to-close predictability disappears out of sample in the paper. Regime and signal-strength conditioning motivate a competing model, not a blanket positive result. Our filtered-state implementation is an adaptation. [Primary source](https://onlinelibrary.wiley.com/doi/10.1002/fut.22375).

## P11 — Profitability of Technical Stock Trading: Has It Moved from Daily to Intraday Data?

Schulmeister · 2009; 2008 working version · Review of Financial Economics / WIFO

- Market: S&P 500 spot and futures
- Access: Full institutional working paper downloaded; methods inspected
- Decision: **BACKGROUND**

Historical moving-average, momentum and RSI systems; performance weakens in later periods. Intraday sampling does not imply positions always close daily. No generic indicator ensemble is admitted on this evidence alone. [Primary source](https://www.wifo.ac.at/en/publication/120484/).

## P12 — A Profitable Day Trading Strategy for the U.S. Equity Market

Zarattini; Barbon; Aziz · 2024 · Academic/practitioner working paper

- Market: Cross-section of US stocks
- Access: Prior project primary-source review and source register
- Decision: **EXISTING**

Stocks-in-play selection is central. A single NQ contract cannot replicate the stock-selection opportunity set. R2 opening direction and relative-volume models are adaptations. [Primary source](https://concretumgroup.com/wp-content/uploads/2026/02/A-Profitable-Day-Trading-Strategy-For-The-U.S.-Equity-Market.pdf).

## P13 — Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)

Zarattini; Aziz; Barbon · 2024; revised 2025 · Swiss Finance Institute Research Paper 24-97; Concretum / St. Gallen / Peak Capital

- Market: SPY
- Access: Author abstract plus prior project primary-method review
- Decision: **SELECT**

Time-of-day noise bands and dynamic exits deserve a fuller implementation. R2 fixed ATR stops and one-entry restriction changed the strategy materially; its missing-path flags also prevent a clean conclusion. [Primary source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172).

## P14 — Volume Weighted Average Price (VWAP): The Holy Grail for Day Trading Systems

Zarattini; Aziz · 2023; revised 2025 · Practitioner working paper; Concretum / Peak Capital

- Market: QQQ and TQQQ
- Access: Author abstract and prior project primary-source review
- Decision: **SELECT**

Standalone VWAP direction strategy, not an ORB filter. Headline leveraged-ETF returns are not NQ forecasts. Bar-derived VWAP is only an approximation to transaction VWAP. [Primary source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4631351).

## P15 — Can Day Trading Really Be Profitable?

Zarattini; Aziz · 2023; revised 2025 · Practitioner working paper

- Market: QQQ / TQQQ
- Access: Author abstract and author research summary
- Decision: **EXISTING**

Modified opening-range strategy. Already represented in prior ORB work. ETF leverage, execution, and returns cannot be copied to prop-firm NQ accounts. [Primary source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622).

## P16 — Intraday Price Reversals in the US Stock Index Futures Market: A 15-Year Study

Grant; Wolf; Yu · 2005 · Journal of Banking & Finance

- Market: S&P 500 futures
- Access: Publisher abstract and methodology excerpts
- Decision: **EXISTING**

Opening-gap reversals follow initial continuation, but transaction costs sharply weaken significance. R2 already tests fixed gap and opening-shock fades. Supports a comparator for statistical gap classification. [Primary source](https://www.sciencedirect.com/science/article/pii/S0378426604000949).

## P17 — Statistical Arbitrage with Mean-Reverting Overnight Price Gaps on High-Frequency Data of the S&P 500

Stubinger; Schneider · 2019 · Journal of Risk and Financial Management; Erlangen-Nurnberg

- Market: S&P 500 index event study; constituent-stock trading
- Access: Full paper downloaded; event detection and trading sections inspected
- Decision: **SELECT**

Uses jump tests rather than a fixed gap cutoff. Prior-day intraday returns plus the current opening gap can define a causal event. NQ lacks constituent selection; R3 is a single-instrument transfer, not the paper's statistical-arbitrage portfolio. [Primary source](https://www.mdpi.com/1911-8074/12/2/51).

## P18 — Evidence and Behaviour of Support and Resistance Levels in Financial Time Series

Chung; Bellotti · 2021 · Academic preprint; Imperial / Nottingham affiliations in manuscript

- Market: EURUSD, LLOY equity and Brent price series
- Access: Full author preprint downloaded; algorithms and sample inspected
- Decision: **SELECT_EXPLORATORY**

Prior bounce count and age relate to subsequent bounces. Source is not NQ and does not establish executable net trading profits. Causal level discovery and next-bar execution are required. [Primary source](https://arxiv.org/abs/2101.07410).

## P19 — Support for Resistance: Technical Analysis and Intraday Exchange Rates

Osler · 2000 · Federal Reserve Bank of New York Economic Policy Review

- Market: FX
- Access: Primary institutional source located
- Decision: **MECHANISM**

Level-related trend interruptions provide contextual support. FX evidence does not validate NQ levels, opening-range retests, or net profits. [Primary source](https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf).

## P20 — Currency Orders and Exchange-Rate Dynamics: An Explanation for the Predictive Success of Technical Analysis

Osler · 2001 staff report; 2003 publication · NY Fed Staff Report 125 / Journal of Finance

- Market: FX bank orders
- Access: Primary institutional research record
- Decision: **MECHANISM**

Stop and take-profit order clustering offers a possible mechanism for continuation or reversal at levels. Our OHLCV data do not reveal those orders; avoid claims of measured stop hunts. [Primary source](https://www.newyorkfed.org/research/staff_reports/sr125.html).

## P21 — Intraday Patterns in the Cross-section of Stock Returns

Heston; Korajczyk; Sadka · 2010 · Journal of Finance; academic authors, PanAgora research funding acknowledged

- Market: Cross-section of US stocks
- Access: Author manuscript abstract, funding statement and publication record
- Decision: **SELECT_EXPLORATORY**

Same-clock half-hour return continuation motivates a time-series NQ transfer. The paper's cross-sectional finding does not establish an aggregate-index effect. Net executable edge may be absent. [Primary source](https://www.bauer.uh.edu/departments/finance/documents/Heston_Korajczyk_Sadka_paper_UH.pdf).

## P22 — The Overnight Drift

Boyarchenko; Larsen; Whelan · 2020; revised 2022 · Federal Reserve Bank of New York Staff Report 917

- Market: S&P 500 futures
- Access: Primary abstract; prior project full-method review
- Decision: **EXISTING**

European-opening drift and inventory interpretation already motivated R2. A DST correction or extra time filter is not a new discovery family; retain as later implementation work. [Primary source](https://www.newyorkfed.org/research/staff_reports/sr917).

## P23 — The Pre-FOMC Announcement Drift

Lucca; Moench · 2015; staff report 2011/2013 · Journal of Finance / Federal Reserve Bank of New York

- Market: US equities and international comparisons
- Access: Primary institutional abstract
- Decision: **DEFER**

Calendar-event mechanism is credible, but a cash-session-only NQ transfer has a much smaller exposure window and very few events in our short history. Requires a separately frozen event calendar and more data. [Primary source](https://www.newyorkfed.org/research/staff_reports/sr512).

## P24 — Time Series Momentum

Moskowitz; Ooi; Pedersen · 2012 · Journal of Financial Economics / AQR

- Market: 58 futures
- Access: Primary institutional research summary
- Decision: **BACKGROUND**

Long-horizon futures evidence. A 12-month/next-month result is not evidence for a five-minute NQ rule; no intraday model slot on that basis. [Primary source](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum).

## P25 — Enhancing Time Series Momentum Strategies Using Deep Neural Networks

Lim; Zohren; Roberts · 2019 preprint · Oxford / Oxford-Man research

- Market: 88 continuous futures
- Access: Author preprint abstract
- Decision: **DEFER**

Deep Momentum Networks concern a much larger futures panel and a different horizon. Our short single-instrument sample cannot justify a faithful transfer. [Primary source](https://arxiv.org/abs/1904.04912).

## P26 — Deep Reinforcement Learning for Trading

Zhang; Zohren; Roberts · 2019 preprint · Oxford / Oxford-Man research

- Market: Continuous futures portfolios
- Access: Author preprint abstract
- Decision: **DEFER**

Interesting methodology, but reward optimization does not itself supply an edge. Dataset scale, costs and daily-flattening differences make it unsuitable for a new NQ-only slot now. [Primary source](https://arxiv.org/abs/1911.10107).

## P27 — Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic Falsification Study

Mesfin · 2026 · Independent, non-peer-reviewed preprint

- Market: MNQ
- Access: Full author preprint downloaded; abstract and methods inspected
- Decision: **NEGATIVE_EVIDENCE**

Fourteen tested families fail the author's joint criteria. Useful warning, not a proof that all OHLCV strategies are impossible. Positive-control claims are not adopted without reproducible specifications. Already cited in R1 ORB03. [Primary source](https://arxiv.org/abs/2605.04004).

## P28 — A Validated Volatility-Volume-Gap Classifier for Regime Identification in MNQ Intraday Data

Mesfin · 2026 · Independent, non-peer-reviewed preprint

- Market: MNQ
- Access: Full author preprint downloaded and inspected
- Decision: **EXCLUDE**

The paper reports failed trading variants. Unreconciled counts include 40 classifier days, yearly counts totaling 55, and 125 days in another analysis. First-30-minute return is observable at 10:00, not premarket. Do not use the title as evidence of a validated tradable edge. [Primary source](https://arxiv.org/abs/2605.11423).

## P29 — Sequential Structure in Intraday Futures Data: LSTM vs Gradient Boosting on MNQ

Mesfin · 2026 · Independent, non-peer-reviewed preprint

- Market: MNQ
- Access: Full author preprint downloaded; abstract inspected
- Decision: **NEGATIVE_EVIDENCE**

No tested architecture has significant out-of-sample accuracy above the stated base rate. This does not rule out all ML, but it argues against selecting an LSTM simply for sophistication. [Primary source](https://arxiv.org/abs/2605.17724).

## P30 — Market Simulation under Adverse Selection

Lalor; Swishchuk · 2024 preprint; revised 2026 · Academic preprint

- Market: ES, NQ, CL and ZN
- Access: Author preprint record
- Decision: **EXECUTION_ONLY**

Fill probability and adverse selection matter. Market making needs order-level inputs and queue/fill modeling that our one-minute OHLCV data cannot supply. [Primary source](https://arxiv.org/abs/2409.12721).

## P31 — The Probability of Backtest Overfitting

Bailey; Borwein; Lopez de Prado; Zhu · 2017 journal; earlier working versions · Journal of Computational Finance; academic/institutional methodology

- Market: Strategy-selection methodology
- Access: Author-hosted paper/source record
- Decision: **VALIDATION**

Retain the full trial universe and account for selection. PBO is a diagnostic, not a substitute for causal execution or a genuinely untouched test. [Primary source](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

## P32 — The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality

Bailey; Lopez de Prado · 2014 · Journal of Portfolio Management

- Market: Strategy-selection methodology
- Access: Author SSRN abstract
- Decision: **VALIDATION**

Adjust for search and non-normal returns; dependence assumptions and effective trial count must be disclosed. Do not treat every correlated grid row as an independent strategy. [Primary source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551).

## P33 — Anatomy of the Retest in the QQQ Opening Range Breakout

Pineda · 2026 · Independent descriptive working paper

- Market: QQQ one-minute data
- Access: Author SSRN abstract; full specification not accessed
- Decision: **SELECT_EXPLORATORY**

Directly studies breakout/retest sequences, but explicitly makes no exploitability or causality claim. NQ entries, risk rules and timing below are our proposed hypothesis, not a replicated institutional system. [Primary source](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6745958).

## P34 — Information Shares for Markets with Partially Overlapping Trading Hours

See publisher record · 2023 · Journal of Banking & Finance

- Market: S&P 500 / Nasdaq cash and E-mini markets
- Access: Publisher method and conclusion excerpts
- Decision: **DEFER**

Relevant to price discovery, but requires synchronized cash/futures inputs. It does not show that ES reliably leads NQ at our execution horizon. [Primary source](https://doi.org/10.1016/j.jbankfin.2023.106970).

## P35 — Improving Performance with Fast Alphas: A Tactical Overlay for Intraday Trend Trading

Zarattini; Pagani · 2026 · Practitioner research note; Concretum QuanTips

- Market: SPY five-minute bars
- Access: Primary author summary and indexed paper excerpts
- Decision: **EXECUTION_ONLY**

The standalone short-horizon reversal signal loses money after transaction costs in the authors study; they instead investigate delaying trend entries and exits. Retain as a possible later execution overlay after a base NQ signal survives, not an independent tenth edge. [Primary source](https://concretumgroup.com/wp-content/uploads/2026/02/Improving-Performance-with-Fast-Alphas-A-Tactical-Overlay-for-Intraday-Trend-Trading.pdf).

## I01 — Goldman Sachs New Horizons Index: Satellite Intraday Equity Component

Goldman Sachs · Retrieved 2026-09-04 · Official bank methodology; not an academic paper

- Market: Explicit standalone NQ and ES components
- Access: Full 105-page public PDF downloaded; pages 87-88 inspected
- Decision: **SELECT**

NQ component GSISMRNQ reacts to moves from the previous close, uses delayed TWAP rebalancing and ends flat. This overview omits numerical subcomponent parameters; our transparent version must not be called an exact replica or endorsed strategy. [Primary source](https://www.goldmansachs.com/what-we-do/FICC-and-equities/products-and-business-groups/products/index-methodologies-docs/gs-new-horizons-methodology.pdf).

## I02 — Morgan Stanley Non-Financial US Large Cap Short-Only Intraday Momentum Series 3 Index

Morgan Stanley · 2026 filing · Official bank description in SEC filing; not an academic paper

- Market: NQ futures
- Access: Primary filing, pages 20-21 inspected
- Decision: **SUPPORT**

Short-only, previous-close threshold exposure, scaled with price movement and volatility, flat overnight. Corroborates institutional use of the mechanism. Treated within I01's family rather than an extra independent edge; 0.0001 in the table is a transaction-cost rate, not the signal threshold. [Primary source](https://www.sec.gov/Archives/edgar/data/895421/000183988226026759/ms16252_424b2-17291.htm).

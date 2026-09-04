# Research #3 â€” NQ-only edge discovery

Prepared 4 September 2026. **Original literature proposal. Implementation and the frozen v1 grid are now documented in [README.md](README.md); no full Research #3 run has been claimed here.**

The objective is to find an economically meaningful NQ signal that survives executable trading costs and the project's prop-account constraints. Research #1 and #2 supply historical benchmarks. Their original grids are not the main work of this study.

The review register contains **35 research works and two official bank methodologies**, with access depth and rejection reasons recorded in [SOURCES.md](SOURCES.md). Some were read in full, others were screened from primary abstracts, excerpts or conference records. This is a broad, bounded review, not a claim to have found every NQ paper in existence.

## What the search changed

The final selection is **one ORB sequence model and nine non-ORB models**. There is no reason to fill an arbitrary ORB quota. Fifteen-minute ORB was already included in our previous research; the remaining ORB question here is whether waiting for a specific post-breakout sequence changes expectancy.

Direct NQ evidence and institutional provenance are separate facts. Goldman Sachs and Morgan Stanley publicly describe NQ intraday momentum components. Yu et al. directly study NQ return conditions; Rosa includes Nasdaq futures. Much of the remaining usable literature studies ETFs, other futures or individual stocks. Those transfers are labeled below. No candidate is advertised as a proprietary hedge-fund strategy, a verified profitable NQ strategy, or an exact reproduction where source details are missing.

Several candidates are related. In particular, M03 and M04 compete to forecast the same final half-hour using different information. M01, M05 and M06 are different trend engines, not automatically separate economic edges. We will report daily return correlation, overlapping trades and common loss periods before making any diversification claim.

## Selected ten

Numbers identify models, not expected-profit rankings. Priority concerns the strength of the research case and usefulness of the test.

| ID | Model | Main source | Evidence / priority | Material difference from earlier research |
|---|---|---|---|---|
| M01 | Previous-close intraday momentum with gradual position changes | Goldman Sachs I01; Morgan Stanley I02 | Direct NQ institutional methodology; first priority | Repeated, delayed intraday decisions and explicit no-trade bands, rather than one fixed-time closing entry |
| M02 | Conditional overnight / prior-session return forecast | Yu et al. P01 | Direct NQ academic finding; first priority | Estimate magnitudes and interactions prospectively; do not reduce the paper to a static gap-sign filter |
| M03 | Early-return forecast of the closing window | Gao et al. P08 | Peer-reviewed ETF-to-NQ transfer; first priority | Freeze the signal at 10:00; do not substitute the accumulated return through 15:30 |
| M04 | Regime-dependent overnight-to-close forecast | Rosa P10 | Nasdaq-inclusive academic study; conditional reconstruction | Test whether a causal state model improves on a single overnight-return forecast; state inference must not use today's closing return |
| M05 | Dynamic noise-area momentum with band/VWAP exits | Zarattini et al. P13 | Academic/practitioner SPY-to-NQ transfer; first priority | Restore strategy-specific exits and controlled re-entry; explicitly a fuller reconstruction of the R2 family |
| M06 | Standalone VWAP trend engine | Zarattini & Aziz P14 | QQQ-to-NQ practitioner transfer | VWAP supplies entry and exit decisions; no opening-range breakout prerequisite |
| M07 | Statistically detected gap-jump mean reversion | Stubinger & Schneider P17; Grant et al. P16 comparator | Peer-reviewed stock/index-to-NQ transfer; first priority | Test whether jump detection adds value over the fixed-percent gap fades already tested |
| M08 | ORB break, retest, and continuation | Pineda P33; Tsai P02 context | Exploratory QQQ-to-NQ sequence hypothesis | Require distinct, completed breakout and retest bars before entering |
| M09 | Causal support/resistance bounce with level aging | Chung & Bellotti P18; Osler P19/P20 context | Exploratory cross-market transfer | Infer levels from past observations and test bounce count / age; no opening-range requirement |
| M10 | Same-clock return continuation | Heston, Korajczyk & Sadka P21 | Peer-reviewed cross-sectional finding; exploratory NQ time-series transfer | Previous days' returns at the same clock time predict a future interval; no dependence on today's opening breakout |

### M01 â€” Previous-close intraday momentum

**Source boundary.** The Goldman overview describes NQ component GSISMRNQ, decisions based on moves from the prior close, next-window execution, position bands and end-of-day flattening. Its numerical subcomponent rules are not fully specified there. Morgan Stanley's short-only NQ description corroborates the mechanism, not profitability. These are bank index methodologies, not peer-reviewed alpha papers. [Goldman methodology, pp. 87â€“88](https://www.goldmansachs.com/what-we-do/FICC-and-equities/products-and-business-groups/products/index-methodologies-docs/gs-new-horizons-methodology.pdf); [Morgan Stanley filing, pp. 20â€“21](https://www.sec.gov/Archives/edgar/data/895421/000183988226026759/ms16252_424b2-17291.htm).

**Our proposed implementation.** At scheduled decisions, compare the completed-window mean price with the prior regular-session close, scaled by lagged daily return volatility. Use a dead zone and a separate exit band to reduce turnover. The signed score determines a capped target risk budget; translate it into whole NQ/MNQ contracts. Execute only after the signal window ends. The primary executable version uses subsequent bar opens; a delayed multi-bar execution schedule is a separately charged sensitivity test. Do not give fills at the signal's own average price.

**Finite design axes.** Decision spacing 15/30/60 minutes; lookback 20/60 sessions; entry threshold 0.1/0.25/0.5 lagged daily standard deviations; fixed-budget versus capped signal-strength sizing; both directions with long/short attribution. Numerical choices and the RTH-close anchor are our adaptations. Source-like short-only behavior is an ablation within this family, not an eleventh model.

**Reject if:** gains require frictionless rebalancing, the signal loses to matched-exposure unconditional trades, or contract rounding / account caps remove its advantage.

### M02 â€” Conditional session-return forecast

**Source boundary.** Yu et al. study interactions between prior-day and overnight returns directly in Nasdaq futures. The accessible abstract does not provide every regression coefficient or trading rule. This model is a transparent reconstruction of that research question. [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=712168).

**Our proposed implementation.** At the cash open, combine the now-observed opening gap with prior RTH return, their sign interaction, lagged volatility, and a Monday indicator. Fit a small regularized linear model only to completed prior sessions to forecast the return from the first executable post-open bar to a specified morning horizon. Trade only when the predicted move exceeds modeled costs plus a predeclared uncertainty margin. Forecast direction can be continuation, reversal or no trade; it is not hard-wired from the gap sign.

**Finite design axes.** Estimation history 126/252 sessions; endpoints 10:30/11:30/13:00; simple main-effects model versus a limited interaction model; fixed small regularization menu. No exhaustive interactions among arbitrary indicators. Feature scaling and regularization selection happen inside each historical training window.

**Reject if:** the model fails to outperform an intercept-only forecast and the existing gap-sign rule, or coefficients change sign so often that apparent profit is concentrated in a single fitting period.

### M03 â€” Early return to late return

**Source boundary.** Gao et al.'s predictor runs from the previous close to the end of the opening half-hour. It is not just the 09:30â€“10:00 move. Their principal evidence is in equity ETFs. [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866).

**Our proposed implementation.** Freeze that predictor at 10:00 ET, remain flat until 15:30, then trade its predicted direction to 15:59. Test a sign rule and a small, training-only linear forecast. Compare the combined predictor against separate opening-gap and opening-half-hour components. A no-trade band is based on the prior distribution of signal magnitude, not on today's later outcome.

**Finite design axes.** Signal-strength thresholds at the prior median / upper quartile, plus the unfiltered source-inspired baseline; 126/252-session training; forecast versus sign implementation. Keep the primary entry at 15:30 so timing optimization does not silently create a different effect. Long and short outcomes are reported separately.

**Reject if:** a matched 15:30 long-only control explains the result, forecast errors are unstable, or early information adds nothing beyond R2's prior-close-to-entry signal. The R2 comparison uses common eligible dates; it is not a rerun of its whole grid.

### M04 â€” Regime-dependent overnight-to-close forecast

**Source boundary.** Rosa reports disappearing unconditional predictability out of sample and investigates signal strength and regime dependence. The study includes Nasdaq futures, but the full model specification was not accessible here. We are not assuming the paper proves its strategy profitable today. [Publisher record](https://onlinelibrary.wiley.com/doi/10.1002/fut.22375).

**Our proposed implementation.** Forecast 15:30â€“15:59 returns using the opening gap and a two-state Markov regression fitted to prior completed sessions. Today's state probabilities are predicted from yesterday's filtered state and the transition matrix. Do not use smoothed full-sample states or today's target return to classify today's regime. Compare against a single-regime regression and a simple signal-strength threshold before giving the more complex model any credit.

**Finite design axes.** 252-session or expanding estimation, one/two states as explicit comparison, and a small training-only confidence gate. Exclude a fit with singular covariance, inadequate state membership or nonconvergence; do not silently replace it with an in-sample best fit. No VIX, ES or factor data enter our NQ version.

**Reject if:** state conditioning does not improve sequential forecasts after costs and complexity adjustment. M03 and M04 are competing closing-window hypotheses, not assumed portfolio diversifiers.

### M05 â€” Dynamic noise-area momentum

**Source boundary.** The source uses time-dependent bands and dynamic trade management. R2 imposed fixed ATR stops, one entry per date, and different timing; every R2 configuration in this family also carried a missing-path flag. This is the one explicitly designated **fuller reconstruction**, not a newly discovered family. [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172).

**Our proposed implementation.** Estimate absolute open-to-clock-time moves from prior complete sessions. Construct gap-adjusted upper/lower bands. Enter after a scheduled completed-bar signal outside a band. Manage exits using the relevant band and session VWAP, with a protective risk stop added for the account. Allow a limited number of genuinely new signals after an exit; do not reopen repeatedly on every bar of an unchanged signal. Flat by 15:59.

**Finite design axes.** Lookback 14/28/60 sessions; band multiplier 0.75/1/1.25/1.5; decisions every 15/30 minutes; one versus at most three entries; band-only versus band/VWAP exit. These are our declared experimental settings, not all source settings.

**Reject if:** its fuller implementation fails to improve on the simplified one on the same valid dates, costs consume re-entry gains, or unresolved missing bars prevent a known trade path. Repair input coverage before drawing a profit conclusion; never fill gaps with fabricated prices.

### M06 â€” Standalone VWAP trend

**Source boundary.** Zarattini & Aziz test directional VWAP trading in QQQ/TQQQ. Their reported leveraged returns are not forecasts for NQ. The paper is practitioner research. [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4631351).

**Our proposed implementation.** Compute cumulative RTH VWAP from the available bars and trade confirmed price moves onto one side, exiting after a confirmed move back through the exit band. Start with the source-inspired direction rule, then test limited entry/exit hysteresis and controlled re-entry. No ORB trigger. Bar typical-price times volume approximates VWAP; this cannot be described as exact transaction VWAP or actual institutional order flow.

**Finite design axes.** Decision spacing 5/15/30 minutes; confirmation one/two completed decisions; zero/small lagged-volatility buffer; maximum one/three entries; VWAP exit versus protective-stop-first exit. All repeated crossings incur trading costs, and stop distances have a predeclared tick floor.

**Reject if:** turnover or a one-bar execution delay erases the result, or the system merely reproduces a long market exposure with no timing benefit.

### M07 â€” Statistical gap-jump reversion

**Source boundary.** Stubinger & Schneider use jump detection and a constituent-stock framework. We can transfer the event-classification question to NQ, but cannot reproduce their stock selection or market-neutral portfolio. [Paper](https://www.mdpi.com/1911-8074/12/2/51); [accessible repository copy](https://www.econstor.eu/bitstream/10419/239006/1/166817832X.pdf).

**Our proposed implementation.** Use the prior completed session's intraday returns plus the current opening gap in a Barndorff-Nielsenâ€“Shephard-style jump test. Determine the event with information available at the opening quote. Test a subsequent gap fade toward the prior cash close, with a fixed maximum holding period and a protective stop. Compare against an equally selective fixed-percent gap rule, so improved returns cannot be credited simply to taking fewer trades.

**Finite design axes.** Jump significance 0.1%/1%; prior return sampling 1/5 minutes; earliest executable entry versus a five-minute confirmation; hold cap 30/60/120 minutes; target partial/full gap closure. These choices are our transfer. Diagnose the test's calibration when an overnight return has a much longer duration than an intraday observation. If that issue cannot be justified, label the feature an empirical jump score rather than a calibrated statistical p-value.

**Reject if:** too few independent event days survive, overnight-normalization assumptions drive the selection, or the jump rule offers no improvement over R2's simpler gap fade.

### M08 â€” ORB retest continuation

**Source boundary.** Pineda's QQQ paper is explicitly descriptive and does not claim executable profits. Tsai's Nasdaq-inclusive ORB work supports the opening-range context, not this retest rule. This is an exploratory NQ hypothesis with weaker evidence than M01â€“M07. [Retest study](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6745958).

**Our proposed implementation.** Form the opening range, require a completed close outside it, then wait for a later bar to revisit the boundary and close back on the breakout side. Enter at the following bar's open. Track elapsed time and excursion before the retest using already completed bars. Put the initial stop beyond the observed retest extreme or the range boundary, as separate predeclared choices. Never infer break â†’ retest â†’ continuation ordering from one OHLC candle.

**Finite design axes.** Opening range 5/15/30 minutes; retest deadline 5/15/30 minutes; zero/one-tick boundary tolerance; maximum pre-retest excursion as a fraction of range; 1.5/2/3R or time exit. One completed sequence per date for the primary experiment.

**Reject if:** it does not improve on immediate next-bar breakout entries after matching opportunity dates, favorable fills create the result, or waiting removes almost all usable observations.

### M09 â€” Support/resistance bounce with aging

**Source boundary.** Chung & Bellotti study non-NQ price series and statistical bounces, not a validated net-profit NQ strategy. Osler supplies FX mechanism evidence only. [Paper](https://arxiv.org/abs/2101.07410).

**Our proposed implementation.** Discover price zones using strictly trailing windows. Any pivot requiring right-hand observations becomes eligible only after those observations have closed. Store a zone's creation time, past confirmed bounces and age. After price enters an eligible zone and a later close confirms rejection, enter away from it. Exit at a modest predefined move or the opposite previously known zone, with a stop beyond the entry zone. Freeze levels while a setup is being evaluated; do not redraw historical levels using later price action.

**Finite design axes.** Discovery window 30/60/120 minutes; minimum prior bounces one/two/three; maximum age 60/120/240 minutes; zone width derived from lagged short-horizon volatility; holding cap 15/30/60 minutes. The age and bounce-count hypotheses are tested separately before combining them.

**Reject if:** causal discovery removes the apparent effect, net expectancy is absent despite a high bounce probability, or the result depends on assuming an exact limit fill on first touch.

### M10 â€” Same-clock return continuation

**Source boundary.** Heston et al. find a cross-sectional stock pattern at corresponding half-hour intervals on different days. PanAgora support is acknowledged in the manuscript; this is not proof PanAgora trades our proposed NQ model. Transfer from a stock cross-section to one aggregate futures series is substantial and exploratory. [Author manuscript](https://www.bauer.uh.edu/departments/finance/documents/Heston_Korajczyk_Sadka_paper_UH.pdf).

**Our proposed implementation.** For each predeclared half-hour slot, estimate that slot's expected return from previous sessions, with shrinkage toward zero. Trade only when the forecast clears estimated costs and its uncertainty gate. Estimate from prior days only; do not choose the best clock slot using the eventual evaluation period. Distinguish a fixed unconditional time-of-day drift from continuation based on recent same-slot returns.

**Finite design axes.** Lookback 20/40/60 sessions; equal-weighted versus exponentially weighted mean; predeclared signal thresholds; all eligible RTH half-hour slots, with every slot counted in the multiple-testing record. Skip conflicting entries and apply the account's aggregate daily risk budget. The final slot exits at 15:59 as a disclosed adaptation.

**Reject if:** it is no better than a static time-of-day control, only one selected clock slot works, or dependence-aware uncertainty includes zero after search adjustment.

## Shared execution and prop-account requirements

These are requirements for the next implementation, not assertions that an unbuilt engine already satisfies them.

1. **NQ-only signals.** All ten use NQ OHLCV and calendar time derivable from timestamps. No ES, QQQ feed, VIX, option gamma, order-book imbalance, news sentiment or hidden dealer positioning is required. Source-market prices are not needed to run a clearly labeled NQ transfer.
2. **Known bar timing.** Completed-bar signals enter at a later open. Roll handling, exchange timestamps, Eastern Time conversion, duplicate bars and session boundaries must be explicit. Higher-timeframe bars are constructed only from complete one-minute observations.
3. **Daily flattening.** Use 15:59 ET on normal sessions as the research cap, with an earlier session-aware exit or prior exclusion for shortened sessions. No position carries past the selected daily deadline. Entry orders are canceled before the exit deadline. The applicable provider's actual rules must be versioned and checked when implementing; the existing LucidPro reference is not universal compliance certification.
4. **Whole contracts.** Retain the user's NQ-first, MNQ-fallback convention, including fees and slippage in sizing. Use NQ prices as the research input; MNQ fills remain a proxy requiring later independent validation. Do not round contract count upward to reach a target risk.
5. **Multiple-entry accounting.** R2's one-entry engine cannot simply be reused unchanged. Each entry, reversal, scale change and exit must consume costs and respect realized-plus-open daily loss, remaining drawdown buffer and position limits. A stop-out does not restore the daily loss budget. Lockout cancels pending orders and prevents re-entry.
6. **Risk grid is not alpha.** Carry forward the declared intended-risk menu ($50, $75, $100, $125, $150, $175, $200, $250, $300), but report signal returns separately from account sizing. A candidate's best prop variant is selected only from feasible whole-contract account paths. Model-specific exits remain model-specific.
7. **Unknown paths remain unknown.** Missing trade bars, missing forced-exit quotes and unresolved intrabar ordering are flagged. No favorable synthetic fills, no clipping gap losses, no post-hoc switch to another entry when the first opportunity was ambiguous. Stop/target same-bar events receive conservative handling and a separate sensitivity count.
8. **Results must include opportunity cost.** Report eligible days, entries, blocked entries, quantity-zero skips, breaches, inactivity after drawdown and unrealized drawdown, in addition to net P&L, PF and closed-equity drawdown. An account that survives by becoming unable to trade is not a successful variant.

## Research design and stop criteria

The menus above are a specification proposal. Before any launch, enumerate and hash a finite valid configuration manifest, including exact formulas, source versions and all exclusions. Do not claim every continuous setting, every possible ORB or every combination of all ten has been exhausted.

**Stage 1 â€” mechanism and execution.** Give all ten a baseline and a bounded family-specific grid. Test gross prediction and net execution separately. Include the stated simple control for every candidate. Match samples when comparing filters. Record all trials, including failed fits and null results; do not search for an exit rule until a completely different signal appears to win.

**Stage 2 â€” sequential selection.** Within the already examined 2023â€“2025 history, use chronological training and subsequent evaluation windows. Keep scaling, quantiles, model choice, state estimates and risk selection inside training. This is useful walk-forward development evidence, but it is **not a pristine holdout** after R1/R2 and the published papers have exposed overlapping history. Do not rename 2025 'unseen'.

**Stage 3 â€” robustness and prop replay.** Inspect neighboring settings, year/quarter results, block-bootstrap uncertainty on daily P&L, matched long/short controls, delayed entry and harsher cost scenarios. Account for multiple testing using a disclosed deflated-Sharpe / bootstrap framework; effective trial count is uncertain when strategies are correlated. Large-winner concentration is a diagnostic, not an automatic disqualification of positively skewed trend models. Keep top-trade removal and missed-trade stresses visible.

**Stage 4 â€” independent decision.** Obtain a genuinely unexamined period or prospective forward sample after the specification is frozen, with adequate warmup and independent price provenance. A new vendor for the same dates improves data checks but does not create an unseen market period. Our current mirror stops in December 2025, so this final gate is not satisfied today.

For this short dataset, a rare signal is labeled **underpowered**, not promoted from a spectacular PF on a handful of trades. The numerical minimum event count and confidence thresholds must be registered before results. Multiple trades on one date do not create multiple independent market days.

The eventual output for each of the ten must show: the best net-profit configuration, the best qualifying prop-account configuration, source fidelity, cost sensitivity, temporal stability, number of distinct event days, and an explicit ADVANCE / REJECT / NEEDS_DATA / UNDERPOWERED decision. A model may have no qualifying prop variant. Comparisons to existing leaders use the common period and accounting definitions; no rerun of every R1/R2 configuration is needed.

## Why other attractive ideas were left out

- **ESâ€“NQ pairs / lead-lag:** synchronized ES data are absent. Cash/futures price-discovery studies do not prove minute-horizon ES-to-NQ predictability.
- **Dealer-gamma, footprint, order-flow and market making:** their required inputs and fill models cannot be reconstructed from OHLCV.
- **Fast-alpha execution overlay (P35):** the practitioner study reports an unprofitable standalone reversal signal after costs, then uses it to time trend entries/exits. Keep this as later execution research after a base signal survives; do not count it as an independent edge or multiply all ten initial grids by its settings.
- **Another generic neural net / RL / indicator ensemble:** architectural sophistication is not an economic mechanism. Larger-panel, longer-horizon results do not transfer automatically to roughly three years of one instrument.
- **VVG classifier:** its own trading tests fail, and its denominators are unreconciled. It is excluded rather than used as a 'validated regime edge'.
- **Pre-FOMC drift:** worth keeping in the literature register, but too few calendar events and a materially truncated holding window for the present main ten.
- **Failed-ORB reversal and generic VWAP mean reversion:** no sufficiently direct, verified tradable evidence was found to prioritize these over the selected candidates. They remain hypotheses outside this study, not disproven strategies.
- **Another plain 5/15/30-minute ORB or another daily-volatility filter:** already represented in the previous research. The retest model earns its slot through a different observable entry sequence.

The strongest first implementation priorities are M01, M02, M03, M05 and M07. That is a ranking of research usefulness and evidence, **not a prediction of which will earn the most money**. The remaining five still receive their declared tests; exploratory models do not receive a looser promotion standard.

## Status and deliverables

- Literature selection and model definitions: complete for this proposal.
- Source register: [readable](SOURCES.md), [CSV](source_register.csv), [JSON](source_register.json).
- Executable engine, exact grid manifest and GitHub workflow: subsequently implemented; see [README.md](README.md) for the frozen scope and run instructions.
- New empirical performance claims: none. No Research #3 best model or best prop variant exists until its results are produced.

# Research #4: 31 ORB-related variants without repeated searches

Prepared 2026-09-04. Status: selected research designs, not implemented, backtested or validated. No GitHub workflow has been launched. Parameter values below are draft finite menus, not a frozen executable grid.

User requirement: never rerun an already tested strategy/configuration as another search candidate. Reuse archived results for historical reference. A new name, opening length, risk amount, threshold value or estimator alone does not establish novelty. Do not silently add old benchmark reruns.

The user expanded this study to 31 variants. R4-01 through R4-20 are retained; R4-21 through R4-30 are paper-grounded additions; R4-31 is the user-defined inside-range target model. These include changes to entry/context/range construction and explicit changes to trade management. They are related ORB hypotheses, not 31 independent sources of alpha. Profitability is unknown. A six-minute earlier run does not establish the runtime or cost of this study.

## Earlier work checked

- R1: `nq_orb_research_suite_010.py`, `source_notes.json`: opening direction and EMA gates; opening volume z-score and breakout close-location proxy; delayed entry; short probe/touch ORB; prior-return volatility states; statistical price thresholds; shifted range boundaries; neural direction classifier; predicted full-session range gate; prior-day/overnight return states. Fixed structural/ATR stops, targets and clock exits.
- R2: `research2/grid.json`, `research2/README.md`: VWAP, relative opening volume, volatility state, gap/prior-return direction, opening body strength; one/two-close confirmation, fixed/ATR stops and targets, breakeven trailing. Five non-ORB families as documented there.
- R3: `research3/signals.py`, `research3/registry.py`: notably M08's first-break boundary retest/rejection, plus standalone momentum, forecasts, noise bands, VWAP direction, gap fade, support/resistance rejection and same-clock continuation.

The distinctions below are based on inspected executable mechanisms. This is not yet a generated cross-study manifest equality proof. That check must occur before running R4.

## Common causal contract

All models use NQ minute OHLCV only; whole NQ-first/MNQ-fallback sizing. Overnight-dependent models require verified full overnight coverage, not just cash-session bars. Missing observations invalidate the affected feature/path; no synthetic fills or retroactive skipping of adverse paths.

Opening ranges normally use 5/15/30 completed minutes; these are settings, not separate models. R4-04 defines its opening range using volume instead. A completed-bar signal may submit an order no earlier than the next minute. Market-entry models enter at that next executable open. R4-15 explicitly tests a resting limit instead. All sequence events must occur on separate completed bars, with no inference about intrabar event order. Protective prices must be valid ticks. One entry episode per session; the observed first break in R4-07/08 is not traded. R4-19 and R4-25 permit partial exits and R4-20 permits additions within its single episode. R4-31 enters inside its fixed 15-minute range rather than on an outside breakout. No exposure overnight; flatten by 15:59 ET, with daily loss and continuous account protections applied consistently.

## Selected models

### R4-01 — Inside-day compression ORB

Prior RTH session is strictly inside the preceding RTH high/low AND its high-low range is the smallest over the last N completed sessions, including that prior session. Trade the first confirmed break of today's completed opening range. N in {4,7}; condition is mandatory, never an OFF option.

Hypothesis: contraction in actual price-range geometry may precede directional expansion. Novelty: inside-day containment plus narrow-range rank; R1/R2 used return-volatility states, not this joint pattern. Source: Crabel's original inside-day ORB article, with the narrow-range conjunction our specified reconstruction. Not an exact replication or proof on NQ.

### R4-02 — Opening and overnight range clearance

Build the overnight high/low from the scheduled prior CME evening session through 09:29 ET. For a long, require the first completed close above both opening-range high and overnight high; mirror for shorts. Require the overnight boundary to be beyond the opening boundary by at least one tick so this cannot collapse into ordinary ORB. Draft maximum boundary separation in opening-range units: {0.5,1,2}.

Hypothesis: clearing a second observable range may distinguish continuation from a break into nearby resistance. Novelty: overnight extrema and combined breakout threshold, not overnight return sign. Original NQ hypothesis; order-clustering research provides only indirect motivation, not evidence of orders at these exact levels.

### R4-03 — Acceptance outside the previous day's range

Today's RTH opens strictly above the previous RTH high (long) or below its low (short). Every completed opening-range close must remain outside that prior boundary. Enter only on the subsequent opening-range breakout in that direction. Reject a day that closes back inside the previous range before entry.

Hypothesis: sustained repricing outside the previous range may be more informative than a gap measured from the previous close. Novelty: prior high/low and observed acceptance sequence; neither the old gap-sign gate nor its magnitude filter contains this rule. Original hypothesis.

### R4-04 — Volume-clock opening range

Before the session, set a volume quota to {0.75,1,1.25} times the median first-15-minute volume over {20,40} prior valid normal sessions. After at least five completed minutes, freeze the opening range at the first completed minute when accumulated volume reaches the quota. If not reached by 10:15 ET, do not trade. Only later completed-bar breakouts can trigger entry; the quota-crossing bar is part of the range.

Hypothesis: comparable trading activity may define the opening auction more consistently than a fixed number of minutes. Novelty: volume determines range completion, rather than filtering a fixed range with RVOL. Original ORB construction, conceptually related to activity-time models; not an existing proven NQ strategy.

### R4-05 — Opening path efficiency ORB

Compute E = abs(last opening close - RTH open) / (abs(first close - RTH open) + sum of absolute successive minute-close changes). Zero denominator means no trade. Require E >= {0.4,0.6,0.8} and allow breakout only in the opening net-move direction.

Hypothesis: a persistent opening path may contain more directional information than a choppy path with the same net move. Novelty: the denominator measures the entire observed close path; R2's body/high-low-range ratio and R1's single-bar close-location proxy do not. Original hypothesis, not a paper replication.

### R4-06 — Repeated pressure at the opening boundary

After the range forms, count {2,3} distinct completed closes inside a band of {0.1,0.2} opening widths immediately below the upper boundary (mirror for shorts). Separate visits require an intervening close at least {0.2,0.3} opening widths away from that boundary toward the range interior. An outside close before enough visits cancels that direction. Enter on the subsequent completed close outside the boundary.

Hypothesis: repeated approaches followed by a break may identify a different continuation population. Novelty: event count and separated approaches before the first break; not a post-break retest, consecutive-close confirmation or support/resistance fade. Price observations do not establish actual liquidity absorption. Original hypothesis with indirect market-microstructure motivation.

### R4-07 — Failed first side, opposite ORB

Observe but do not trade a first completed close outside either opening boundary. Require a later close strictly back inside the opening range, followed by a still later close beyond the opposite boundary. Enter the opposite breakout. Draft maximum elapsed time from first break: {15,30,60} minutes. Each stage needs a distinct completed bar.

Hypothesis: failure on one side followed by a full range traversal may identify a directional reversal with follow-through. Novelty: failure and opposite-boundary break are mandatory; this is neither the old opening-shock fade nor first-break retest. Original hypothesis; no claim that trapped positions can be observed from OHLCV.

### R4-08 — Second attempt after a failed breakout

Observe but do not trade the first completed breakout. Require a subsequent close at least {0.1,0.25} opening widths back inside the range, then at least {2,3} consecutive inside closes. Cancel if the opposite boundary breaks. Enter only on a later new close outside the original boundary; maximum sequence duration {15,30,60} minutes.

Hypothesis: a renewed break after genuine failure and rebuilding may differ from a first attempt. Novelty versus R3 M08: mandatory closes well back inside and a fresh inside phase; merely touching the boundary and closing outside cannot qualify. Original hypothesis. Only the second attempt is traded.

### R4-09 — Flag continuation entirely beyond the opening range

Observe a first completed ORB without entering. Require a completed impulse of at least {0.25,0.5} opening widths beyond that boundary, then a box of {3,5} fully completed bars whose total high-low span is no more than {0.25,0.5} opening widths. Every low of a long-side box must be at least one tick above the opening high (mirror for shorts). Freeze the first qualifying box, then enter only on a later close beyond its far edge. Cancel if price re-enters the original range before entry; wait at most 30 minutes after the first break.

Hypothesis: consolidation outside the range followed by renewed expansion may filter failed breakouts. Novelty: a new, strictly external consolidation box and secondary breakout; no original-boundary retest is allowed. Original hypothesis.

### R4-10 — ORB with a progress-dependent exit

Use the completed first ORB close as entry signal. Retain the initial protective stop. At {5,10,15} completed minutes after entry, exit at the next open if the maximum favorable COMPLETED-CLOSE movement has not reached {0.25,0.5} of initial stop distance. Otherwise retain the original stop/target and hard session exit. Initial price risk is frozen at entry. Do not introduce pyramiding, retries or an OFF setting.

Hypothesis: breakouts that fail to make early progress may have a different continuation expectancy; conditional exits could improve usable risk-adjusted returns. Novelty: path-dependent progress deadline, rather than a fixed time exit or breakeven stop. This is an explicit management model, not a claim of a new entry signal. Kaminski/Lo provide general analysis of when stop policies can add/subtract value, not evidence for this exact deadline rule. The unchanged entry computation may be reused; the new exit requires its own outcome evaluation.

### R4-11 — ORB with VWAP slope alignment

Require the first qualifying completed ORB close to be on the correct side of RTH VWAP AND require the signed change in VWAP over {3,5,10} completed minutes, normalized by lagged daily ATR, to exceed {0.001,0.003,0.005}. VWAP uses cumulative typical-price times volume from 09:30, matching the existing data convention. Insufficient lookback means no signal. The positive slope threshold is mandatory.

Hypothesis: the direction of the session's volume-weighted average may distinguish directional activity from a brief price crossing. Novelty: a mandatory VWAP trajectory condition; the previous ORB VWAP gate measured only contemporaneous price distance. Original extension, not a validated paper rule.

### R4-12 — VWAP reclaim before ORB

After the opening range forms, require price first to close below RTH VWAP for a prospective long, later to close above it, and then to hold above for {2,3} completed closes. The final hold close must still be inside the opening range. Only a subsequent completed opening-range breakout enters. Mirror for shorts. Cancel if the opposite opening boundary breaks during setup or if VWAP is lost after the hold; setup expires after {10,20,30} minutes.

Hypothesis: a completed change in price position around VWAP followed by range clearance may differ from simply being above VWAP. Novelty: mandatory ordered reclaim, hold and later breakout. Never admit a setup that starts already aligned without a reclaim. Original hypothesis.

### R4-13 — ORB with a VWAP trailing exit

Enter the first completed ORB close, then retain the initial protective stop while tightening it each minute using the preceding completed bar's RTH VWAP, offset against the trade by {0,0.025,0.05} lagged daily ATR. A long stop is the maximum of its old stop and the new tick-rounded level; mirror for shorts. Stop updates apply only to the following bar and can never loosen the stop.

Hypothesis: ORB trades may benefit from a session-responsive exit. Novelty: R2's ORB VWAP condition was an entry gate; its exits were fixed or breakeven. R3 used VWAP within other entry families, not this ORB entry/management combination. Adaptation motivated by Concretum's SPY momentum exit research; no NQ performance claim.

### R4-14 — Overnight and cash VWAP alignment ORB

Compute a frozen overnight VWAP from the preceding scheduled evening session through 09:29 and a developing cash-session VWAP from 09:30. At the ORB signal require, for a long, close > cash VWAP > overnight VWAP, with the latter gap exceeding {0.001,0.005,0.01} lagged daily ATR; mirror for shorts. Both anchors must have valid coverage and positive volume.

Hypothesis: agreement between overnight and cash-session average prices may carry information beyond gap direction. Novelty: the relation of two explicitly defined VWAP anchors, not the old single VWAP or return-sign filter. Original hypothesis. Overnight coverage is a prerequisite.

### R4-15 — Resting pullback-limit ORB

After a completed first breakout, place a limit at the broken opening boundary, offset further into the range by {0,0.1,0.2} opening widths. It becomes active only on the following minute and expires after {3,5,10} minutes or the session entry cutoff, whichever is earlier. Cancel on an opposite-boundary close. Do not fill retroactively on the signal bar. A later completed rejection is not an entry prerequisite.

Hypothesis: improved entry price can offset missed fills and adverse selection. Novelty: a precommitted resting limit, rather than R3 M08's market order after completed retest/rejection. Use conservative trade-through fill assumptions and flag bars where fill/stop ordering is unresolved. No claim of queue-level fill certainty from OHLCV. Original execution variant.

### R4-16 — Nested opening-range expansion

Use nested opening lengths {(5,15),(5,30),(15,30)}. Observe a completed breakout of the short range before the long range finishes forming; do not enter. Every subsequent close through completion of the long range must remain beyond that same short-range boundary. Enter only on a later completed breakout of the long range in that direction. Require the long boundary to extend beyond the short boundary by at least one tick. Otherwise skip.

Hypothesis: sustained expansion across two opening stages may identify a different continuation population. Novelty: mandatory earlier break and persistent acceptance before a second range completes; not merely a longer opening window or two-bar confirmation. Original hypothesis.

### R4-17 — Failed ORB fade toward the midpoint

Observe a completed breakout followed within {3,5,10} minutes by a later close back inside the opening range by at least {0.1,0.25} opening widths. Enter toward the opening midpoint at the next open, only if that target remains ahead of the executable entry. Freeze a protective stop beyond the observed failed-break extreme. One attempt; no retry or reversal after exit.

Hypothesis: some failed breakouts revert within the established opening range. Novelty: requires an actual completed ORB failure; R3's gap fade and R2's opening-shock reversal did not. Differs from R4-07, which waits to trade through the opposite boundary. This is an ORB-failure variant, not a continuation trade. Original hypothesis.

### R4-18 — ORB with a chandelier trailing stop

After a completed ORB market entry, retain its initial stop. For a long, tighten using the highest high observed since entry minus {2,3,4} times ATR of the last {5,10,20} fully completed RTH minute bars; mirror for shorts. Need a complete ATR window, update next bar only, never widen the stop, and round to valid ticks. Use the actual post-entry path, not future session extrema.

Hypothesis: a volatility-adaptive trailing exit may retain trend extensions while reducing reversals. Novelty: realized post-entry extreme and rolling intraday ATR management, unlike fixed daily-ATR stops, breakeven or noise-band stops previously tested. Original ORB management adaptation.

### R4-19 — ORB with partial profit and a runner

After an ordinary completed ORB entry, exit {one-third,one-half} of initial whole contracts at {1,1.5,2} initial R; round the partial quantity down and require at least one contract exited and one left. Retain the initial stop on the remainder and hold it to the specified session exit. Do not silently turn an infeasible partial exit into an ordinary all-or-nothing strategy. Charge costs per actually traded contract.

Hypothesis: a different payoff distribution may improve prop-account usability. Novelty: explicit partial realization plus residual exposure within an ORB episode. Existing fixed targets closed the whole trade. Original management hypothesis, not a promise that scaling out improves expectancy.

### R4-20 — ORB with conditional additions

Commit {one-half,two-thirds} of the fixed total episode risk budget at the first completed ORB entry. Permit at most {1,2} additions after completed favorable-close progress of {0.5,1} initial R per addition, entering next open. Each addition requires valid whole-contract size and aggregate marked liquidation risk within the original total episode budget, daily/account headroom and contract caps. Keep the original instrument while exposed; never add to a loser or widen the protective stop to enable an addition. A second addition is allowed only where additional reserved risk remains.

Hypothesis: reserve exposure for breakouts that demonstrate progress. Novelty: explicit ORB staged entry under a fixed total risk cap; R1/R2 ORB entered full size once, and R3 M01 resizing used another signal family. Original management hypothesis. Outcomes must include commissions, missed quantity and cumulative episode risk.

## R4-21 through R4-30: additional paper-grounded designs

These ten are new ORB adaptations of inspected research methods. They are not ten published, validated NQ ORB strategies. Source support for a method is distinct from evidence of profitable transfer. Draft parameter menus remain unfrozen.

### R4-21 - Causal triangle-compression ORB

Role: Entry selection. Wait for a narrowing triangle inside the opening range, then trade its later breakout.

**Rule:** After the opening range forms, require five alternating confirmed close-price extrema wholly inside it: successive highs decrease and successive lows increase. Freeze the first qualifying shape. Enter only on a later completed close outside the original opening range. Cancel if either range boundary breaks before the pattern is confirmed.

**Method:** Use a trailing local-linear smoother, with each estimate frozen when computed. Confirm a candidate extreme only after a fixed number of later observed bars; the detection time, not the extreme time, governs availability. This causal reconstruction differs from the source smoothing implementation.

**Novelty:** Two-sided geometric convergence before the first breakout. R4-06 counts one-sided approaches, R4-09 requires an external flag, and R3 M09 fades general support/resistance.

**Limits:** Pattern informativeness on daily stocks is not executable NQ profit. Confirmation delay can make events sparse. Kernel bandwidth and pivot delay must be fixed before evaluation.

**Axes to freeze:** Opening 5/15/30 minutes; smoothing bandwidth; confirmation delay; minimum contraction; pattern expiry; shared compatible risk/exit choices.

**Primary source:** [Andrew Lo, Harry Mamaysky and Jiang Wang (2000)](https://business.columbia.edu/sites/default/files-efs/pubfiles/19268/Lo-Mamaysky_wang_foundations.pdf).

### R4-22 - Sequential drift-evidence ORB

Role: Entry selection. Require accumulated directional evidence before accepting the breakout.

**Rule:** Standardize completed minute returns using location and scale from prior sessions at the same clock time. Update Cplus=max(0,Cplus+z-k) and Cminus=max(0,Cminus-z-k). Admit the first completed ORB close only when its same-direction statistic exceeds a positive threshold and the opposing detector has not triggered recently. Reset and expire alarms using frozen rules.

**Method:** The score accumulated across the observed sequence is the new mechanism. Calibrate thresholds on prior training data; treat uncalibrated values as research scores, not nominal sequential significance levels.

**Novelty:** Unlike R1 statistical price-distance thresholds and R2 consecutive-close confirmation, contrary observations can erase accumulated evidence. R4-26 acts after entry on posterior deterioration, not before entry on this score.

**Limits:** Opening seasonality and serial dependence violate naive iid false-alarm interpretations. An anomaly detector need not identify profitable continuation.

**Axes to freeze:** Prior normalization window; score drift allowance; alarm threshold; expiry; OR length; compatible execution settings.

**Primary source:** [Andrey Pepelyshev and Aleksey Polunchenko (2015 manuscript)](https://arxiv.org/pdf/1509.01570).

### R4-23 - Return-volume interaction ORB

Role: Conditional forecast. Learn when opening volume supports continuation and when it signals reversal.

**Rule:** Fit a small prior-only regression y=a+b*x+c*x*v, where x is the completed opening return, v is opening volume surprise relative to prior same-clock history, and y is the later return over a fixed horizon. Refit using only completed prior-day labels. Require agreement with the ORB direction, a material interaction contribution, and a cost-adjusted forecast hurdle before entry.

**Method:** Volume is not a monotone high-volume-is-good filter. Freeze a low-dimensional model with shrinkage and minimum historical episodes. The exact forecast horizon must match the entry evaluation; do not train on the opening period itself as outcome.

**Novelty:** R2 RVOL used a fixed volume threshold. R3 M02 did not use this opening-return times unexpected-volume mechanism. It is not another classifier merely given a new name.

**Limits:** Daily equity evidence is transferred to NQ opening episodes. Coefficients may be unstable with few sessions. Forecasting a horizon return does not directly predict stop/target ordering.

**Axes to freeze:** Opening length; prior volume window; training window; future forecast horizon; regularization; nonzero interaction hurdle; cost hurdle.

**Primary source:** [John Campbell, Sanford Grossman and Jiang Wang (1993)](https://web.mit.edu/wangj/www/pap/CampbellGrossmanWang93.pdf).

### R4-24 - Jump-shock recovery ORB

Role: Entry sequence. Skip the shock breakout; trade only after quieter rebuilding and fresh clearance.

**Rule:** Require a high descriptive jump share in the opening block, observe its first breakout without trading, then require a later complete low-jump-share block. Enter only on a still-later close beyond both the original opening boundary and the frozen shock-block extreme. Cancel on an opposite-boundary break.

**Method:** RV=sum(r squared), BV approximately (pi/2)*sum(abs(r_i)*abs(r_i-1)); J=max(RV-BV,0). Compare J/RV using fixed block-length conventions and prior clock-matched ranks. Do not count an overnight gap inside a cash-session return block.

**Novelty:** Mandatory shock, rebuild and second clearance. R1 volatility states lack this path; R3 M07 detects an overnight jump and fades its gap.

**Limits:** Short blocks do not justify asymptotic jump-test confidence claims. This is a descriptive shock statistic; no news event or information cause is observed.

**Axes to freeze:** Opening 15/30 minutes; high jump-share rank; rebuild 10/15/20 minutes; low jump-share rank; sequence deadline.

**Primary source:** [Torben Andersen, Tim Bollerslev and Francis Diebold (2007 publication; 2005 manuscript inspected)](https://public.econ.duke.edu/~get/browse/courses/201/spr08/DOWNLOADS/Bollerslev/Andersen-Bollerslev-Diebold-2005.pdf).

### R4-25 - Adverse-semivariance reduction ORB

Role: Position management. Reduce exposure when damaging price variation builds after entry.

**Rule:** After an ordinary completed ORB entry and a minimum observation block, calculate squared negative returns for a long, or squared positive returns for a short. If adverse variation exceeds both a share threshold and a lagged same-clock magnitude threshold, reduce a fixed fraction of whole contracts at the next open. Never re-add; retain the initial stop and hard session exit.

**Method:** Adverse share = sum(r squared for side*r<0)/sum(r squared). Both magnitude and share conditions are mandatory, preventing tiny quiet moves from triggering solely by sign. Require enough contracts to execute a genuine partial reduction.

**Novelty:** R4-19 takes profits; this can reduce a losing position before its initial stop. It is not the progress deadline, breakeven rule or ATR trail.

**Limits:** The paper predicts future volatility, not return direction. Treating positive returns as adverse for shorts is our symmetric adaptation. Management cannot manufacture positive expectancy from nothing.

**Axes to freeze:** Observation block; share threshold; prior magnitude percentile; reduction fraction; compatible ORB entry/initial risk rules.

**Primary source:** [Andrew Patton and Kevin Sheppard (2015 publication; 2013 manuscript inspected)](https://public.econ.duke.edu/~ap172/Patton_Sheppard_good_bad_vol_Nov13_ALL.pdf).

### R4-26 - Bayesian regime-break exit ORB

Role: Position management. Exit when online evidence suggests the breakout regime has changed against the position.

**Rule:** Enter a completed ORB, then update a Bayesian model on completed seasonality-adjusted returns. Exit next open when posterior mass for a recent new run and an adverse mean exceeds a frozen threshold. Require a minimum observation/run length and retain hard stops throughout.

**Method:** Use the joint event P(run length<=k and side*new mean<0 | observed data), not only a potentially uninformative constant-hazard reset probability. Freeze prior, hazard and posterior truncation. Never backdate the exit to an inferred past change point.

**Novelty:** Post-entry online deterioration exit; distinct from the prior HMM closing forecast and R4-22 entry-only cumulative evidence. Related detection concepts, different complete order policies.

**Limits:** Posterior probabilities depend on model assumptions. The cited futures momentum work is daily and multi-asset; its neural strategy and returns are not reproduced here.

**Axes to freeze:** Hazard; recent-run cutoff; posterior threshold; minimum observations; frozen prior choices; compatible entry and stop settings.

**Primary source:** [Ryan Prescott Adams and David MacKay (2007)](https://www.cs.princeton.edu/~rpa/pubs/adams2007changepoint.pdf), [Kieran Wood, Stephen Roberts and Stefan Zohren (2021 preprint; version 2 inspected)](https://arxiv.org/html/2105.13727v2).

### R4-27 - Serial-dependence transition ORB

Role: Entry sequence. Require a transition from choppy returns to persistent returns before the breakout.

**Rule:** Require an earlier completed return window with negative serial dependence, then a later nonoverlapping window with positive dependence, and only then a completed ORB. Both windows must lie within the same valid session. If the opening boundary already broke before the transition was observable, skip that direction.

**Method:** Use VR(q)-1=2*sum((1-j/q)*rho(j)) with the published heteroskedasticity correction. Normalize using prior same-clock scales. Use sufficiently long blocks and small lags; the scores need separate sequential calibration before any p-value interpretation.

**Novelty:** An ordered dependence-state transition, rather than net direction or R4-05 absolute path efficiency. Neither prior generic volatility gating nor the same-clock forecast encodes it.

**Limits:** The Federal Reserve source fails to reject a random walk for the S&P 500. Longer windows may leave few eligible late breakouts; insufficient events must be reported, not solved by shrinking windows post hoc.

**Axes to freeze:** Two consecutive block lengths, draft 20/30 minutes; small lag q, draft 2/3; negative/positive score hurdles; expiry; OR length.

**Primary source:** [Paul Eitelman and Justin Vitanza (2008)](https://www.federalreserve.gov/pubs/ifdp/2008/956/ifdp956.htm).

### R4-28 - Two-scale directional-change ORB

Role: Entry sequence. Require a small pullback and recovery while a larger price trend remains intact.

**Rule:** Track small and large price-change event states using completed closes, with both amplitude thresholds fixed from lagged ATR before the session. After opening-range formation require large-scale alignment, a small-scale turn against it, then a confirmed small-scale turn back with it while the large state never reverses. Enter on a later ORB; cancel premature boundary breaks.

**Method:** An event is available at its confirming reversal, not at the retrospectively identified extreme. Keep large threshold strictly above small threshold. The representation is adapted; the paper AutoML/genetic strategy is not copied.

**Novelty:** Ordered events across two price-amplitude scales, unlike the two clock-defined ranges in R4-16, the fixed box in R4-09 or a simple retest.

**Limits:** The source studies FX and includes events with no subsequent overshoot. A simple percentage trailing stop would not constitute this model.

**Axes to freeze:** Small event amplitude; larger/smaller ratio; sequence expiry; opening length; compatible entry and exits.

**Primary source:** [Adesola Adegboye, Michael Kampouridis and Fernando Otero (2022 online publication)](https://link.springer.com/article/10.1007/s10462-022-10307-0).

### R4-29 - Unexpected price-impact ORB

Role: Execution-condition selection. Avoid breakouts where unusually little turnover produces a large price move.

**Rule:** For completed opening bars, aggregate absolute log return divided by NQ notional turnover, using contract volume times price times the fixed NQ multiplier. Compare log impact against a prior-only same-clock forecast. Admit an ORB only when the positive unexpected-impact residual is below a strict predeclared upper bound.

**Method:** Freeze aggregation and handling of zero-volume/zero-return observations. Missing or zero turnover cannot become zero impact. This is an OHLCV proxy; do not label it measured order-book impact.

**Novelty:** Return per turnover and its forecast residual, rather than volume alone, volume clock or volatility alone. R4-30 estimates spread; this estimates a different friction proxy.

**Limits:** Amihud studies stock liquidity over much longer horizons. The direction of the proposed intraday selection effect is a new hypothesis. Thin-print ratios can be unstable.

**Axes to freeze:** Opening window; robust aggregation; prior forecast window; residual cutoff; compatible ORB execution settings.

**Primary source:** [Yakov Amihud (2002)](https://www.cis.upenn.edu/~mkearns/finread/amihud.pdf).

### R4-30 - Estimated-friction ORB

Role: Execution-condition selection. Require sufficient room relative to an estimated trading-friction measure.

**Rule:** Wait for two complete adjacent 15-minute blocks, earliest 10:00. Compute the Corwin-Schultz high-low spread proxy from those observed intervals. Admit a subsequent, still-untriggered ORB only if a valid nonnegative estimate is below both a prior same-clock percentile and a fraction of opening width. Skip earlier breaks rather than assigning them a later estimate.

**Method:** Negative estimates are invalid observations in this candidate, not free trading. Keep baseline commission/slippage unchanged even for a small estimate. Require high!=low and valid observations in both blocks.

**Novelty:** Mandatory pre-entry friction selection absent from earlier fixed-cost tests. The two-block availability constraint is part of the design, not a hidden lookahead.

**Limits:** The source validates daily averages of equity estimates, not a single NQ block. The proxy may be especially noisy for liquid tick-constrained futures. No quote-level accuracy claim.

**Axes to freeze:** Fixed 15-minute estimator blocks; lagged percentile; spread/opening-width ceiling; OR length; entry cutoff; compatible risk/exit settings.

**Primary source:** [Shane Corwin and Paul Schultz (February 2009 appendix; related Journal of Finance article 2012)](https://sites.nd.edu/scorwin/files/2019/11/Application_Intraday_Analysis.pdf).

## R4-31 - Inside-range target model

User clarification: entry must be inside the fixed opening range; target its high or low. Outside-to-boundary entries are excluded.

Freeze H=max(high) and L=min(low) from 09:30:00 through 09:44:59 America/New_York. In minute-open data these are the 09:30 through 09:44 bars. W=H-L. No entry before 09:45. Every executable entry must be strictly inside (L,H). A long targets H; a short targets L. Target levels never expand with later prices.

This is the user's original target hypothesis. None of the inspected papers validates these exact NQ targets. Pattern and optimal-stopping research inform how to define entry, costs and deadlines, not a claim that opening extrema attract price.

### 31A - Edge rejection toward the opposite boundary

For a long, price visits the lower quarter of the frozen range after 09:45 while closing inside. Require a later completed close above the preceding two completed-bar highs, with confirmation still below the midpoint. Enter next open only if strictly inside and the target remains ahead. Stop below the lowest observed setup low plus a tick buffer; target H. Mirror near the upper quarter for a short targeting L.

Largest structural room to the opposite boundary and a local reversal trigger. First implementation priority because its entry and invalidation are easy to audit.

### 31B - Failed breakout back inside, then full-range traverse

Observe a completed close outside one opening boundary. Require a later close back inside and one additional inside hold close; then enter in the return direction at the next inside open. A failed lower break gives a long targeting H; a failed upper break gives a short targeting L. Stop beyond the frozen failed-break extreme. Skip if price has already crossed the target or the reward/cost hurdle fails.

Tests failure and rejection of the outside move. Shares a setup concept with R4-17, but its opposite-boundary target and extra hold alter the order policy; record that relationship rather than claim independence.

### 31C - Midpoint reclaim toward the nearer directional boundary

Require at least two completed inside closes in the lower half, then a completed reclaim above midpoint and an additional inside hold above midpoint. Enter long at the next inside open, target H, stop below the lowest observed reclaim/hold low. Mirror for a short. No target is chosen after observing the future move.

Later confirmation may reduce false reversals but sacrifices target distance; costs and reward-to-risk screening are essential.

### Expanded entries approved for design: 31D-31J

Models 1-30 remain unchanged. Model 31 now contains ten entry families, A-J. The detailed [MODEL31_ENTRIES.md](MODEL31_ENTRIES.md) specification defines the new one-minute patterns, location filters, causal sequencing and applicable draft grids, and resolves implementation details for A-C.

| Family | Additional entry hypothesis |
|---|---|
| 31D | One-minute IFVG: full-zone close inversion, immediate or later retest entry; with/without displacement confirmation |
| 31E | Pure displacement candle, quantified by lagged body size, body/range and closing position |
| 31F | Ordinary FVG pullback and rejection toward the opening boundary |
| 31G | Wick excursion beyond an opening boundary and recovery; immediate or later confirmation |
| 31H | Two separated edge tests, then a neckline break |
| 31I | RTH VWAP reclaim and hold while still inside the opening range |
| 31J | Tight box wholly inside the opening range, then directional escape |

**Draft finite grid:** Use the applicable family-specific and common menus in MODEL31_ENTRIES.md. Explicitly test entry proximity to both opening boundaries, including continuation near the destination when reward/risk and costs permit. Do not multiply irrelevant parameters or interpret these ten families as ten independent edges. The earlier PDF/report is the original research snapshot; this expanded entry specification supersedes its model-31 section. No backtest has been run.

**Event selection:** Select the first fully qualifying event per session separately for each configuration, not the most profitable future opportunity. Signal formed at close; conditional order may be canceled at the next open if it is outside the range, beyond the target, or cannot satisfy the minimum reward/cost and whole-contract constraints.

**Illustration:** Illustration only: H=20,000, L=19,950. A lower-edge rejection leads to a long fill at 19,962 with a protective stop at 19,950 and target 20,000: 38 points potential reward versus 12 points initial price risk, about 3.17R before fees/slippage. These are hypothetical levels, not a trade recommendation or measured result.

**Evaluation:** Measure target before stop before deadline from the actual entry. Report stop exits, time exits, ambiguous bars, costs, expectancy, distinct event days and continuous account paths. A target touched at any time during the day, or before entry, is not a successful trade. A high win rate alone is insufficient. Stops can gap; never cap the recorded loss retrospectively.

**Cost diagnostic:** For a simplified two-outcome trade with gross reward G, gross loss R and round-trip cost C, positive expectancy requires p>(R+C)/(G+R). Actual testing must include time exits, variable fills and account restrictions; the simple inequality is only a diagnostic.

**Excluded assumptions:** Outside-to-nearest-boundary entries are excluded following the user clarification. No ORB entry waiting until price is already beyond its target. No assumption that a 15-minute NQ price sample establishes an Ornstein-Uhlenbeck process or stable mean reversion.

Methodological background: [Andrew Lo, Harry Mamaysky and Jiang Wang (2000)](https://business.columbia.edu/sites/default/files-efs/pubfiles/19268/Lo-Mamaysky_wang_foundations.pdf), [Tim Leung and Xin Li (2015; arXiv version 3)](https://arxiv.org/pdf/1411.5062), [Tim Leung and Yerkin Kitapbayev (2017 preprint)](https://arxiv.org/pdf/1701.00875).

## Source register and evidence limits

1. Toby Crabel, Opening Range Breakout Part 4, original Stocks & Commodities publisher excerpt: https://technical.traders.com/archive/archivelogin.asp?file=%5CV07%5CC02%5CORB.pdf&src=SC . Access: public excerpt, not full paid article. Explicit inside-day/next-day ORB precedent for R4-01. Do not invent unviewed exact settings.
2. Christian Lundstrom, Day trading returns across volatility states, university working-paper abstract: https://swopec.hhs.se/umnees/abs/umnees0861.htm . S&P 500/crude futures, not direct NQ validation. General state-dependence motivation; its already tested volatility-state model is excluded from R4.
3. Carol Osler, Stop-Loss Orders and Price Cascades in Currency Markets, New York Fed staff report: https://www.newyorkfed.org/research/staff_reports/sr150.html . Original FX evidence about stop clustering/cascades. Indirect motivation for R4-02/06/07; it does not validate opening/overnight levels or prove any NQ order-flow mechanism.
4. Peter K. Clark, A Subordinated Stochastic Process Model with Finite Variance for Speculative Prices, Econometrica 41(1), 135-155: https://doi.org/10.2307/1913889 . Bibliographic record checked via publisher table of contents https://www.jstor.org/stable/i332775 ; full article not read in this selection pass. Activity-time conceptual lead for R4-04 only; require full-text review before describing exact paper mechanisms.
5. Kathryn Kaminski and Andrew Lo, When Do Stop-Loss Rules Stop Losses?, author manuscript, January 2007: https://citeseerx.ist.psu.edu/document?doi=954a65e94b6cee2abf017650e7381aacef54f8b2&repid=rep1&type=pdf . Abstract inspected; general stop-policy framework, not intraday NQ ORB proof. R4-10 is our own synthesis.

6. Concretum Research, Beat the Market: Intraday Momentum Strategy for SPY ETF: https://concretumgroup.com/wp-content/uploads/2026/02/Beat-the-Market.pdf . Public manuscript excerpt checked for current-band/VWAP trailing-stop discussion. This is SPY momentum research, not proof of these ORB extensions. Directly motivates investigating the management role of VWAP in R4-13; does not establish R4-11/12/14.

R4-03/05/08/09 and most added variants are explicitly original hypotheses/adaptations. Other sources supply varying degrees of precedent or motivation, not 31 externally validated models. No proprietary hedge-fund implementation or institutional endorsement is claimed. Mechanistic plausibility is a reason to test, not a forecast of profit. Management variants can change a payoff distribution without creating positive underlying expectancy.

## Duplicate prevention and resource policy

Before any full run, create a canonical rule registry describing feature availability, range construction, sequence states, direction, entry, stop, target, management, sizing and account semantics. Compare with the actual R1/R2/R3 rules; names and JSON hashes alone are insufficient. Exclude neutral parameter choices that disable the new rule and recover a previously tested setup.

Collapse duplicate R4 signal paths before expensive execution. Deduplicate executable configurations only when the full order schedule and execution/account policies are identical; equal entry timestamps alone are not enough for a management model. Preserve a mapping from all aliases to the single computed outcome. Different hypotheses may naturally share some individual trades; shared trades do not by themselves mean repeated strategies.

Reuse existing data preparation/features/results where compatible. No old full-grid reruns and no mandatory old benchmark jobs. Historical references from differing simulators remain labeled non-comparable; do not claim R4 superiority from an unfair comparison. A necessary bounded correctness check is distinct from a repeated parameter search, but do not use that distinction to launch old grids.

Repair common tick/execution problems and check data completeness before full runs. Resolve overnight data availability before admitting R4-02. Reject cases that require unavailable tick ordering, L2/MBO, ES or news data. Freeze finite menus and count configurations before launch; draft menus here must not silently expand after looking at results.

Use the same base costs, continuous account replay, higher-cost and timing stresses across R4. Rank standalone and actual account results separately. Reused 2023-2025 history remains development data. Event counts, parameter sensitivity and chronological selection must accompany any selected result; future/unseen observations remain necessary for independent validation.

Design status: 31 selected variants with documented novelty; model 31 has ten labelled entry subfamilies (A-J). Implementation, cross-study canonical registry, frozen counts and validated workflow remain future work. No backtest performance is claimed. See COVERAGE_CONTRACT.md for the exact meaning of exhaustive coverage and the earlier VWAP search boundary.

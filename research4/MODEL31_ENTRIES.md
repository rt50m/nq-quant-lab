# R4-31: entries inside the opening range, targeting its high or low

Updated 2026-09-04 following approval of models 1-30. Those thirty designs remain unchanged. This document expands model 31 from three to ten entry families, A-J. These are proposed tests, not tested results or ten independent edges. It supersedes only the model-31 entry section of the earlier deep-research PDF/report. No executable grid or workflow exists yet.

## Shared target and execution contract

Freeze H and L from the 09:30 through 09:44 minute-open bars in America/New_York. W=H-L must be positive. Signals and entries start at 09:45. Every actual fill must be strictly inside (L,H). Longs target H; shorts target L. Neither boundary moves later. A wick outside during a setup is allowed; an entry outside is not.

Use completed one-minute candles. A qualifying close produces an order for the next available scheduled minute open; a missing expected bar invalidates that event rather than silently delaying execution. Recheck range membership, direction, stop geometry, costs and sizing at that open. Stops are frozen from information available at signal time, rounded outward to NQ ticks, with a 1/2-tick draft buffer. A long stop must be below entry and a short stop above it. Flatten by 15:59 ET, or an earlier applicable account/session deadline. No overnight positions.

Preserve whole NQ-first/MNQ-fallback sizing, contract limits, fees/slippage, daily loss rules and continuous account replay. Risk budgets remain $50/75/100/125/150/175/200/250/300. Skip when no permitted whole-contract position fits. Never assume a stop guarantees the budgeted loss during a gap. Account-profile validation remains an implementation gate.

The default is the first qualifying *executable* event per configuration/session and at most one trade. A canceled candidate consumes its setup, not the session; a later independent setup can qualify. Do not select the day's best future entry. Reset stale states at session boundaries and discard setups with missing required observations. If simultaneous opposite signals occur, skip that timestamp. Pattern-specific selection and expiry must be deterministic.

## Location: explicitly test proximity to both boundaries

At the executable open, compute u=(entry-L)/W. For longs define v=u; for shorts v=1-u. Thus small v means near the boundary behind the trade; large v means near its destination. Draft disjoint location cells are:

| Cell | Direction-normalized position | Long example | Short example |
|---|---|---|---|
| Origin edge | 0<v<=0.25 | Near low, target high | Near high, target low |
| Interior | 0.25<v<0.75 | Inside middle half, target high | Inside middle half, target low |
| Destination edge | 0.75<=v<1 | Near high, target high | Near low, target low |

Treat these as predeclared eligibility filters and report actual distances to both boundaries. Reversal and continuation hypotheses must be visible separately. A bullish IFVG near the high is not automatically attractive: it has less remaining reward. Retain it only when the same cost and reward/risk checks pass. Structural restrictions make some family/location combinations impossible; classify those before launch instead of counting phantom tests. Do not add an overlapping all-locations optimization row; pooled diagnostics can be computed from events.

## Entry families

Long rules below have exact price-reflected short counterparts. Unless otherwise specified, pattern formation begins after 09:45. Stop references include only the observed setup through its confirming candle, never future pivots.

### 31A — Edge rejection and local recovery (retained)

A candle visits the lower edge zone and closes strictly inside. A later inside close clears the previous k completed-bar highs while remaining below the midpoint. Enter next open, target H; stop below the minimum setup low. k=1/2 is a backward breakout lookback, not an unconfirmed future pivot. Draft edge-zone width: 15/25/35% of W. This retains the original single-rejection family.

### 31B — Failed outside close, return and hold (retained)

Observe a completed close below L, followed by a close back inside and h additional consecutive inside closes. Enter next inside open toward H. Stop below the failed excursion's lowest low through confirmation. Draft h=1/2/3. The short version fails above H. This requires an outside *close*, unlike 31G's single wick excursion. Its target/hold policy differs from R4-17; keep their related origin visible.

### 31C — Midpoint reclaim and hold (retained)

At least two consecutive inside closes occur below the frozen midpoint, followed by an inside close above it and h additional inside closes above it. Enter next open toward H; stop below the reclaim/hold lows. Draft h=1/2/3. Later confirmation trades some target distance for additional evidence.

### 31D — One-minute inverse fair value gap (IFVG)

Our explicit OHLC convention: a bullish FVG first exists after bar t closes if low[t]>high[t-2], with zone [high[t-2],low[t]]. A bearish FVG exists if high[t]<low[t-2], with zone [high[t],low[t-2]]. Require three consecutive valid candles; these are chart gaps between nonadjacent bars, not evidence that no transactions occurred in the zone. No additional middle-candle condition is implied.

For a long IFVG, identify a previously completed bearish FVG. A *later* completed candle must close strictly above its full upper edge. This is the inversion; neither a wick nor a midpoint touch qualifies. For a short, a prior bullish FVG must later close below its full lower edge. Only the inverted zone with the most recent formation time is selected if several newly invert on the same candle; consume that selection without searching retrospectively for a more profitable gap.

Test two schedules separately: (1) next-open entry after inversion; (2) wait for a later candle whose range intersects the inverted zone and which closes back above its upper edge for a long, then enter next open. The short retest closes below the lower edge. Cancel a retest setup on a completed close through its far invalidation edge, its deadline, or a target touch before the retest completes. Stop below the minimum low from the three formation bars through the confirming inversion/retest candle; mirror for shorts.

Draft axes: minimum zone width 1/2/4 ticks; maximum formation-to-inversion age 3/5/10 minutes; formation window opening-only (09:30-09:44) or post-opening (>=09:45), defined by the third candle's timestamp; inversion-only/retest schedule; inversion displacement confirmation off/on. Retest expiry uses the shared setup-expiry menu, measured from inversion. The gap can form during the opening range, but inversion must be observable at or after 09:45. Location uses actual entry, with zone position retained as a diagnostic.

Definition provenance only: [edgeful's public IFVG description](https://www.tradingview.com/script/eReDWB2w-edgeful-iFVG-inverse-fair-value-gaps/) illustrates full-edge inversion and differing close/wick conventions. Our fixed candle-close convention above is the specification, not a replication of every condition in that script. This is not institutional research or evidence of profitable NQ execution.

### 31E — Displacement alone

A bullish completed candle closes above its open, has absolute body >= m times the median absolute body of the preceding 20 completed one-minute candles, body/range >= b, and closes in the top 20% of its own range. It must close inside the opening range. Enter next open toward H, stop below the signal candle's low. Mirror for shorts, requiring a close in the bottom 20%. Zero range, zero reference median or incomplete history invalidates the signal. Lookback candles can include the opening window but cannot cross the session boundary.

Draft m=1.5/2/2.5; b=0.60/0.75. This is the pure displacement test: no IFVG, swing-break, VWAP or volume requirement. The same exact displacement definition can be an explicit on/off confirmation within 31D; when off, its m/b parameters are absent. A strong candle is measurable; actual trader intent is not observed.

### 31F — Ordinary FVG pullback and rejection

A bullish FVG forms using 31D's three-candle geometry after 09:45, with its entire zone strictly inside the opening range. On a later bar, price revisits that zone and closes above its upper edge. Enter next open toward H; stop below the minimum formation-through-rejection low. Cancel on a close below the zone, a target touch before confirmation or setup expiry. Mirror a bearish FVG for shorts. Select the most recently formed eligible gap deterministically.

Draft minimum zone width 1/2/4 ticks; expiry measured from formation. This tests continuation from an ordinary gap, while 31D requires an opposite-direction gap to invert first. Do not label them equivalent merely because both use the word FVG.

### 31G — Opening-boundary wick excursion and recovery

Require the preceding completed close strictly inside. A later candle trades below L by at least d ticks but closes strictly inside; it must not close outside. Test next-open entry immediately after that recovery, or wait for a later inside close above the excursion candle's high. Target H; stop below the minimum excursion-through-confirmation low. Cancel a waiting setup on an outside close, an earlier target touch or expiry. Mirror above H toward L.

Draft d=1/2/4 ticks; immediate/recovery-high-break confirmation. This tests a wick excursion, distinct from 31B's mandatory outside close. The OHLC pattern does not establish that stop orders or liquidity were actually swept.

### 31H — Double test of an edge, then neckline break

For a long, a completed candle enters the lower edge zone and closes inside; freeze that first contact's low p1. Then require a later inside close at least r*W above p1, creating an observable separation. A subsequent candle retests within +/- epsilon*W of p1 and closes inside. Freeze the neckline as the highest high after the first contact and before the second. Only a later inside close above that neckline confirms; enter next open toward H. Stop below the minimum low from first contact through confirmation. Require that the neckline itself is inside and cancel on an intervening outside close or target touch. Mirror for shorts.

Draft edge zone 15/25/35%; separation r=0.10/0.20; tolerance epsilon=0.025/0.05. Two temporally separated visits distinguish this from 31A. No retrospectively selected optimal pivots. First eligible contact starts the setup; failed/expired setups must reset before another first contact.

### 31I — VWAP reclaim inside the opening range

Compute cumulative RTH typical-price VWAP using observed volume. Require two consecutive inside closes below their contemporaneous VWAP, followed by an inside reclaim close above VWAP and h additional inside closes above their contemporaneous VWAP. VWAP must remain strictly inside (L,H) throughout the reclaim/hold. Enter next open toward H; stop below the minimum reclaim/hold low. Mirror for shorts. Missing/zero cumulative volume invalidates the event.

Draft h=1/2/3. This is a changing volume-weighted reference, unlike 31C's fixed midpoint. R4-12 uses a VWAP sequence followed by an ORB; this family enters inside and exits at the boundary. Cache shared features and audit the full policy for duplicates.

### 31J — Tight box inside the range, then directional escape

At each candidate signal time, freeze a box from the preceding n completed candles, all with their full high-low intervals strictly inside (L,H). Its width must be positive and <= q*W. A later signal candle closes above the box high but below H for a long, or below its low but above L for a short. Enter next open toward the matching opening boundary. Stop beyond the opposite frozen box edge. The signal candle is excluded from box construction.

Draft n=3/5/8; q=0.10/0.20/0.30. This box is inside the opening range; R4-09's flag is outside. Distinct location and target policies must remain in the registry.

## Finite coverage and selection discipline

Common draft axes: direction both/long-only/short-only; three applicable location cells; minimum gross target-distance/stop-distance 1/1.5/2; signal cutoff 10:30/11:30/13:00 ET; maximum hold 30/60/120 minutes subject to the hard flat time; stop buffer 1/2 ticks; nine existing risk budgets. Require positive net reward after modeled costs as an additional fixed eligibility condition; calculate the gross ratio and cost estimate at the executable open.

Setup expiry 5/10/20 minutes applies to A/B/C/D-retest/F/G-confirmed/H/I. A starts at edge contact, B at the first outside close, C at the first of its qualifying below-midpoint closes, H at first contact, I at the first below-VWAP close. E, D-inversion-only, G-immediate and J have no delayed setup-expiry parameter. D has its separate formation-to-inversion age. Document reset and first-event behavior in the executable state machines before counting.

Take every compatible product of the frozen family-specific and shared menus. Do not multiply E's displacement settings into families that do not use displacement, D's retest expiry into its immediate branch, or delayed confirmation into immediate 31G. Deduplicate equivalent full policies while preserving aliases and trial accounting. No claim of exact total coverage until an executable manifest publishes raw, invalid, duplicate, unique and completed counts. Do not launch a grid just because the previous study took six minutes.

Keep direct IFVG, displacement-only and IFVG-with-displacement results separately identifiable. Additional arbitrary mixes of every family are outside this declared scope. These ten families are a broad finite entry study, not every indicator or every possible setting. Compare against the actual earlier rule registry before running; reject prior exact strategies rather than renaming them.

Measure net expectancy, target-before-stop-before-deadline, time exits, event days, drawdown and continuous prop-account survival. Record how many candidates were canceled, including poor geometry or cost failures. A boundary touch before entry is not a win. If stop and target occur within the same minute with unknown ordering, flag ambiguity and apply the declared conservative execution policy; do not manufacture tick ordering. A plausible entry name and a high touch rate are insufficient evidence of an edge. Reused historical data remains development data; report selection uncertainty across all trials.

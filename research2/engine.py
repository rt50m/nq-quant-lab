"""Causal bar execution and account path simulation; no post-hoc loss clipping."""
import math
import numpy as np
from numba import njit


@njit(cache=True)
def quantity(distance, risk, slip, nq_comm, mnq_comm, max_nq, max_mnq):
    # Entry already includes its adverse fill. Budget stop distance + exit slip + fees.
    q = min(max_nq, int(risk // ((distance + slip) * 20 + 2*nq_comm)))
    if q >= 1:
        return q, 20., nq_comm
    q = min(max_mnq, int(risk // ((distance + slip) * 2 + 2*mnq_comm)))
    return q, 2., mnq_comm


@njit(cache=True)
def floor_after_close(previous_floor, peak_close, max_loss, locked_floor):
    return max(previous_floor, min(locked_floor, peak_close - max_loss))


@njit(cache=True)
def execute_day(bars, entry_minute, side, distance, target_r, exit_minute, trailing,
                risk, slip, nq_comm, mnq_comm, max_nq, max_mnq,
                daily_limit, account_allowance, account_buffer):
    # Output: pnl, min liquidation pnl, exit minute, reason, qty, point value,
    # ambiguous exits, data gap, actual planned risk. Reasons 1 stop,2 target,
    # 3 time,4 personal/DLL,5 account protection,6 no size,7 missing data.
    out = np.zeros(9)
    out[2] = -1
    if entry_minute <= -2:
        # Negative encoding preserves the first missing signal minute so an
        # irrelevant gap AFTER this configuration's exit cannot invalidate it.
        if -entry_minute-2 < exit_minute:
            out[3] = 7;out[7] = 1
        return out
    if entry_minute < 0 or entry_minute >= exit_minute or not np.isfinite(distance):
        return out
    if distance <= 0 or not np.isfinite(bars[entry_minute, 0]):
        out[3] = 7; out[7] = 1
        return out
    # Round stop distance up to a tradable NQ tick.
    distance = math.ceil(distance*4)/4
    entry = bars[entry_minute, 0] + side*slip
    budget = min(risk, daily_limit, max(0., account_allowance-account_buffer))
    q, pv, commission = quantity(distance, budget, slip, nq_comm, mnq_comm, max_nq, max_mnq)
    if q < 1:
        out[3] = 6
        return out
    value = q*pv; fees = q*commission*2
    out[4] = q; out[5] = pv
    out[8] = (distance+slip)*value+fees
    stop = entry-side*distance
    # Targets are limit fills. No favorable gap-price improvement is credited.
    target = entry+side*math.ceil(distance*target_r*4)/4 if target_r > 0 else side*1e12
    worst = -fees-slip*value
    gap_seen = 0
    for t in range(entry_minute, exit_minute+1):
        o,h,l,c = bars[t,0],bars[t,1],bars[t,2],bars[t,3]
        if not np.isfinite(o):
            gap_seen = 1
            continue
        # Translate money limits to liquidation levels. Include projected exit fees/slip.
        daily_stop = entry-side*max(0., (daily_limit-fees-slip*value)/value)
        account_stop = entry-side*max(0., (account_allowance-account_buffer-fees-slip*value)/value)
        active_stop = stop; reason = 1
        if side*(daily_stop-active_stop) > 0:
            active_stop = daily_stop; reason = 4
        if side*(account_stop-active_stop) > 0:
            active_stop = account_stop; reason = 5
        # Round protective levels towards entry so rounding cannot loosen limits.
        active_stop = math.ceil(active_stop*4)/4 if side == 1 else math.floor(active_stop*4)/4
        stop_gap = side*(o-active_stop) <= 0
        target_gap = side*(o-target) >= 0 and target_r > 0
        hit_stop = l <= active_stop if side == 1 else h >= active_stop
        hit_target = (h >= target if side == 1 else l <= target) and target_r > 0
        price = 0.; why = 0
        # The open is chronologically known before intrabar highs/lows.
        if stop_gap:
            price=o-side*slip; why=reason
        elif target_gap:
            price=target; why=2
        elif t == exit_minute:
            price=o-side*slip; why=3
        elif hit_stop:
            price=active_stop-side*slip; why=reason
            if hit_target:
                out[6] += 1
        elif hit_target:
            price=target; why=2
        if why:
            pnl=(price-entry)*side*value-fees
            # Before a target, the adverse extreme may have occurred first.
            # Bound it by the active stop; open/time exits do not use future extremes.
            if why == 2 and not target_gap:
                adverse=max(l,active_stop) if side == 1 else min(h,active_stop)
                worst=min(worst,(adverse-entry)*side*value-fees-slip*value)
            worst=min(worst,pnl)
            out[0]=pnl;out[1]=worst;out[2]=t;out[3]=why;out[7]=gap_seen
            return out
        adverse=l if side == 1 else h
        worst=min(worst,(adverse-entry)*side*value-fees-slip*value)
        # A new trailing level becomes active NEXT BAR, never retroactively.
        if trailing == 1 and side*(c-entry) >= distance:
            stop=max(stop,entry) if side == 1 else min(stop,entry)
    # Never invent a close at an earlier bar when the forced-exit quote is missing.
    out[3]=7;out[7]=1;out[0]=0;out[1]=worst
    return out


@njit(cache=True)
def simulate(bars, entries, sides, atr, exits, risk, stop_fraction, target_r, trailing,
             slip, nq_comm, mnq_comm, start, max_loss, locked_floor,
             daily_limit, buffer, max_nq, max_mnq, enforce_account):
    n=len(entries)
    results=np.zeros((n, 9))
    results[:,2]=-1
    balance=start; peak=start; floor=start-max_loss
    failed=0; fail_day=-1; protection=0
    for d in range(n):
        if failed and enforce_account:
            continue
        allowance=balance-floor if enforce_account else 1e12
        r=execute_day(bars[d],int(entries[d]),int(sides[d]),atr[d]*stop_fraction,
                      target_r,int(exits[d]),trailing,risk,slip,nq_comm,mnq_comm,
                      max_nq,max_mnq,daily_limit,allowance,buffer)
        results[d]=r
        if r[3] == 5:
            protection+=1
        if r[4] > 0 and r[3] != 7:
            # Include intratrade liquidation equity, not just closed-trade balance.
            if balance+r[1] <= floor:
                failed=1;fail_day=d
            balance+=r[0]
            peak=max(peak,balance)
            floor=floor_after_close(floor,peak,max_loss,locked_floor)
        if r[7] > 0 and enforce_account:
            # Unknown trade path stops the account replay; never continue from invented P&L.
            failed=2;fail_day=d
    return results, balance, failed, fail_day, protection

"""Numba event replay. One position at a time, multiple causal re-entries per day."""
from __future__ import annotations
import math, numpy as np
from numba import njit

@njit(cache=True)
def outward_stop(value,side):
    return math.floor(value*4+1e-8)/4 if side==1 else math.ceil(value*4-1e-8)/4
@njit(cache=True)
def inward_target(value,side):
    return math.floor(value*4+1e-8)/4 if side==1 else math.ceil(value*4-1e-8)/4

@njit(cache=True)
def outcomes(a,atr,events,stop_atr,target_r,hold,slip,hard_flat=389):
    # columns day, signal_minute, entry_minute, exit_minute, side, pnl_points, worst_points, stop_points
    n=len(events);out=np.full((n,8),np.nan)
    for i in range(n):
        d=int(events[i,0]);m=int(events[i,1]);side=int(events[i,2]);entry_m=m+1
        if entry_m>=hard_flat or not np.isfinite(a[d,entry_m]).all() or not np.isfinite(atr[d]):continue
        o=a[d,entry_m,0];entry=o+side*slip
        stop=outward_stop(entry-side*stop_atr*atr[d],side);dist=side*(entry-stop)
        if dist<=0:continue
        target=np.nan
        if target_r>0:
            target=inward_target(entry+side*target_r*dist,side)
            if side*(target-entry)<=0:continue
        deadline=min(hard_flat,entry_m+hold)
        exit_px=np.nan;exit_m=-1;worst=0.0
        for k in range(entry_m,deadline+1):
            if not np.isfinite(a[d,k]).all():break
            oo,hh,ll=a[d,k,0],a[d,k,1],a[d,k,2]
            # Conservative opening gap handling.
            if side*(oo-stop)<=0:
                exit_px=oo-side*slip;exit_m=k;break
            if np.isfinite(target) and side*(oo-target)>=0:
                exit_px=target;exit_m=k;break
            if k==deadline:
                exit_px=oo-side*slip;exit_m=k;break
            stop_hit=ll<=stop if side==1 else hh>=stop
            target_hit=np.isfinite(target) and (hh>=target if side==1 else ll<=target)
            adverse=(ll-side*slip) if side==1 else (hh-side*slip)
            w=side*(adverse-entry)
            if w<worst:worst=w
            if stop_hit:
                exit_px=stop-side*slip;exit_m=k;break
            if target_hit:
                exit_px=target;exit_m=k;break
        if exit_m<0:continue
        pnl=side*(exit_px-entry)
        if pnl<worst:worst=pnl
        out[i,0]=d;out[i,1]=m;out[i,2]=entry_m;out[i,3]=exit_m;out[i,4]=side
        out[i,5]=pnl;out[i,6]=worst;out[i,7]=dist
    return out

@njit(cache=True)
def select(outcomes,window_start,window_end,direction,max_trades=12):
    # Keep earliest available trigger, never overlap positions, and permit re-entry after an exit.
    count=0;last_day=-1;available=-1;used=0
    for i in range(len(outcomes)):
        if not np.isfinite(outcomes[i,0]):continue
        d=int(outcomes[i,0]);m=int(outcomes[i,1]);side=int(outcomes[i,4])
        if d!=last_day:last_day=d;available=-1;used=0
        if m<window_start or m>=window_end or used>=max_trades:continue
        if direction!=0 and side!=direction:continue
        if m<=available:continue
        count+=1;available=int(outcomes[i,3]);used+=1
    chosen=np.empty((count,8));j=0;last_day=-1;available=-1;used=0
    for i in range(len(outcomes)):
        if not np.isfinite(outcomes[i,0]):continue
        d=int(outcomes[i,0]);m=int(outcomes[i,1]);side=int(outcomes[i,4])
        if d!=last_day:last_day=d;available=-1;used=0
        if m<window_start or m>=window_end or used>=max_trades:continue
        if direction!=0 and side!=direction:continue
        if m<=available:continue
        chosen[j]=outcomes[i];j+=1;available=int(outcomes[i,3]);used+=1
    return chosen

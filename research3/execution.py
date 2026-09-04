"""Next-open, multi-entry execution. Prices are points; fees/caps are whole contracts.

Commands are stamped at the executable minute, never at the signal minute.
NaN means keep current exposure; zero means exit. Dynamic stops are also delayed.
Daily loss includes realized P&L, entry fees and marked liquidation of open exposure.
"""
import math
import numpy as np
from numba import njit

@njit(cache=True)
def size(distance, budget, slip, max_nq, max_mnq, nq_fee, mnq_fee):
    if budget<=0 or distance<=0: return 0,2.,mnq_fee
    q=min(max_nq,int(budget//((distance+slip)*20+2*nq_fee)))
    if q>=1: return q,20.,nq_fee
    return min(max_mnq,int(budget//((distance+slip)*2+2*mnq_fee))),2.,mnq_fee

# Daily columns: net, worst liquidation P&L, episodes, wins$, losses$, win count,
# ambiguity, unknown path, size skips, blocked commands, entries, max qty, nq entries,
# mnq entries, protection exits, last exit minute, gross points (one-unit diagnostic),
# long net, short net, closed-equity intraday drawdown, max episode planned risk.
@njit(cache=True)
def replay(bars, commands, stops, targets, deadlines, eligible, atr, risk, stop_atr,
           max_entries, slip, nq_fee, mnq_fee, start, loss_limit, locked_floor,
           daily_limit, buffer, max_nq, max_mnq, enforce):
    n=len(bars);out=np.zeros((n,21));out[:,15]=-1
    balance=start;peak=start;floor=start-loss_limit;status=0;failed_day=-1
    for d in range(n):
        if not eligible[d] or (enforce and status!=0): continue
        day=0.;worst=0.;q=0;side=0;pv=2.;fee=mnq_fee;entry=0.;stop=0.;target=0.
        deadline=389;entries=0;episode=0.;episode_entry=0.;locked=False;day_peak=0.
        for t in range(390):
            o,h,l,c=bars[d,t,0],bars[d,t,1],bars[d,t,2],bars[d,t,3]
            if not np.isfinite(o):
                # A missing observation is encountered in time; don't pre-exclude a day
                # using its later missing bars. Stop the replay instead of fabricating fills.
                if q or np.isinf(commands[d,t]):
                    out[d,7]=1;locked=True
                    if enforce: status=2;failed_day=d
                    break
                continue
            # A completed previous bar can change the stop for this bar.
            if q and np.isfinite(stops[d,t]):
                candidate=stops[d,t]
                stop=max(stop,candidate) if side==1 else min(stop,candidate)
            cmd=commands[d,t]
            why=0;price=0.;active=stop;protection=False
            if q:
                value=q*pv
                allowance=balance-floor-buffer if enforce else 1e12
                # day already contains entry and partial-exit fees/P&L.
                limit=min(daily_limit,allowance)
                protected=entry+side*(-limit-day+q*fee+slip*value)/value
                protected=math.ceil(protected*4)/4 if side==1 else math.floor(protected*4)/4
                if side*(protected-active)>0: active=protected;protection=True
                gapstop=side*(o-active)<=0
                gaptarget=np.isfinite(target) and side*(o-target)>=0
                if gapstop: price=o-side*slip;why=1
                elif gaptarget: price=target;why=2
                elif t>=deadline or t==389: price=o-side*slip;why=3
                elif np.isfinite(cmd) and (cmd==0 or cmd*side<0): price=o-side*slip;why=4
                if why:
                    pnl=(price-entry)*side*value-q*fee
                    day+=pnl;episode+=pnl;worst=min(worst,day)
                    out[d,2]+=1;out[d,3]+=max(episode,0);out[d,4]+=min(episode,0)
                    out[d,5]+=episode>0;out[d,15]=t
                    out[d,16]+=(price-episode_entry)*side
                    out[d,17 if side==1 else 18]+=episode
                    if why==1 and protection:out[d,14]+=1;locked=True
                    q=0;episode=0.
            # Gap losses can breach hard rules. Never clip their realized amount.
            if day<=-daily_limit or (enforce and balance+day<=floor):
                locked=True
                if enforce and balance+day<=floor:status=1;failed_day=d
            # No same-minute re-entry after a protective/target/time exit. Reversals
            # explicitly commanded at the open may close and open on that known quote.
            can_enter=(why==0 or why==4) and t<389 and t<int(deadlines[d,t])
            if np.isfinite(cmd) and cmd!=0 and can_enter:
                wanted=1 if cmd>0 else -1
                if locked or (q==0 and entries>=max_entries):out[d,9]+=1
                elif q==0:
                    fill=o+wanted*slip
                    dist=abs(fill-stops[d,t]) if stop_atr==0 and np.isfinite(stops[d,t]) else atr[d]*stop_atr
                    dist=math.ceil(dist*4)/4
                    allowance=balance+day-floor-buffer if enforce else 1e12
                    budget=min(risk*abs(cmd),daily_limit+day,allowance)
                    nq,npv,nfee=size(dist,budget,slip,max_nq,max_mnq,nq_fee,mnq_fee)
                    if nq==0:out[d,8]+=1
                    else:
                        q=nq;pv=npv;fee=nfee;side=wanted;entry=fill;episode_entry=fill
                        stop=entry-side*dist
                        target=targets[d,t];deadline=int(deadlines[d,t])
                        day-=q*fee;episode=-q*fee;entries+=1
                        out[d,10]+=1;out[d,11]=max(out[d,11],q)
                        out[d,12 if pv==20 else 13]+=1
                        out[d,20]=max(out[d,20],(dist+slip)*q*pv+2*q*fee)
                elif wanted==side:
                    # Same-side resize retains average entry and trades only the delta.
                    # Keep the instrument until flat; no implicit NQ/MNQ conversion.
                    dist=max(.25,side*(o+side*slip-stop))
                    marked=side*(o-entry)*q*pv-q*fee-slip*q*pv
                    allowance=balance+day+marked-floor-buffer if enforce else 1e12
                    budget=min(risk*abs(cmd),daily_limit+day+marked,allowance)
                    cap=max_nq if pv==20 else max_mnq
                    desired=max(0,min(cap,int(max(0.,budget)//((dist+slip)*pv+2*fee))))
                    delta=desired-q
                    if delta>0:
                        fill=o+side*slip
                        entry=(q*entry+delta*fill)/desired
                        day-=delta*fee;episode-=delta*fee
                    elif delta<0:
                        pnl=(o-side*slip-entry)*side*(-delta)*pv-(-delta)*fee
                        day+=pnl;episode+=pnl
                    q=desired;out[d,11]=max(out[d,11],q)
                    if q==0:
                        out[d,2]+=1;out[d,3]+=max(episode,0);out[d,4]+=min(episode,0)
                        out[d,5]+=episode>0;out[d,15]=t
                        out[d,17 if side==1 else 18]+=episode;episode=0.
            if q:
                value=q*pv;active=stop;protection=False
                allowance=balance-floor-buffer if enforce else 1e12
                limit=min(daily_limit,allowance)
                protected=entry+side*(-limit-day+q*fee+slip*value)/value
                protected=math.ceil(protected*4)/4 if side==1 else math.floor(protected*4)/4
                if side*(protected-active)>0:active=protected;protection=True
                hitstop=l<=active if side==1 else h>=active
                hittarget=np.isfinite(target) and (h>=target if side==1 else l<=target)
                if hitstop or hittarget:
                    if hitstop:
                        # A newly tightened stop already beyond the open fills at open.
                        price=(min(o,active) if side==1 else max(o,active))-side*slip
                        if hittarget:out[d,6]+=1
                    else:price=target
                    adverse=max(l,active) if side==1 else min(h,active)
                    if not hitstop:worst=min(worst,day+(adverse-entry)*side*value-q*fee-slip*value)
                    pnl=(price-entry)*side*value-q*fee;day+=pnl;episode+=pnl
                    worst=min(worst,day)
                    out[d,2]+=1;out[d,3]+=max(episode,0);out[d,4]+=min(episode,0)
                    out[d,5]+=episode>0;out[d,15]=t
                    out[d,16]+=(price-episode_entry)*side;out[d,17 if side==1 else 18]+=episode
                    if hitstop and protection:out[d,14]+=1;locked=True
                    q=0;episode=0.
                else:
                    adverse=l if side==1 else h
                    worst=min(worst,day+(adverse-entry)*side*value-q*fee-slip*value)
            day_peak=max(day_peak,day);out[d,19]=min(out[d,19],day-day_peak)
            if day<=-daily_limit:locked=True
            if enforce and balance+worst<=floor:status=1;failed_day=d;locked=True
            if enforce and status:break
        out[d,0]=day;out[d,1]=worst
        # Unknown/unliquidated exposure cannot be used to advance account equity.
        if q or out[d,7]:
            out[d,7]=1
            if enforce and status==0:status=2;failed_day=d
        if not out[d,7]:
            balance+=day;peak=max(peak,balance)
            floor=max(floor,min(locked_floor,peak-loss_limit))
    return out,balance,status,failed_day

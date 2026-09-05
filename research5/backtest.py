"""Small extracted-strategy simulator; hot path uses NumPy and one trade per day."""
from __future__ import annotations
import numpy as np
from discover import mask_rule

NQ_POINT=20.0; MNQ_POINT=2.0; NQ_COMM=3.50; MNQ_COMM=1.00; MAX_NQ=4; MAX_MNQ=40
SLIP_PER_SIDE=0.25


def size(stop_points, risk=300.0):
    if not np.isfinite(stop_points) or stop_points <= 0: return None
    nq=max(0,min(MAX_NQ,int(risk//(stop_points*NQ_POINT))))
    if nq>=1: return ('NQ',nq,NQ_POINT,NQ_COMM)
    mnq=max(0,min(MAX_MNQ,int(risk//(stop_points*MNQ_POINT))))
    if mnq>=1:return ('MNQ',mnq,MNQ_POINT,MNQ_COMM)
    return None


def _mdd(pnls):
    if not len(pnls): return 0.0
    eq=np.r_[0.0,np.cumsum(pnls)]
    peak=np.maximum.accumulate(eq)
    return float(np.min(eq-peak))


def simulate(ds, rule, stop_atr, target_r, hold, risk=300.0):
    X=ds['X']; names=ds['feature_names']; rth=ds['rth']; atr=ds['atr']
    rulemask=mask_rule(X,names,rule.conditions)
    daycol=X[:,names.index('day_index')].astype(int); mincol=X[:,names.index('minute')].astype(int)
    yearcol=X[:,names.index('year')].astype(int)
    # Freeze signal validity to the rule's discovery horizon; execution settings do not alter the rule.
    eligible=np.flatnonzero(rulemask & np.isin(yearcol,[2023,2024,2025]))
    trades=[]; used=set()
    for ix in eligible:
        d=int(daycol[ix]); m=int(mincol[ix]);
        if d in used or m+1>=390: continue
        entry=float(rth[d,m+1,0]); a=float(atr[d])
        if not np.isfinite(entry+a) or a<=0: continue
        stop_points=stop_atr*a; sz=size(stop_points,risk)
        if sz is None: continue
        symbol,qty,point,comm=sz; side=rule.direction
        stop=entry-side*stop_points; target=entry+side*stop_points*target_r
        end=min(389,m+hold)
        exit_px=None; reason='TIME'; exit_m=end
        for j in range(m+1,end+1):
            hi=float(rth[d,j,1]);lo=float(rth[d,j,2])
            stop_hit=lo<=stop if side==1 else hi>=stop
            target_hit=hi>=target if side==1 else lo<=target
            if stop_hit: exit_px=stop;reason='STOP';exit_m=j;break
            if target_hit: exit_px=target;reason='TARGET';exit_m=j;break
        if exit_px is None: exit_px=float(rth[d,end,3])
        gross=side*(exit_px-entry)*point*qty
        costs=(2*SLIP_PER_SIDE*point*qty)+(comm*qty)
        pnl=gross-costs
        trades.append((d,int(yearcol[ix]),m,exit_m,side,pnl,reason,qty,1 if symbol=='NQ' else 0))
        used.add(d)
    if not trades:return None
    t=np.array(trades,dtype=object); pnl=t[:,5].astype(float)
    wins=pnl[pnl>0];loss=-pnl[pnl<0]
    pf=float(wins.sum()/loss.sum()) if loss.sum()>0 else (99.0 if wins.sum()>0 else 0.0)
    out={'trades':len(pnl),'net_profit':float(pnl.sum()),'profit_factor':pf,'win_rate':float((pnl>0).mean()),'max_drawdown':_mdd(pnl),'avg_trade':float(pnl.mean())}
    for yr in (2023,2024,2025):
        k=t[:,1].astype(int)==yr; z=pnl[k]; w=z[z>0]; l=-z[z<0]
        out[f'net_{yr}']=float(z.sum()) if len(z) else 0.0
        out[f'pf_{yr}']=float(w.sum()/l.sum()) if l.sum()>0 else (99.0 if w.sum()>0 else 0.0)
        out[f'trades_{yr}']=int(k.sum())
    return out

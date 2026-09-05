"""Sizing optimization: fixed contracts and fixed-dollar risk, ranked only by profit under $2k intratrade DD."""
from __future__ import annotations
import numpy as np
from numba import njit
from registry import config

@njit(cache=True)
def metrics_for_pnl(pnl,worst,years):
    n=len(pnl);eq=0.0;peak=0.0;mdd=0.0;worst_day=0.0
    net23=0.0;net24=0.0;net25=0.0;gp=0.0;gl=0.0
    last=-1;dayp=0.0
    # outcomes are chronological; worst is trade liquidation P&L relative to trade start.
    for i in range(n):
        d=int(years[i,0]);yr=int(years[i,1])
        if d!=last:
            if last>=0 and dayp<worst_day:worst_day=dayp
            last=d;dayp=0.0
        candidate=eq+worst[i]-peak
        if candidate<mdd:mdd=candidate
        eq+=pnl[i];dayp+=pnl[i]
        if eq>peak:peak=eq
        dd=eq-peak
        if dd<mdd:mdd=dd
        if pnl[i]>0:gp+=pnl[i]
        elif pnl[i]<0:gl-=pnl[i]
        if yr==2023:net23+=pnl[i]
        elif yr==2024:net24+=pnl[i]
        elif yr==2025:net25+=pnl[i]
    if last>=0 and dayp<worst_day:worst_day=dayp
    pf=gp/gl if gl>0 else (99.0 if gp>0 else 0.0)
    return eq,mdd,pf,worst_day,net23,net24,net25

@njit(cache=True)
def fixed_risk_eval(trades,years,budgets,slip,nq_pv,mnq_pv,nq_comm,mnq_comm,max_nq,max_mnq,dd_cap):
    best=np.full(9,np.nan);best_net=-1e100
    for b in budgets:
        n=len(trades);pnl=np.zeros(n);worst=np.zeros(n);ok=0
        for i in range(n):
            stop=trades[i,7]
            nq_risk=(stop+slip)*nq_pv+nq_comm
            mnq_risk=(stop+slip)*mnq_pv+mnq_comm
            qnq=min(max_nq,int(b//nq_risk));qmnq=min(max_mnq,int(b//mnq_risk))
            exp_nq=qnq*nq_pv;exp_mnq=qmnq*mnq_pv
            if exp_nq<=0 and exp_mnq<=0:
                pnl[i]=0;worst[i]=0;continue
            # Choose the greatest point-value exposure that fits the budget; ties prefer NQ's lower equivalent commission.
            if exp_nq>=exp_mnq:
                q=qnq;pv=nq_pv;comm=nq_comm
            else:
                q=qmnq;pv=mnq_pv;comm=mnq_comm
            ok+=1;pnl[i]=trades[i,5]*pv*q-comm*q;worst[i]=trades[i,6]*pv*q-comm*q
        if ok==0:continue
        m=metrics_for_pnl(pnl,worst,years)
        if m[1]>-dd_cap and m[0]>best_net:
            best_net=m[0];best[0]=b;best[1]=ok
            for k in range(7):best[k+2]=m[k]
    return best

def evaluate(trades,dates):
    g=config();cost=g['costs'];cap=g['objective']['max_drawdown']
    if len(trades)==0:return None
    days=trades[:,0].astype(int);yrs=np.array([int(str(dates[d])[:4]) for d in days],dtype=np.int64)
    dy=np.c_[days,yrs].astype(np.float64)
    best={'mode':None,'net_profit':-1e100}
    for symbol,pv,comm,limit in [('NQ',cost['nq_point_value'],cost['nq_round_trip_commission'],cost['max_nq']),
                                 ('MNQ',cost['mnq_point_value'],cost['mnq_round_trip_commission'],cost['max_mnq'])]:
        pnl1=trades[:,5]*pv-comm;worst1=trades[:,6]*pv-comm
        m=metrics_for_pnl(pnl1.astype(float),worst1.astype(float),dy)
        if m[1]>=0:q=limit
        else:q=min(limit,int((cap-1e-9)//abs(m[1])))
        if q>=1:
            mm=metrics_for_pnl((pnl1*q).astype(float),(worst1*q).astype(float),dy)
            if mm[1]>-cap and mm[0]>best['net_profit']:
                best={'mode':'FIXED_QTY','symbol':symbol,'quantity':q,'risk_budget':None,'trades':len(trades),
                      'net_profit':mm[0],'max_drawdown':mm[1],'profit_factor':mm[2],'worst_day':mm[3],
                      'net_2023':mm[4],'net_2024':mm[5],'net_2025':mm[6]}
    budgets=np.array(g['risk_budgets'],dtype=np.float64)
    fr=fixed_risk_eval(trades,dy,budgets,cost['slippage_per_side_points'],cost['nq_point_value'],cost['mnq_point_value'],
                       cost['nq_round_trip_commission'],cost['mnq_round_trip_commission'],cost['max_nq'],cost['max_mnq'],cap)
    if np.isfinite(fr[0]) and fr[2]>best['net_profit']:
        best={'mode':'FIXED_RISK','symbol':'BEST_NQ_OR_MNQ_PER_TRADE','quantity':None,'risk_budget':float(fr[0]),'trades':int(fr[1]),
              'net_profit':float(fr[2]),'max_drawdown':float(fr[3]),'profit_factor':float(fr[4]),'worst_day':float(fr[5]),
              'net_2023':float(fr[6]),'net_2024':float(fr[7]),'net_2025':float(fr[8])}
    if best['mode'] is None:return None
    best['profit_to_dd']=best['net_profit']/abs(best['max_drawdown']) if best['max_drawdown']<0 else 999.0
    best['pass_scale']=bool(best['net_profit']>=g['objective']['min_net_profit'] and best['max_drawdown']>-cap)
    return best

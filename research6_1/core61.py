from __future__ import annotations
from pathlib import Path
import json, math
import numpy as np
from numba import njit

ROOT=Path(__file__).resolve().parent

def cfg(): return json.loads((ROOT/'config61.json').read_text())

def year_mask(dates, trades, year):
    days=trades[:,0].astype(int)
    return np.array([int(str(dates[d])[:4])==year for d in days],dtype=bool)

@njit(cache=True)
def outward_stop(value,side):
    return math.floor(value*4+1e-8)/4 if side==1 else math.ceil(value*4-1e-8)/4
@njit(cache=True)
def inward_target(value,side):
    return math.floor(value*4+1e-8)/4 if side==1 else math.ceil(value*4-1e-8)/4

# 14 columns: day,signal,entry,exit,side,pnl_pts,worst_pts,stop_dist,mfe_pts,mae_pts,reason,hold,signal_index,ambiguous
# reason: 1 stop, 2 target, 3 time/progress, 4 breakeven/trailing stop
@njit(cache=True)
def enriched_outcomes(a,atr,events,stop_atr,target_r,hold,slip,hard_flat=389,
                      be_trigger_r=0.0,trail_activate_r=0.0,trail_distance_r=0.0,
                      progress_minutes=0,progress_mfe_r=0.0):
    n=len(events);out=np.full((n,14),np.nan)
    for i in range(n):
        d=int(events[i,0]);m=int(events[i,1]);side=int(events[i,2]);entry_m=m+1
        if entry_m>=hard_flat or not np.isfinite(a[d,entry_m]).all() or not np.isfinite(atr[d]):continue
        entry=a[d,entry_m,0]+side*slip
        initial_stop=outward_stop(entry-side*stop_atr*atr[d],side);dist=side*(entry-initial_stop)
        if dist<=0:continue
        target=np.nan
        if target_r>0:
            target=inward_target(entry+side*target_r*dist,side)
            if side*(target-entry)<=0:continue
        deadline=min(hard_flat,entry_m+hold);stop=initial_stop
        exit_px=np.nan;exit_m=-1;reason=0;worst=0.0;mfe=0.0;mae=0.0;ambiguous=0
        pending_progress=False
        for k in range(entry_m,deadline+1):
            if not np.isfinite(a[d,k]).all():break
            oo,hh,ll,cc=a[d,k,0],a[d,k,1],a[d,k,2],a[d,k,3]
            if side*(oo-stop)<=0:
                exit_px=oo-side*slip;exit_m=k;reason=4 if side*(stop-initial_stop)>0 else 1;break
            if np.isfinite(target) and side*(oo-target)>=0:
                exit_px=target;exit_m=k;reason=2;break
            if pending_progress or k==deadline:
                exit_px=oo-side*slip;exit_m=k;reason=3;break
            fav=(hh-entry) if side==1 else (entry-ll)
            adv=(ll-side*slip-entry) if side==1 else (entry-(hh-side*slip))
            if fav>mfe:mfe=fav
            if adv<mae:mae=adv
            if adv<worst:worst=adv
            stop_hit=ll<=stop if side==1 else hh>=stop
            target_hit=np.isfinite(target) and (hh>=target if side==1 else ll<=target)
            if stop_hit and target_hit:ambiguous=1
            if stop_hit:
                exit_px=stop-side*slip;exit_m=k;reason=4 if side*(stop-initial_stop)>0 else 1;break
            if target_hit:
                exit_px=target;exit_m=k;reason=2;break
            # Management changes are based only on the completed candle and become active next minute.
            mfe_r=mfe/dist
            if be_trigger_r>0 and mfe_r>=be_trigger_r:
                candidate=outward_stop(entry,side)
                if side==1:stop=max(stop,candidate)
                else:stop=min(stop,candidate)
            if trail_activate_r>0 and trail_distance_r>0 and mfe_r>=trail_activate_r:
                extreme=entry+side*mfe
                candidate=outward_stop(extreme-side*trail_distance_r*dist,side)
                if side==1:stop=max(stop,candidate)
                else:stop=min(stop,candidate)
            if progress_minutes>0 and (k-entry_m+1)>=progress_minutes and mfe_r<progress_mfe_r:
                pending_progress=True
        if exit_m<0:continue
        pnl=side*(exit_px-entry)
        if pnl<worst:worst=pnl
        out[i,0]=d;out[i,1]=m;out[i,2]=entry_m;out[i,3]=exit_m;out[i,4]=side
        out[i,5]=pnl;out[i,6]=worst;out[i,7]=dist;out[i,8]=mfe;out[i,9]=mae
        out[i,10]=reason;out[i,11]=exit_m-entry_m;out[i,12]=i;out[i,13]=ambiguous
    return out

@njit(cache=True)
def select61(out,eligible,window_start,window_end,direction,max_trades,cooldown):
    count=0;last_day=-1;available=-1;used=0
    for i in range(len(out)):
        if not eligible[i] or not np.isfinite(out[i,0]):continue
        d=int(out[i,0]);m=int(out[i,1]);side=int(out[i,4])
        if d!=last_day:last_day=d;available=-1;used=0
        if m<window_start or m>=window_end or used>=max_trades:continue
        if direction!=0 and side!=direction:continue
        if m<=available:continue
        count+=1;available=int(out[i,3])+cooldown;used+=1
    chosen=np.empty((count,out.shape[1]));j=0;last_day=-1;available=-1;used=0
    for i in range(len(out)):
        if not eligible[i] or not np.isfinite(out[i,0]):continue
        d=int(out[i,0]);m=int(out[i,1]);side=int(out[i,4])
        if d!=last_day:last_day=d;available=-1;used=0
        if m<window_start or m>=window_end or used>=max_trades:continue
        if direction!=0 and side!=direction:continue
        if m<=available:continue
        chosen[j]=out[i];j+=1;available=int(out[i,3])+cooldown;used+=1
    return chosen

@njit(cache=True)
def metrics(pnl,worst,days,years):
    eq=0.0;peak=0.0;mdd=0.0;gp=0.0;gl=0.0;wins=0;worst_day=0.0
    last=-1;dayp=0.0
    for i in range(len(pnl)):
        d=int(days[i])
        if d!=last:
            if last>=0 and dayp<worst_day:worst_day=dayp
            last=d;dayp=0.0
        cand=eq+worst[i]-peak
        if cand<mdd:mdd=cand
        eq+=pnl[i];dayp+=pnl[i]
        if eq>peak:peak=eq
        if eq-peak<mdd:mdd=eq-peak
        if pnl[i]>0:gp+=pnl[i];wins+=1
        elif pnl[i]<0:gl-=pnl[i]
    if last>=0 and dayp<worst_day:worst_day=dayp
    pf=gp/gl if gl>0 else (99.0 if gp>0 else 0.0)
    return eq,mdd,pf,wins/len(pnl) if len(pnl) else 0.0,worst_day

def sized_path(trades,dates,mode,spec,r6cfg):
    cost=r6cfg['costs'];n=len(trades);pnl=np.zeros(n);worst=np.zeros(n);executed=np.zeros(n,dtype=bool)
    symbols=np.full(n,'',dtype=object);qty=np.zeros(n,dtype=int)
    if mode=='FIXED_QTY':
        symbol,q=spec
        pv=cost['nq_point_value'] if symbol=='NQ' else cost['mnq_point_value']
        comm=cost['nq_round_trip_commission'] if symbol=='NQ' else cost['mnq_round_trip_commission']
        pnl=trades[:,5]*pv*q-comm*q;worst=trades[:,6]*pv*q-comm*q;executed[:]=True;symbols[:]=symbol;qty[:]=q
    else:
        b=float(spec);slip=cost['slippage_per_side_points']
        for i,t in enumerate(trades):
            stop=t[7]
            nr=(stop+slip)*cost['nq_point_value']+cost['nq_round_trip_commission']
            mr=(stop+slip)*cost['mnq_point_value']+cost['mnq_round_trip_commission']
            qn=min(cost['max_nq'],int(b//nr));qm=min(cost['max_mnq'],int(b//mr))
            en=qn*cost['nq_point_value'];em=qm*cost['mnq_point_value']
            if en<=0 and em<=0:continue
            if en>=em:sym='NQ';q=qn;pv=cost['nq_point_value'];comm=cost['nq_round_trip_commission']
            else:sym='MNQ';q=qm;pv=cost['mnq_point_value'];comm=cost['mnq_round_trip_commission']
            executed[i]=True;symbols[i]=sym;qty[i]=q;pnl[i]=t[5]*pv*q-comm*q;worst[i]=t[6]*pv*q-comm*q
    days=trades[:,0].astype(int);years=np.array([int(str(dates[d])[:4]) for d in days],dtype=int)
    return pnl,worst,executed,symbols,qty,days,years

def path_stats(pnl,worst,executed,days,years):
    x=executed
    if not np.any(x):return None
    m=metrics(pnl[x].astype(float),worst[x].astype(float),days[x].astype(float),years[x].astype(float))
    out={'trades':int(x.sum()),'net_profit':float(m[0]),'max_drawdown':float(m[1]),'profit_factor':float(m[2]),'win_rate':float(m[3]),'worst_day':float(m[4])}
    out['profit_to_dd']=out['net_profit']/abs(out['max_drawdown']) if out['max_drawdown']<0 else 999.0
    for y in [2023,2024,2025]:
        z=x&(years==y)
        if np.any(z):
            mm=metrics(pnl[z].astype(float),worst[z].astype(float),days[z].astype(float),years[z].astype(float))
            out[f'trades_{y}']=int(z.sum());out[f'net_{y}']=float(mm[0]);out[f'mdd_{y}']=float(mm[1]);out[f'pf_{y}']=float(mm[2])
        else:
            out[f'trades_{y}']=0;out[f'net_{y}']=0.0;out[f'mdd_{y}']=0.0;out[f'pf_{y}']=0.0
    return out

def sizing_candidates(c61,r6cfg):
    for q in range(1,r6cfg['costs']['max_nq']+1):yield 'FIXED_QTY',('NQ',q)
    for q in range(1,r6cfg['costs']['max_mnq']+1):yield 'FIXED_QTY',('MNQ',q)
    for b in c61['sizing']['risk_budgets']:yield 'FIXED_RISK',float(b)

def choose_sizing(trades,dates,c61,r6cfg,selection_years=(2023,2024),oracle=False):
    cap=c61['objective']['max_drawdown'];best=None
    for mode,spec in sizing_candidates(c61,r6cfg):
        p,w,x,sym,q,days,years=sized_path(trades,dates,mode,spec,r6cfg)
        mask=x if oracle else x&np.isin(years,np.array(selection_years))
        if not np.any(mask):continue
        stsel=path_stats(p,w,mask,days,years)
        if stsel is None or stsel['max_drawdown']<=-cap:continue
        key=(stsel['net_profit'],stsel['profit_to_dd'])
        if best is None or key>best[0]:best=(key,mode,spec)
    if best is None:return None
    _,mode,spec=best
    p,w,x,sym,q,days,years=sized_path(trades,dates,mode,spec,r6cfg)
    full=path_stats(p,w,x,days,years);sel=path_stats(p,w,x&np.isin(years,np.array(selection_years)),days,years)
    return {'mode':mode,'spec':spec,'selection':sel,'full':full,'pnl':p,'worst':w,'executed':x,'symbols':sym,'qty':q,'days':days,'years':years}

def credible(stats,c61):
    if stats is None:return False
    o=c61['objective'];net=stats['net_profit']
    if net<o['min_net_profit'] or stats['max_drawdown']<=-o['max_drawdown'] or stats['trades']<o['credible_min_trades']:return False
    ys=[]
    for y in [2023,2024,2025]:
        if stats[f'trades_{y}']<o['credible_min_trades_per_year'] or stats[f'net_{y}']<=0:return False
        ys.append(stats[f'net_{y}'])
    return max(ys)/net<=o['max_year_profit_share'] if net>0 else False

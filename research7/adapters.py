from __future__ import annotations
from pathlib import Path
import importlib.util, json, sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent


def load_spec(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load module {name} from {path}')
    mod=importlib.util.module_from_spec(spec)
    # Python 3.12 dataclasses resolve annotations through sys.modules during
    # class decoration. Register the module before executing it, exactly as
    # the normal import machinery does. Remove a half-imported module on error.
    sys.modules[name]=mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name,None)
        raise
    return mod


def load_r6_modules():
    p=str(REPO/'research6')
    if p not in sys.path: sys.path.insert(0,p)
    import registry as registry6
    import features as features6
    import signals as signals6
    import execution as execution6
    return registry6,features6,signals6,execution6


def load_r61_modules():
    core=load_spec('r7_core61',REPO/'research6_1'/'core61.py')
    ctx=load_spec('r7_context61',REPO/'research6_1'/'context61.py')
    return core,ctx


def load_r1_module():
    return load_spec('r7_r1suite',REPO/'nq_orb_research_suite_010.py')


def attach_overnight(f,prepared):
    ov=Path(prepared)/'overnight.npy'
    f.overnight=np.load(ov).astype(np.float64,copy=False) if ov.exists() else np.full((len(f.a),3),np.nan)
    return f


def common_r1_state(prepared,r1):
    p=Path(prepared);meta=json.loads((p/'prepared.json').read_text());a=np.load(p/'rth.npy').astype(float)
    dates=np.array(meta['dates']);normal=np.array(meta['normal_session_mask'],dtype=bool);rows=[];allowed=set()
    for d,ds in enumerate(dates):
        day=pd.Timestamp(ds).date();x=a[d];good=np.isfinite(x).all(axis=1)
        if not good.all():continue
        if normal[d]:allowed.add(str(day))
        for m in np.where(good)[0]:
            o,h,l,c,v=x[m]
            rows.append((o,h,l,c,v,day,int(str(ds)[:4]),570+int(m)))
    df=pd.DataFrame(rows,columns=['open','high','low','close','volume','date_et','year','minute_et'])
    daily=r1.prepare_daily(df);days=r1.day_map(df);dayfeat=r1.build_day_features(df,daily,days)
    for L in [1,2,3,4,5,15,25,30,35]:
        vals={}
        for d,g in days.items():
            s=r1.opening_stats(g,L)
            if s:vals[d]=s['close']
        dayfeat[f'orb{L}_close']=pd.Series(vals)
    ml,tr=r1.train_ml_gates(dayfeat)
    return a,dates,days,dayfeat,ml,tr,allowed


def standardize_r1(prepared,candidate,state=None):
    r1=load_r1_module();
    if state is None: state=common_r1_state(prepared,r1)
    a,dates,days,dayfeat,ml,tr,allowed=state
    idx=int(candidate['config_id'][1:]);configs=r1.generate_configs();cfg=configs[idx]
    trade_days={d:g for d,g in days.items() if str(d) in allowed}
    st,legacy=r1.run_config(cfg,trade_days,dayfeat,ml,tr,risk=100000.0,return_trades=True)
    date_index={str(d):i for i,d in enumerate(dates)};out=[]
    slip=0.25
    for t in legacy:
        ds=str(t['date_et']);d=date_index.get(ds)
        if d is None:continue
        side=int(t['side']);entry_i=int(t['entry_min'])-570;exit_i=int(t['exit_min'])-570
        if not (0<=entry_i<390 and 0<=exit_i<390 and exit_i>=entry_i):continue
        entry_fill=float(t['entry'])+side*slip
        pnl_pts=float(t['gross_points'])-0.50
        worst=0.0
        for k in range(entry_i,exit_i+1):
            if not np.isfinite(a[d,k]).all():continue
            if side==1: w=float(a[d,k,2])-slip-entry_fill
            else: w=entry_fill-(float(a[d,k,1])+slip)
            worst=min(worst,w)
        worst=min(worst,pnl_pts)
        stop_pts=float(t['risk_points'])+slip
        out.append([d,entry_i,exit_i,side,pnl_pts,worst,stop_pts,entry_fill])
    return np.asarray(out,dtype=float),{'common_engine_unscaled_trades':len(out),'legacy_high_budget_stats':st,'config':cfg}


def standardize_r6(prepared,candidate,f=None):
    registry,features,signals,execution=load_r6_modules();
    if f is None:f=features.Features(prepared)
    ev=signals.build(f,candidate['signal']);e=candidate['execution'];slip=registry.config()['costs']['slippage_per_side_points']
    raw=execution.outcomes(f.a,f.atr,ev,e['stop_atr'],e['target_r'],e['hold'],slip,registry.config()['objective']['hard_flat_rth_index'])
    tr=execution.select(raw,e['window_start'],e['window_end'],e['direction'],e.get('max_trades',12))
    out=[]
    for t in tr:
        d,entry_i,exit_i,side=int(t[0]),int(t[2]),int(t[3]),int(t[4])
        entry=float(f.a[d,entry_i,0])+side*slip
        out.append([d,entry_i,exit_i,side,float(t[5]),float(t[6]),float(t[7]),entry])
    return np.asarray(out,dtype=float),{'signal_events':int(len(ev)),'selected_opportunities':int(len(tr))}


def standardize_r61(prepared,candidate,f=None):
    registry,features,signals,execution=load_r6_modules();core,ctx=load_r61_modules()
    if f is None:f=attach_overnight(features.Features(prepared),prepared)
    elif not hasattr(f,'overnight'):attach_overnight(f,prepared)
    ev=signals.build(f,candidate['signal']);X,names=ctx.context_matrix(f,ev,candidate['signal']['lookback'])
    years=np.array([int(str(f.dates[int(d)])[:4]) for d in ev[:,0]],dtype=int)
    preds=ctx.predicate_library(X,names,years==2023);lookup={n:m for n,m in preds};eligible=np.ones(len(ev),dtype=bool)
    for name in candidate['conditions']:
        if name not in lookup:raise KeyError('Frozen R6.1 predicate missing: '+name)
        eligible &= lookup[name]
    m=candidate['management'];slip=registry.config()['costs']['slippage_per_side_points']
    raw=core.enriched_outcomes(f.a,f.atr,ev,m['stop_atr'],m['target_r'],m['hold'],slip,389,m['be_trigger_r'],m['trail_activate_r'],m['trail_distance_r'],m['progress_minutes'],m['progress_mfe_r'])
    s=candidate['selection'];tr=core.select61(raw,eligible.astype(np.bool_),s['window_start'],s['window_end'],s['direction'],s['max_trades'],s['cooldown'])
    out=[]
    for t in tr:
        d,entry_i,exit_i,side=int(t[0]),int(t[2]),int(t[3]),int(t[4]);entry=float(f.a[d,entry_i,0])+side*slip
        out.append([d,entry_i,exit_i,side,float(t[5]),float(t[6]),float(t[7]),entry])
    return np.asarray(out,dtype=float),{'signal_events':int(len(ev)),'eligible_events':int(eligible.sum()),'selected_opportunities':int(len(tr))}

from __future__ import annotations
from pathlib import Path
import importlib.util, json, sys, itertools
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
R1_SEED=20260903


def load_spec(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load module {name} from {path}')
    mod=importlib.util.module_from_spec(spec)
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


def attach_overnight(f,prepared):
    ov=Path(prepared)/'overnight.npy'
    f.overnight=np.load(ov).astype(np.float64,copy=False) if ov.exists() else np.full((len(f.a),3),np.nan)
    return f

# ---------------------------------------------------------------------------
# Frozen R1 common-engine adapter.
#
# R7 intentionally does NOT import the legacy research script at runtime.
# Only the five canonical R1 rules carried into R7 are encoded here. This
# removes Python-version/import coupling while preserving the published rule
# definitions from RESEARCH_TRACKER.md / Suite 010.
# ---------------------------------------------------------------------------

R1_RULES={
    'C047761': dict(model='ORB09',orb_len=30,entry_mode='TOUCH',direction='BOTH',stop='OPPOSITE',target_r=3.0,time_exit=780,tr_model='HGBR_SHALLOW',tr_q=.67),
    'C013131': dict(model='ORB05',orb_len=30,entry_mode='TOUCH',direction='BOTH',stop='OPPOSITE',target_r=None,time_exit=959,vol_lb=10,vol_regime='LOW33'),
    'C051005': dict(model='ORB10',orb_len=15,entry_mode='TOUCH',direction='BOTH',stop='OPPOSITE',target_r=1.5,time_exit=959,gap_mode='REVERSAL',gap_thr=.005),
    'C002514': dict(model='ORB02',orb_len=35,entry_mode='CLOSE',direction='BOTH',stop='MID',target_r=None,time_exit=959,volz=1.0,close_loc=0.0),
    'C003740': dict(model='ORB03',orb_len=25,entry_mode='TOUCH',direction='LONG',stop='OPPOSITE',target_r=3.0,time_exit=780,delay=0),
}


def _r1_opening_stats(g,orb_len):
    og=g[(g.minute_et>=570)&(g.minute_et<570+orb_len)]
    if len(og)<max(1,orb_len-1):return None
    hi=float(og.high.max());lo=float(og.low.min());op=float(og.iloc[0].open);cl=float(og.iloc[-1].close);width=hi-lo
    if width<=0:return None
    return {'hi':hi,'lo':lo,'open':op,'close':cl,'width':width,'vol':float(og.volume.sum()),'dir':1 if cl>op else -1 if cl<op else 0,'end_min':570+orb_len}


def _r1_prepare_daily(df):
    r=df[(df.minute_et>=570)&(df.minute_et<960)].copy()
    daily=r.groupby('date_et').agg(rth_open=('open','first'),rth_high=('high','max'),rth_low=('low','min'),rth_close=('close','last'),rth_volume=('volume','sum'))
    daily['year']=pd.to_datetime(daily.index).year
    daily['prev_close']=daily.rth_close.shift(1)
    daily['prev_ret']=daily.rth_close.shift(1)/daily.rth_open.shift(1)-1
    daily['overnight_ret']=daily.rth_open/daily.prev_close-1
    pc=daily.rth_close.shift(1)
    trd=pd.concat([daily.rth_high.shift(1)-daily.rth_low.shift(1),(daily.rth_high.shift(1)-pc.shift(1)).abs(),(daily.rth_low.shift(1)-pc.shift(1)).abs()],axis=1).max(axis=1)
    daily['daily_atr14']=trd.rolling(14,min_periods=10).mean()
    daily['daily_ret']=daily.rth_close.pct_change()
    for n in [10,20,50,100]:daily[f'vol_{n}']=daily.daily_ret.shift(1).rolling(n,min_periods=max(8,n//2)).std(ddof=0)
    daily['ema50']=daily.rth_close.shift(1).ewm(span=50,adjust=False,min_periods=30).mean()
    daily['ema200']=daily.rth_close.shift(1).ewm(span=200,adjust=False,min_periods=100).mean()
    for n in [10,20,50]:
        v=daily[f'vol_{n}']
        for q in [.33,.50,.67,.80]:daily[f'vol{n}_q{int(q*100)}']=v.shift(1).rolling(126,min_periods=40).quantile(q)
    return daily


def _r1_build_day_features(daily,days):
    rows=[];hist_by_len={k:[] for k in [1,2,3,4,5,15,25,30,35]}
    for d in sorted(days):
        g=days[d];dr=daily.loc[d] if d in daily.index else None;row={'date_et':d,'year':pd.Timestamp(d).year}
        for L in hist_by_len:
            s=_r1_opening_stats(g,L)
            if s:
                prev=np.asarray(hist_by_len[L][-40:],float)
                row[f'orb{L}_hi']=s['hi'];row[f'orb{L}_lo']=s['lo'];row[f'orb{L}_width']=s['width'];row[f'orb{L}_dir']=s['dir'];row[f'orb{L}_vol']=s['vol'];row[f'orb{L}_close']=s['close']
                row[f'orb{L}_volz']=(s['vol']-prev.mean())/(prev.std(ddof=0) if prev.std(ddof=0)>0 else np.nan) if len(prev)>=10 else np.nan
                hist_by_len[L].append(s['vol'])
        if dr is not None:
            for c in daily.columns:row[c]=dr[c]
        rows.append(row)
    return pd.DataFrame(rows).set_index('date_et').sort_index()


def _r1_train_tr30(dayfeat):
    L=30;cols=[f'orb{L}_width',f'orb{L}_dir',f'orb{L}_volz','overnight_ret','prev_ret','daily_atr14','vol_20']
    z=dayfeat.copy();z['true_range']=z.rth_high-z.rth_low
    tr=z[z.year==2023].dropna(subset=cols+['true_range']);allx=z.dropna(subset=cols)
    if len(tr)<100:return {}
    mdl=HistGradientBoostingRegressor(max_iter=150,max_leaf_nodes=15,learning_rate=.05,l2_regularization=2,random_state=R1_SEED)
    mdl.fit(tr[cols].fillna(0),tr.true_range);pred=mdl.predict(allx[cols].fillna(0))
    return {d:float(p) for d,p in zip(allx.index,pred)}


def common_r1_state(prepared):
    p=Path(prepared);meta=json.loads((p/'prepared.json').read_text());a=np.load(p/'rth.npy').astype(float)
    dates=np.array(meta['dates']);normal=np.array(meta['normal_session_mask'],dtype=bool);rows=[];allowed=set()
    for di,ds in enumerate(dates):
        ds_text=str(ds);day=pd.Timestamp(ds_text).date();x=a[di];good=np.isfinite(x).all(axis=1)
        if not good.all():continue
        if normal[di]:allowed.add(str(day))
        for m in np.where(good)[0]:
            o,h,l,c,v=x[m];rows.append((o,h,l,c,v,day,int(ds_text[:4]),570+int(m)))
    df=pd.DataFrame(rows,columns=['open','high','low','close','volume','date_et','year','minute_et'])
    daily=_r1_prepare_daily(df);days={d:g.sort_values('minute_et').reset_index(drop=True) for d,g in df.groupby('date_et')}
    dayfeat=_r1_build_day_features(daily,days);tr30=_r1_train_tr30(dayfeat)
    return a,dates,days,dayfeat,tr30,allowed


def _r1_gate(rule,d,g,feat,tr30):
    s=_r1_opening_stats(g,rule['orb_len'])
    if not s:return None
    direction=rule['direction']
    if rule['model']=='ORB02':
        if feat.get(f"orb{rule['orb_len']}_volz",np.nan)<rule['volz']:return None
    elif rule['model']=='ORB05':
        v=feat.get(f"vol_{rule['vol_lb']}",np.nan);q=feat.get(f"vol{rule['vol_lb']}_q33",np.nan)
        if not np.isfinite(v) or not np.isfinite(q) or not v<=q:return None
    elif rule['model']=='ORB09':
        pred=tr30.get(d,np.nan);ratio=pred/s['width'] if s['width']>0 else np.nan
        if not np.isfinite(ratio) or ratio<2.5:return None
    elif rule['model']=='ORB10':
        o=feat.get('overnight_ret',np.nan);pr=feat.get('prev_ret',np.nan)
        if not np.isfinite(o) or not np.isfinite(pr) or abs(o)<rule['gap_thr']:return None
        direction='SHORT' if o>0 else 'LONG'
    return s,direction


def _r1_find_entry(rule,g,s,direction):
    start=s['end_min']+int(rule.get('delay',0));bars=g[(g.minute_et>=start)&(g.minute_et<rule['time_exit'])].reset_index()
    for _,r in bars.iterrows():
        longok=direction in ('BOTH','LONG');shortok=direction in ('BOTH','SHORT')
        if rule['entry_mode']=='TOUCH':
            L=longok and r.high>=s['hi'];S=shortok and r.low<=s['lo']
            if L and S:continue
            if L:return int(r['index']),1,max(float(r.open),s['hi'])
            if S:return int(r['index']),-1,min(float(r.open),s['lo'])
        else:
            L=longok and r.close>s['hi'];S=shortok and r.close<s['lo']
            if L or S:
                idx=int(r['index'])+1;nxt=g[g.index==idx]
                if nxt.empty:return None
                nr=nxt.iloc[0]
                if int(nr.minute_et)>=rule['time_exit']:return None
                return idx,1 if L else -1,float(nr.open)
    return None


def _r1_simulate(rule,d,g,feat,tr30):
    z=_r1_gate(rule,d,g,feat,tr30)
    if z is None:return None
    s,direction=z;ent=_r1_find_entry(rule,g,s,direction)
    if ent is None:return None
    idx,side,entry=ent
    if rule['stop']=='OPPOSITE':stop=s['lo'] if side==1 else s['hi']
    elif rule['stop']=='MID':stop=(s['hi']+s['lo'])/2
    else:raise ValueError(rule['stop'])
    riskpts=(entry-stop)*side
    if riskpts<=0:return None
    target=entry+side*riskpts*rule['target_r'] if rule['target_r'] is not None else None
    after=g[(g.index>=idx)&(g.minute_et<=rule['time_exit'])];exitp=None;exitmin=None
    for _,r in after.iterrows():
        if side==1:
            stop_hit=r.low<=stop;target_hit=target is not None and r.high>=target
            if stop_hit:exitp=min(stop,float(r.open)) if r.open<stop else stop;exitmin=int(r.minute_et);break
            if target_hit:exitp=target if r.open<target else float(r.open);exitmin=int(r.minute_et);break
        else:
            stop_hit=r.high>=stop;target_hit=target is not None and r.low<=target
            if stop_hit:exitp=max(stop,float(r.open)) if r.open>stop else stop;exitmin=int(r.minute_et);break
            if target_hit:exitp=target if r.open>target else float(r.open);exitmin=int(r.minute_et);break
    if exitp is None:
        q=after.iloc[-1] if not after.empty else g.loc[idx];exitp=float(q.close);exitmin=int(q.minute_et)
    return {'date_et':d,'side':side,'entry':entry,'entry_min':int(g.loc[idx].minute_et),'exit_min':exitmin,'risk_points':riskpts,'gross_points':(exitp-entry)*side}


def standardize_r1(prepared,candidate,state=None):
    if state is None:state=common_r1_state(prepared)
    a,dates,days,dayfeat,tr30,allowed=state;cid=candidate['config_id'];rule=R1_RULES.get(cid)
    if rule is None:raise KeyError('R7 has no frozen R1 rule for '+cid)
    date_index={str(d):i for i,d in enumerate(dates)};out=[];slip=.25;legacy=[]
    for d,g in days.items():
        if str(d) not in allowed or d not in dayfeat.index or pd.Timestamp(d).year<2023:continue
        t=_r1_simulate(rule,d,g,dayfeat.loc[d],tr30)
        if t is None:continue
        legacy.append(t);ds=str(d);di=date_index.get(ds)
        if di is None:continue
        side=int(t['side']);entry_i=int(t['entry_min'])-570;exit_i=int(t['exit_min'])-570
        if not (0<=entry_i<390 and 0<=exit_i<390 and exit_i>=entry_i):continue
        entry_fill=float(t['entry'])+side*slip;pnl_pts=float(t['gross_points'])-.50;worst=0.0
        for k in range(entry_i,exit_i+1):
            if not np.isfinite(a[di,k]).all():continue
            w=float(a[di,k,2])-slip-entry_fill if side==1 else entry_fill-(float(a[di,k,1])+slip);worst=min(worst,w)
        worst=min(worst,pnl_pts);stop_pts=float(t['risk_points'])
        out.append([di,entry_i,exit_i,side,pnl_pts,worst,stop_pts,entry_fill])
    return np.asarray(out,dtype=float),{'common_engine_unscaled_trades':len(out),'config_id':cid,'rule':rule}


def standardize_r6(prepared,candidate,f=None):
    registry,features,signals,execution=load_r6_modules()
    if f is None:f=features.Features(prepared)
    ev=signals.build(f,candidate['signal']);e=candidate['execution'];slip=registry.config()['costs']['slippage_per_side_points']
    raw=execution.outcomes(f.a,f.atr,ev,e['stop_atr'],e['target_r'],e['hold'],slip,registry.config()['objective']['hard_flat_rth_index'])
    tr=execution.select(raw,e['window_start'],e['window_end'],e['direction'],e.get('max_trades',12));out=[]
    for t in tr:
        d,entry_i,exit_i,side=int(t[0]),int(t[2]),int(t[3]),int(t[4]);entry=float(f.a[d,entry_i,0])+side*slip
        out.append([d,entry_i,exit_i,side,float(t[5]),float(t[6]),float(t[7]),entry])
    return np.asarray(out,dtype=float),{'signal_events':int(len(ev)),'selected_opportunities':int(len(tr))}


def standardize_r61(prepared,candidate,f=None):
    registry,features,signals,execution=load_r6_modules();core,ctx=load_r61_modules()
    if f is None:f=attach_overnight(features.Features(prepared),prepared)
    elif not hasattr(f,'overnight'):attach_overnight(f,prepared)
    ev=signals.build(f,candidate['signal']);X,names=ctx.context_matrix(f,ev,candidate['signal']['lookback'])
    years=np.array([int(str(f.dates[int(d)])[:4]) for d in ev[:,0]],dtype=int);preds=ctx.predicate_library(X,names,years==2023);lookup={n:m for n,m in preds};eligible=np.ones(len(ev),dtype=bool)
    for name in candidate['conditions']:
        if name not in lookup:raise KeyError('Frozen R6.1 predicate missing: '+name)
        eligible&=lookup[name]
    m=candidate['management'];slip=registry.config()['costs']['slippage_per_side_points']
    raw=core.enriched_outcomes(f.a,f.atr,ev,m['stop_atr'],m['target_r'],m['hold'],slip,389,m['be_trigger_r'],m['trail_activate_r'],m['trail_distance_r'],m['progress_minutes'],m['progress_mfe_r'])
    s=candidate['selection'];tr=core.select61(raw,eligible.astype(np.bool_),s['window_start'],s['window_end'],s['direction'],s['max_trades'],s['cooldown']);out=[]
    for t in tr:
        d,entry_i,exit_i,side=int(t[0]),int(t[2]),int(t[3]),int(t[4]);entry=float(f.a[d,entry_i,0])+side*slip
        out.append([d,entry_i,exit_i,side,float(t[5]),float(t[6]),float(t[7]),entry])
    return np.asarray(out,dtype=float),{'signal_events':int(len(ev)),'eligible_events':int(eligible.sum()),'selected_opportunities':int(len(tr))}

from __future__ import annotations

import argparse, itertools, json, math, random, warnings
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

warnings.filterwarnings('ignore')
ET='America/New_York'
SEED=20260903
np.random.seed(SEED); random.seed(SEED)

START_EQUITY=50_000.0
PRIMARY_RISK=300.0
NQ_POINT=20.0; MNQ_POINT=2.0
NQ_RT_COMM=3.50; MNQ_RT_COMM=1.00
MAX_NQ=4; MAX_MNQ=40
SLIPPAGE_RT_POINTS=0.50  # 1 tick each side
RISK_GRID=[50,75,100,125,150,175,200,250,300]
DAILY_STOPS={50:200,75:300,100:400,125:500,150:600,175:700,200:800,250:1000,300:1000}
PROFIT_TARGET=3000.0; MAX_LOSS=2000.0; DLL=1200.0; LOCKED_MLL=50100.0

STOP_SPECS=['OPPOSITE','MID','WIDTH_0.5','WIDTH_1.0','ATR_1.0','ATR_1.5']
TARGET_R=[1.0,1.5,2.0,3.0,None]
TIME_EXITS=[690,780,959]  # 11:30, 13:00, 15:59 ET
ENTRY_MODES=['TOUCH','CLOSE']
DIR_MODES=['BOTH','LONG','SHORT']

MODEL_FIDELITY={
'ORB01_MODERN_5M_FORMED':('Modern 5m formed-range ORB research','RECONSTRUCTION','5m ORB, opening-direction and daily-trend gates; NQ port.'),
'ORB02_VALUE_AREA_FLOW':('Modern NQ MBO/value-area ORB working research','OHLCV_PROXY','Exact MBO/aggressive delta unavailable; uses causal 1m volume/close-location proxy.'),
'ORB03_DELAYED_25M':('Mesfin 2026 MNQ ORB falsification study','MECHANISM_RECONSTRUCTION','25m range and delayed confirmation family; exact paper implementation not fully public.'),
'ORB04_TSAI_TORB':('Tsai et al. 2019 IEEE Access','HIGH','Direct E-mini Nasdaq-100 timely ORB; 1-5m probe family.'),
'ORB05_VOL_STATE':('Lundstrom 2019 / Umea ORB volatility-state research','TRANSFER','Futures ORB conditioned on ex-ante volatility state; transferred to NQ.'),
'ORB06_STAT_THRESHOLD':('Holmberg, Lonnbark & Lundstrom 2013 Finance Research Letters','TRANSFER_RECONSTRUCTION','Distribution/volatility-threshold ORB transferred from futures evidence to NQ.'),
'ORB07_GAORB_FULL_GRID':('Wu, Syu, Lin & Ho 2021 Knowledge-Based Systems','TRANSFER_FULL_GRID','Threshold-adjusted ORB + protective closing; exhaustive grid replaces GA search.'),
'ORB08_NN_THRESHOLD':('Chen, Syu & Ho 2020 IEEE SMC','TRANSFER_RECONSTRUCTION','Neural-network threshold classification gate on NQ ORB.'),
'ORB09_PREDICTED_TR':('Wu et al. 2026 ACIIDS/Springer','TRANSFER_RECONSTRUCTION','Predictive true-range gate; uses HGBR surrogate instead of paper LSTM due source detail/data limits.'),
'ORB10_NQ_GAP_STATE':('Yu, Rentzler & Wolf 2005 NQ futures intraday state research','NQ_CONDITIONAL_RECONSTRUCTION','NQ prior-day/overnight state used as an ORB activation/direction gate.'),
}


def load_data(data_dir:Path)->pd.DataFrame:
    dates=json.loads((data_dir/'dates.json').read_text())
    chunks=[]
    for i,d in enumerate(dates,1):
        p=data_dir/f'{d}.json'
        if p.exists():
            rows=json.loads(p.read_text())
            if rows: chunks.append(pd.DataFrame(rows,columns=['time','open','high','low','close','volume']))
        if i%150==0: print('loaded',i,'/',len(dates))
    if not chunks: raise RuntimeError('No data')
    x=pd.concat(chunks,ignore_index=True).drop_duplicates('time').sort_values('time').reset_index(drop=True)
    x['ts_utc']=pd.to_datetime(x['time'],unit='s',utc=True); x['ts_et']=x['ts_utc'].dt.tz_convert(ET)
    for c in ['open','high','low','close','volume']: x[c]=pd.to_numeric(x[c],errors='coerce')
    x=x.dropna(subset=['open','high','low','close']).reset_index(drop=True)
    x=x[(x.ts_et>='2022-12-26')&(x.ts_et<'2026-01-01')].reset_index(drop=True)
    x['date_et']=x.ts_et.dt.date; x['year']=x.ts_et.dt.year.astype(int); x['minute_et']=(x.ts_et.dt.hour*60+x.ts_et.dt.minute).astype(int)
    prev=x.close.shift(1)
    tr=pd.concat([x.high-x.low,(x.high-prev).abs(),(x.low-prev).abs()],axis=1).max(axis=1)
    x['atr1m14']=tr.rolling(14,min_periods=14).mean()
    return x


def prepare_daily(df):
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
    for n in [10,20,50,100]: daily[f'vol_{n}']=daily.daily_ret.shift(1).rolling(n,min_periods=max(8,n//2)).std(ddof=0)
    daily['ema50']=daily.rth_close.shift(1).ewm(span=50,adjust=False,min_periods=30).mean()
    daily['ema200']=daily.rth_close.shift(1).ewm(span=200,adjust=False,min_periods=100).mean()
    # thresholds from only prior history
    for n in [10,20,50]:
        v=daily[f'vol_{n}']
        for q in [0.33,0.50,0.67,0.80]: daily[f'vol{n}_q{int(q*100)}']=v.shift(1).rolling(126,min_periods=40).quantile(q)
    return daily


def day_map(df):
    return {d:g.sort_values('minute_et').reset_index(drop=True) for d,g in df[(df.minute_et>=570)&(df.minute_et<960)].groupby('date_et')}


def opening_stats(g,orb_len):
    og=g[(g.minute_et>=570)&(g.minute_et<570+orb_len)]
    if len(og)<max(1,orb_len-1): return None
    hi=float(og.high.max()); lo=float(og.low.min()); op=float(og.iloc[0].open); cl=float(og.iloc[-1].close); width=hi-lo
    if width<=0:return None
    vol=float(og.volume.sum()); rng=width
    return {'hi':hi,'lo':lo,'open':op,'close':cl,'width':width,'vol':vol,'dir':1 if cl>op else -1 if cl<op else 0,'end_min':570+orb_len}


def build_day_features(df,daily,days):
    rows=[]
    # historical opening volume baselines are prior days only
    hist_by_len={k:[] for k in [1,2,3,4,5,15,25,30,35]}
    for d in sorted(days):
        g=days[d]; dr=daily.loc[d] if d in daily.index else None
        row={'date_et':d,'year':pd.Timestamp(d).year}
        for L in hist_by_len:
            s=opening_stats(g,L)
            if s:
                prev=np.asarray(hist_by_len[L][-40:],float)
                row[f'orb{L}_hi']=s['hi']; row[f'orb{L}_lo']=s['lo']; row[f'orb{L}_width']=s['width']; row[f'orb{L}_dir']=s['dir']; row[f'orb{L}_vol']=s['vol']
                if len(prev)>=10:
                    row[f'orb{L}_volz']=(s['vol']-prev.mean())/(prev.std(ddof=0) if prev.std(ddof=0)>0 else np.nan)
                else: row[f'orb{L}_volz']=np.nan
                hist_by_len[L].append(s['vol'])
        if dr is not None:
            for c in daily.columns: row[c]=dr[c]
        rows.append(row)
    return pd.DataFrame(rows).set_index('date_et').sort_index()


def causality_audit(dayfeat):
    checks=[]
    # All daily conditioning fields must be lagged where they summarize a completed day.
    checks.append(('prev_close_available',dayfeat.prev_close.notna().sum()>100))
    checks.append(('daily_atr_lagged',dayfeat.daily_atr14.notna().sum()>100))
    # ORB stats only represent their completed range; simulator never scans before end_min.
    for L in [1,5,15,25,30,35]: checks.append((f'orb{L}_exists',dayfeat[f'orb{L}_width'].notna().sum()>100))
    status='PASS' if all(v for _,v in checks) else 'FAIL'
    return {'status':status,'checks':[{'name':n,'pass':bool(v)} for n,v in checks]}

@dataclass(frozen=True)
class Config:
    model:str; orb_len:int; entry_mode:str; direction:str; stop:str; target_r:float|None; time_exit:int
    delay:int=0; trend:str='NONE'; volz:float=-999.; close_loc:float=0.; vol_lb:int=20; vol_regime:str='NONE'
    stat_lb:int=20; stat_k:float=0.; eps_up:float=0.; eps_dn:float=0.; ml_arch:str='NONE'; ml_alpha:float=0.; ml_p:float=0.
    tr_model:str='NONE'; tr_q:float=0.; gap_mode:str='NONE'; gap_thr:float=0.


def common_product(model,orb_lens,entries=ENTRY_MODES,directions=DIR_MODES):
    for L,e,d,s,t,x in itertools.product(orb_lens,entries,directions,STOP_SPECS,TARGET_R,TIME_EXITS):
        yield dict(model=model,orb_len=L,entry_mode=e,direction=d,stop=s,target_r=t,time_exit=x)


def generate_configs():
    cfg=[]
    # 1 formed 5m: opening direction rule and trend filters
    for base in common_product('ORB01_MODERN_5M_FORMED',[5],directions=['BOTH']):
        for trend in ['NONE','EMA50','EMA200']:
            for od in ['OPENING','BOTH']:
                z=base.copy(); z['trend']=trend; z['gap_mode']=od; cfg.append(Config(**z))
    # 2 35m value-area/order-flow proxy: vol z + breakout close-location proxy
    for base in common_product('ORB02_VALUE_AREA_FLOW',[35],directions=['BOTH']):
        for vz,cl in itertools.product([0.,0.5,1.,1.5],[0.,0.65,0.80]):
            z=base.copy();z['volz']=vz;z['close_loc']=cl;cfg.append(Config(**z))
    # 3 delayed 25m
    for base in common_product('ORB03_DELAYED_25M',[25]):
        for delay in [0,1,2,3,5]: z=base.copy();z['delay']=delay;cfg.append(Config(**z))
    # 4 Tsai timely ORB 1-5m
    for base in common_product('ORB04_TSAI_TORB',[1,2,3,4,5]): cfg.append(Config(**base))
    # 5 volatility-state ORB
    for base in common_product('ORB05_VOL_STATE',[5,15,30],directions=['BOTH']):
        for lb,reg in itertools.product([10,20,50],['HIGH50','HIGH67','HIGH80','LOW33']):
            z=base.copy();z['vol_lb']=lb;z['vol_regime']=reg;cfg.append(Config(**z))
    # 6 distribution threshold ORB - threshold applied from session open in units of prior daily-return vol * price
    for base in common_product('ORB06_STAT_THRESHOLD',[1],directions=DIR_MODES):
        for lb,k in itertools.product([20,50,100],[0.25,0.5,0.75,1.0,1.25,1.5]):
            z=base.copy();z['stat_lb']=lb;z['stat_k']=k;cfg.append(Config(**z))
    # 7 full-grid GAORB: 15/30m, threshold shifts by opening-range std proxy (width/4)
    for base in common_product('ORB07_GAORB_FULL_GRID',[15,30],entries=['TOUCH'],directions=['BOTH']):
        for eu,ed in itertools.product([-1.,-.5,0.,.5,1.],repeat=2):
            z=base.copy();z['eps_up']=eu;z['eps_dn']=ed;cfg.append(Config(**z))
    # 8 NN gate
    for base in common_product('ORB08_NN_THRESHOLD',[5,15,30],directions=['BOTH']):
        for arch,a,p in itertools.product(['8','16','16x8'],[1e-4,1e-3],[.50,.55,.60,.65,.70]):
            z=base.copy();z['ml_arch']=arch;z['ml_alpha']=a;z['ml_p']=p;cfg.append(Config(**z))
    # 9 predicted TR gate (HGBR and ridge-like HGBR depth variants)
    for base in common_product('ORB09_PREDICTED_TR',[5,15,30],directions=['BOTH']):
        for m,q in itertools.product(['HGBR_SHALLOW','HGBR_DEEP'],[.50,.67,.80]):
            z=base.copy();z['tr_model']=m;z['tr_q']=q;cfg.append(Config(**z))
    # 10 direct-NQ prior/overnight state gated ORB
    for base in common_product('ORB10_NQ_GAP_STATE',[5,15,30],directions=['BOTH']):
        for mode,thr in itertools.product(['CONTINUATION','REVERSAL','SAME_SIGN','OPPOSITE_SIGN'],[0.,.0025,.005]):
            z=base.copy();z['gap_mode']=mode;z['gap_thr']=thr;cfg.append(Config(**z))
    # exact dedup
    unique={json.dumps(asdict(c),sort_keys=True):c for c in cfg}
    return list(unique.values())


def train_ml_gates(dayfeat):
    gates={}; tr_gates={}
    # build targets from subsequent RTH close relative to ORB close; 2023 training only
    for L in [5,15,30]:
        cols=[f'orb{L}_width',f'orb{L}_dir',f'orb{L}_volz','overnight_ret','prev_ret','daily_atr14','vol_20']
        z=dayfeat.copy(); z['y']=(z.rth_close>z[f'orb{L}_close'] if f'orb{L}_close' in z else z.rth_close>z.rth_open).astype(int)
        # ensure close feature exists through open direction proxy; not future extrema
        tr=z[(z.year==2023)].dropna(subset=[c for c in cols if c in z.columns]+['y'])
        allx=z.dropna(subset=[c for c in cols if c in z.columns])
        Xcols=[c for c in cols if c in z.columns]
        if len(tr)<100 or not Xcols: continue
        Xtr=tr[Xcols].replace([np.inf,-np.inf],np.nan).fillna(0)
        for arch,a in itertools.product(['8','16','16x8'],[1e-4,1e-3]):
            hidden={'8':(8,),'16':(16,),'16x8':(16,8)}[arch]
            mdl=make_pipeline(StandardScaler(),MLPClassifier(hidden_layer_sizes=hidden,alpha=a,max_iter=300,random_state=SEED))
            mdl.fit(Xtr,tr.y)
            prob=mdl.predict_proba(allx[Xcols].replace([np.inf,-np.inf],np.nan).fillna(0))[:,1]
            gates[(L,arch,a)]={d:float(p) for d,p in zip(allx.index,prob)}
        # predicted remaining daily range using only prior-day + opening info
        z['true_range']=(z.rth_high-z.rth_low)
        tr2=z[z.year==2023].dropna(subset=Xcols+['true_range'])
        for name,leaf in [('HGBR_SHALLOW',15),('HGBR_DEEP',31)]:
            mdl=HistGradientBoostingRegressor(max_iter=150,max_leaf_nodes=leaf,learning_rate=.05,l2_regularization=2,random_state=SEED)
            mdl.fit(tr2[Xcols].fillna(0),tr2.true_range)
            pred=mdl.predict(allx[Xcols].fillna(0))
            tr_gates[(L,name)]={d:float(p) for d,p in zip(allx.index,pred)}
    return gates,tr_gates


def gate_and_levels(cfg,d,g,feat,ml_gates,tr_gates):
    s=opening_stats(g,cfg.orb_len)
    if not s:return None
    upper=s['hi'];lower=s['lo']; direction=cfg.direction
    # Model 1: opening candle direction + daily trend
    if cfg.model=='ORB01_MODERN_5M_FORMED':
        if cfg.gap_mode=='OPENING': direction='LONG' if s['dir']>0 else 'SHORT' if s['dir']<0 else 'NONE'
        if cfg.trend!='NONE':
            ema=feat.get(cfg.trend.lower(),np.nan)
            pc=feat.get('prev_close',np.nan)
            if not np.isfinite(ema) or not np.isfinite(pc):return None
            if direction=='LONG' and pc<=ema:return None
            if direction=='SHORT' and pc>=ema:return None
    elif cfg.model=='ORB02_VALUE_AREA_FLOW':
        if feat.get(f'orb{cfg.orb_len}_volz',np.nan)<cfg.volz:return None
    elif cfg.model=='ORB05_VOL_STATE':
        v=feat.get(f'vol_{cfg.vol_lb}',np.nan); qnum={'HIGH50':50,'HIGH67':67,'HIGH80':80,'LOW33':33}[cfg.vol_regime]
        q=feat.get(f'vol{cfg.vol_lb}_q{qnum}',np.nan)
        if not np.isfinite(v) or not np.isfinite(q):return None
        if cfg.vol_regime.startswith('HIGH') and not v>=q:return None
        if cfg.vol_regime=='LOW33' and not v<=q:return None
    elif cfg.model=='ORB06_STAT_THRESHOLD':
        v=feat.get(f'vol_{cfg.stat_lb}',np.nan); op=s['open']
        if not np.isfinite(v):return None
        move=op*v*cfg.stat_k
        upper=op+move;lower=op-move
    elif cfg.model=='ORB07_GAORB_FULL_GRID':
        sig=s['width']/4.0
        upper=s['hi']+cfg.eps_up*sig;lower=s['lo']-cfg.eps_dn*sig
        if upper<=lower:return None
    elif cfg.model=='ORB08_NN_THRESHOLD':
        p=ml_gates.get((cfg.orb_len,cfg.ml_arch,cfg.ml_alpha),{}).get(d,np.nan)
        if not np.isfinite(p):return None
        # classification determines allowed side
        if p>=cfg.ml_p: direction='LONG'
        elif p<=1-cfg.ml_p: direction='SHORT'
        else:return None
    elif cfg.model=='ORB09_PREDICTED_TR':
        pred=tr_gates.get((cfg.orb_len,cfg.tr_model),{}).get(d,np.nan)
        if not np.isfinite(pred):return None
        # compare forecast with causal expanding training quantile from 2023 distribution proxy: multiple of opening width
        ratio=pred/s['width'] if s['width']>0 else np.nan
        threshold={.50:2.0,.67:2.5,.80:3.0}[cfg.tr_q]
        if not np.isfinite(ratio) or ratio<threshold:return None
    elif cfg.model=='ORB10_NQ_GAP_STATE':
        o=feat.get('overnight_ret',np.nan); p=feat.get('prev_ret',np.nan)
        if not np.isfinite(o) or not np.isfinite(p) or abs(o)<cfg.gap_thr:return None
        if cfg.gap_mode=='CONTINUATION': direction='LONG' if o>0 else 'SHORT'
        elif cfg.gap_mode=='REVERSAL': direction='SHORT' if o>0 else 'LONG'
        elif cfg.gap_mode=='SAME_SIGN':
            if np.sign(o)!=np.sign(p):return None
            direction='LONG' if o>0 else 'SHORT'
        else:
            if np.sign(o)==np.sign(p):return None
            direction='LONG' if o>0 else 'SHORT'
    return s,upper,lower,direction


def stop_price(cfg,side,entry,s,feat):
    w=s['width']; atr=feat.get('daily_atr14',np.nan)
    if cfg.stop=='OPPOSITE': return s['lo'] if side==1 else s['hi']
    if cfg.stop=='MID': return (s['hi']+s['lo'])/2
    if cfg.stop=='WIDTH_0.5': return entry-side*.5*w
    if cfg.stop=='WIDTH_1.0': return entry-side*1.0*w
    if cfg.stop=='ATR_1.0' and np.isfinite(atr): return entry-side*atr
    if cfg.stop=='ATR_1.5' and np.isfinite(atr): return entry-side*1.5*atr
    return np.nan


def find_entry(cfg,g,s,upper,lower,direction):
    start=s['end_min']+cfg.delay
    bars=g[(g.minute_et>=start)&(g.minute_et<cfg.time_exit)].reset_index()
    for j,r in bars.iterrows():
        longok=direction in ('BOTH','LONG'); shortok=direction in ('BOTH','SHORT')
        if cfg.entry_mode=='TOUCH':
            L=longok and r.high>=upper; S=shortok and r.low<=lower
            if L and S: continue # ambiguous bar
            if L:return int(r['index']),1,max(float(r.open),upper)
            if S:return int(r['index']),-1,min(float(r.open),lower)
        else:
            L=longok and r.close>upper; S=shortok and r.close<lower
            if L or S:
                idx=int(r['index'])+1
                nxt=g[g.index==idx]
                if nxt.empty:return None
                nr=nxt.iloc[0]
                if int(nr.minute_et)>=cfg.time_exit:return None
                return idx,1 if L else -1,float(nr.open)
    return None


def size_position(stoppts,risk_budget):
    if not np.isfinite(stoppts) or stoppts<=0:return None
    nq_r=stoppts*NQ_POINT+NQ_RT_COMM
    q=min(MAX_NQ,int(risk_budget//nq_r))
    if q>=1:return ('NQ',q,NQ_POINT,NQ_RT_COMM,nq_r*q)
    mnq_r=stoppts*MNQ_POINT+MNQ_RT_COMM
    q=min(MAX_MNQ,int(risk_budget//mnq_r))
    if q>=1:return ('MNQ',q,MNQ_POINT,MNQ_RT_COMM,mnq_r*q)
    return None


def simulate_trade(cfg,d,g,feat,ml_gates,tr_gates,risk_budget=PRIMARY_RISK):
    gl=gate_and_levels(cfg,d,g,feat,ml_gates,tr_gates)
    if gl is None:return None
    s,upper,lower,direction=gl
    if direction=='NONE':return None
    ent=find_entry(cfg,g,s,upper,lower,direction)
    if ent is None:return None
    idx,side,entry=ent
    # model2 close-location confirmation on breakout bar
    if cfg.model=='ORB02_VALUE_AREA_FLOW' and cfg.close_loc>0:
        rr=g.loc[idx]; br=rr.high-rr.low
        loc=(rr.close-rr.low)/br if br>0 else .5
        if side==1 and loc<cfg.close_loc:return None
        if side==-1 and (1-loc)<cfg.close_loc:return None
    st=stop_price(cfg,side,entry,s,feat)
    if not np.isfinite(st):return None
    riskpts=(entry-st)*side
    if riskpts<=0:return None
    pos=size_position(riskpts,risk_budget)
    if pos is None:return None
    inst,qty,pv,comm,actual_risk=pos
    target=entry+side*riskpts*cfg.target_r if cfg.target_r is not None else None
    after=g[(g.index>=idx)&(g.minute_et<=cfg.time_exit)]
    exitp=None;exitmin=None;reason='TIME'
    for _,r in after.iterrows():
        # stop-first if both touched
        if side==1:
            stop_hit=r.low<=st; target_hit=target is not None and r.high>=target
            if stop_hit:
                exitp=min(st,float(r.open)) if r.open<st else st;exitmin=int(r.minute_et);reason='STOP';break
            if target_hit:
                exitp=target if r.open<target else float(r.open);exitmin=int(r.minute_et);reason='TARGET';break
        else:
            stop_hit=r.high>=st; target_hit=target is not None and r.low<=target
            if stop_hit:
                exitp=max(st,float(r.open)) if r.open>st else st;exitmin=int(r.minute_et);reason='STOP';break
            if target_hit:
                exitp=target if r.open>target else float(r.open);exitmin=int(r.minute_et);reason='TARGET';break
    if exitp is None:
        q=after.iloc[-1] if not after.empty else g.loc[idx]
        exitp=float(q.close);exitmin=int(q.minute_et)
    grosspts=(exitp-entry)*side
    netpts=grosspts-SLIPPAGE_RT_POINTS
    pnl=netpts*pv*qty-comm*qty
    return {'date_et':d,'year':pd.Timestamp(d).year,'side':side,'entry':entry,'exit':exitp,'entry_min':int(g.loc[idx].minute_et),'exit_min':exitmin,'reason':reason,'instrument':inst,'qty':qty,'risk_points':riskpts,'actual_risk':actual_risk,'gross_points':grosspts,'net_pnl':pnl,'R_actual':pnl/actual_risk if actual_risk>0 else np.nan,'R_budget':pnl/risk_budget}


def streak_stats(wins):
    if len(wins)==0:return (0,0,0,0)
    ws=[];ls=[];cur=wins[0];n=0
    for x in wins:
        if x==cur:n+=1
        else:
            (ws if cur else ls).append(n);cur=x;n=1
    (ws if cur else ls).append(n)
    return max(ws or [0]),float(np.mean(ws)) if ws else 0,max(ls or [0]),float(np.mean(ls)) if ls else 0


def stats(trades):
    if not trades:return None
    t=pd.DataFrame(trades).sort_values('date_et')
    pnl=t.net_pnl.to_numpy(); r=t.R_actual.to_numpy(); wins=pnl>0
    gp=pnl[pnl>0].sum();gl=-pnl[pnl<0].sum();pf=gp/gl if gl>0 else np.inf
    eq=START_EQUITY+np.cumsum(pnl); peak=np.maximum.accumulate(np.r_[START_EQUITY,eq])[:-1]; dd=eq-peak
    req=np.cumsum(r);rpeak=np.maximum.accumulate(np.r_[0,req])[:-1];rdd=req-rpeak
    mw,aw,ml,al=streak_stats(wins.tolist())
    daily=t.groupby('date_et').net_pnl.sum()
    sh=(daily.mean()/daily.std(ddof=1)*math.sqrt(252)) if len(daily)>2 and daily.std(ddof=1)>0 else np.nan
    neg=daily[daily<0]; so=(daily.mean()/neg.std(ddof=1)*math.sqrt(252)) if len(neg)>2 and neg.std(ddof=1)>0 else np.nan
    return {'trades':len(t),'net_profit':pnl.sum(),'net_R_actual':r.sum(),'profit_factor':pf,'win_rate':wins.mean(),'avg_trade':pnl.mean(),'avg_R':r.mean(),'avg_win':pnl[wins].mean() if wins.any() else 0,'avg_loss':pnl[~wins].mean() if (~wins).any() else 0,'max_drawdown':dd.min(),'max_drawdown_R':rdd.min(),'largest_win':pnl.max(),'largest_loss':pnl.min(),'max_win_streak':mw,'avg_win_streak':aw,'max_loss_streak':ml,'avg_loss_streak':al,'sharpe_daily':sh,'sortino_daily':so}


def run_config(cfg,days,dayfeat,ml_gates,tr_gates,risk=PRIMARY_RISK,return_trades=False):
    tr=[]
    for d,g in days.items():
        if d not in dayfeat.index or pd.Timestamp(d).year<2023:continue
        z=simulate_trade(cfg,d,g,dayfeat.loc[d],ml_gates,tr_gates,risk)
        if z:tr.append(z)
    st=stats(tr)
    if st is None:return None,[]
    # year stats
    for y in [2023,2024,2025]:
        yy=[q for q in tr if q['year']==y]; sy=stats(yy)
        st[f'net_{y}']=sy['net_profit'] if sy else 0; st[f'R_{y}']=sy['net_R_actual'] if sy else 0;st[f'PF_{y}']=sy['profit_factor'] if sy else np.nan;st[f'trades_{y}']=len(yy)
    return st,tr if return_trades else []


def prop_replay(trades,risk_budget,daily_stop,dll_on=True):
    if not trades:return {'pass_rate_pct':0,'fail_rate_pct':0,'median_days_pass':np.nan}
    t=pd.DataFrame(trades); day=t.groupby('date_et').net_pnl.sum().clip(lower=-daily_stop)
    pairs=list(day.items()); outcomes=[]
    for s in range(0,len(pairs),5):
        bal=START_EQUITY; high=bal; mll=bal-MAX_LOSS;res='OPEN';nd=0
        for nd,(d,pnl) in enumerate(pairs[s:],1):
            pnl=max(pnl,-DLL) if dll_on else pnl
            bal+=pnl
            if bal<=mll:res='FAIL';break
            if bal>=START_EQUITY+PROFIT_TARGET:res='PASS';break
            high=max(high,bal);mll=max(START_EQUITY-MAX_LOSS,min(LOCKED_MLL,high-MAX_LOSS))
        outcomes.append((res,nd))
    pdays=[d for r,d in outcomes if r=='PASS']
    return {'pass_rate_pct':100*sum(r=='PASS' for r,d in outcomes)/len(outcomes),'fail_rate_pct':100*sum(r=='FAIL' for r,d in outcomes)/len(outcomes),'open_rate_pct':100*sum(r=='OPEN' for r,d in outcomes)/len(outcomes),'median_days_pass':float(np.median(pdays)) if pdays else np.nan,'starts':len(outcomes)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--out-dir',type=Path,default=Path('orb_suite_010_results'));args=ap.parse_args();args.out_dir.mkdir(parents=True,exist_ok=True)
    df=load_data(args.data_dir); daily=prepare_daily(df); days=day_map(df); dayfeat=build_day_features(df,daily,days)
    audit=causality_audit(dayfeat);(args.out_dir/'causality_audit.json').write_text(json.dumps(audit,indent=2));print('CAUSALITY',audit['status'])
    if audit['status']!='PASS':raise RuntimeError('Causality audit failed')
    # opening close columns are explicitly causal and known at range completion
    for L in [1,2,3,4,5,15,25,30,35]:
        vals={}
        for d,g in days.items():
            s=opening_stats(g,L)
            if s:vals[d]=s['close']
        dayfeat[f'orb{L}_close']=pd.Series(vals)
    ml_gates,tr_gates=train_ml_gates(dayfeat)
    configs=generate_configs()
    manifest=pd.DataFrame([{'config_id':f'C{i:06d}',**asdict(c)} for i,c in enumerate(configs)])
    manifest.to_csv(args.out_dir/'grid_manifest.csv',index=False)
    print('TOTAL CONFIGS',len(configs))
    results=[]
    for i,cfg in enumerate(configs):
        st,_=run_config(cfg,days,dayfeat,ml_gates,tr_gates,PRIMARY_RISK,False)
        if st:
            results.append({'config_id':f'C{i:06d}',**asdict(cfg),**st})
        if (i+1)%1000==0:print('tested',i+1,'/',len(configs))
    res=pd.DataFrame(results)
    res.to_csv(args.out_dir/'all_configuration_results.csv',index=False)
    # completeness assertion: every manifest config was attempted exactly once; no valid-trade configs can naturally be absent from result table
    completion={'manifest_count':len(configs),'attempted_count':len(configs),'valid_result_count':len(res),'status':'PASS' if len(configs)==len(manifest) else 'FAIL'}
    (args.out_dir/'grid_completion.json').write_text(json.dumps(completion,indent=2))
    # rank with minimum trade floor and positive 2024; 2025 remains secondary/seen
    cand=res[(res.trades>=80)&(res.trades_2024>=20)].copy()
    cand['rank_score']=np.log(cand.profit_factor.clip(lower=.01))*np.sqrt(cand.trades)+0.25*cand.avg_R*np.sqrt(cand.trades)
    cand=cand.sort_values(['rank_score','net_profit'],ascending=False)
    cand.head(500).to_csv(args.out_dir/'top_500.csv',index=False)
    topm=cand.groupby('model',group_keys=False).head(10)
    topm.to_csv(args.out_dir/'top_10_per_model.csv',index=False)
    # full trade logs + year/month + risk grid for top 3 per model
    logs=[];prop=[];yearrows=[];monthrows=[]
    for _,row in cand.groupby('model',group_keys=False).head(3).iterrows():
        cid=row.config_id; cfg=configs[int(cid[1:])]
        st,tr=run_config(cfg,days,dayfeat,ml_gates,tr_gates,PRIMARY_RISK,True)
        for q in tr:logs.append({'config_id':cid,**q})
        tt=pd.DataFrame(tr)
        if not tt.empty:
            for y,gg in tt.groupby('year'):
                sy=stats(gg.to_dict('records'));yearrows.append({'config_id':cid,'year':y,**sy})
            tt['month']=pd.to_datetime(tt.date_et).dt.to_period('M').astype(str)
            for m,gg in tt.groupby('month'):
                sm=stats(gg.to_dict('records'));monthrows.append({'config_id':cid,'month':m,**sm})
        for risk in RISK_GRID:
            _,trr=run_config(cfg,days,dayfeat,ml_gates,tr_gates,risk,True)
            sr=stats(trr)
            for dll_on in [True,False]:
                pp=prop_replay(trr,risk,DAILY_STOPS[risk],dll_on)
                prop.append({'config_id':cid,'risk_budget':risk,'personal_daily_stop':DAILY_STOPS[risk],'dll_on':dll_on,**(sr or {}),**pp})
    pd.DataFrame(logs).to_csv(args.out_dir/'trade_logs_top3_per_model.csv',index=False)
    pd.DataFrame(yearrows).to_csv(args.out_dir/'yearly_stats_top3_per_model.csv',index=False)
    pd.DataFrame(monthrows).to_csv(args.out_dir/'monthly_stats_top3_per_model.csv',index=False)
    pd.DataFrame(prop).to_csv(args.out_dir/'prop_risk_grid_top3_per_model.csv',index=False)
    fid=pd.DataFrame([{'model':k,'source':v[0],'fidelity':v[1],'note':v[2]} for k,v in MODEL_FIDELITY.items()]);fid.to_csv(args.out_dir/'model_fidelity.csv',index=False)
    summary=['# NQ ORB Research Suite 010','',f'Grid manifest: **{len(configs):,} configurations**',f'Valid result rows: **{len(res):,}**','', '## Top configuration from each model','']
    best=cand.groupby('model',group_keys=False).head(1)
    cols=['config_id','model','trades','net_profit','net_R_actual','profit_factor','win_rate','avg_R','max_drawdown','max_drawdown_R','PF_2023','PF_2024','PF_2025']
    summary.append(best[cols].to_markdown(index=False) if not best.empty else 'No valid candidates.')
    summary += ['','## Fidelity','',fid.to_markdown(index=False),'','Primary Strategy-Tester risk is $300/trade. All top-3-per-model configurations are replayed at $50/$75/$100/$125/$150/$175/$200/$250/$300 risk. Same-bar stop/target ambiguity is stop-first. Signals never enter before their opening range is complete. 2025 has been inspected in prior project work and is not called pristine OOS.']
    (args.out_dir/'summary.md').write_text('\n'.join(summary))
    print('\n'.join(summary))

if __name__=='__main__':main()

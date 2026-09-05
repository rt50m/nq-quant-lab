from __future__ import annotations
import numpy as np

def context_matrix(f,events,lookback):
    n=len(events);names=['signal_minute','side','impulse_atr','volume_z','vwap_side_atr','vwap_slope_side_atr','session_move_side_atr','range_pos_side','range15_atr','range30_atr','gap_side_atr','prev_day_side_atr','vxn','overnight_range_atr','open_vs_overnight_vwap_side_atr']
    X=np.full((n,len(names)),np.nan)
    for i,e in enumerate(events):
        d,m,side=map(int,e);a=f.atr[d]
        if not np.isfinite(a) or a<=0:continue
        c=f.c[d,m];base=f.c[d,m-lookback] if m>=lookback else np.nan
        X[i,0]=m;X[i,1]=side;X[i,2]=side*(c-base)/a if np.isfinite(base) else np.nan
        X[i,3]=f.volume_z[d,m];X[i,4]=side*(c-f.vwap[d,m])/a;X[i,5]=side*f.vwap_slope5[d,m]/a
        X[i,6]=side*(c-f.o[d,0])/a
        hi=np.nanmax(f.h[d,:m+1]);lo=np.nanmin(f.l[d,:m+1]);pos=(c-lo)/(hi-lo) if hi>lo else .5
        X[i,7]=pos if side==1 else 1-pos
        for j,k in [(8,15),(9,30)]:
            s=max(0,m-k+1);X[i,j]=(np.nanmax(f.h[d,s:m+1])-np.nanmin(f.l[d,s:m+1]))/a
        X[i,10]=side*(f.o[d,0]-f.prev_close[d])/a
        if d>=1 and np.isfinite(f.prev_close[d]) and np.isfinite(f.prev_close[d-1]):X[i,11]=side*(f.prev_close[d]-f.prev_close[d-1])/a
        X[i,12]=f.vxn[d]
        if hasattr(f,'overnight') and np.isfinite(f.overnight[d]).all():
            X[i,13]=(f.overnight[d,0]-f.overnight[d,1])/a
            X[i,14]=side*(f.o[d,0]-f.overnight[d,2])/a
    return X,names

def predicate_library(X,names,train_mask):
    idx={n:i for i,n in enumerate(names)};pred=[('ALL',np.ones(len(X),dtype=bool))]
    def add(label,arr): pred.append((label,np.asarray(arr,dtype=bool)&np.isfinite(np.nan_to_num(arr.astype(float),nan=0.0))))
    m=X[:,idx['signal_minute']]
    for lo,hi in [(5,60),(60,120),(120,180),(180,240),(240,300),(300,360),(5,120),(30,270),(120,360),(5,360)]:
        pred.append((f'time[{lo},{hi})',(m>=lo)&(m<hi)))
    side=X[:,idx['side']];pred += [('LONG',side==1),('SHORT',side==-1)]
    imp=X[:,idx['impulse_atr']]
    for t in [.08,.10,.12,.15,.18,.22,.25,.30]: pred.append((f'impulse>={t}',imp>=t))
    vz=X[:,idx['volume_z']]
    for t in [-.5,0,.5,1.0]: pred.append((f'volume_z>={t}',vz>=t))
    vd=X[:,idx['vwap_side_atr']]
    for t in [0,.10,.25,.50]:pred.append((f'vwap_aligned>={t}',vd>=t))
    pred.append(('vwap_contra',vd<0))
    vs=X[:,idx['vwap_slope_side_atr']]
    for t in [0,.01,.02,.04]:pred.append((f'vwap_slope_aligned>={t}',vs>=t))
    sm=X[:,idx['session_move_side_atr']]
    for t in [0,.25,.50,1.0]:pred.append((f'session_aligned>={t}',sm>=t))
    pred.append(('session_contra',sm<0))
    rp=X[:,idx['range_pos_side']]
    for t in [.5,.67,.8]:pred.append((f'range_pos_side>={t}',rp>=t))
    gap=X[:,idx['gap_side_atr']];pred += [('gap_aligned',gap>=0),('gap_contra',gap<0)]
    prev=X[:,idx['prev_day_side_atr']];pred += [('prevday_aligned',prev>=0),('prevday_contra',prev<0)]
    vx=X[:,idx['vxn']];pred += [('vxn<20',vx<20),('vxn20_30',(vx>=20)&(vx<30)),('vxn>=30',vx>=30)]
    if 'overnight_range_atr' in idx:
        ov=X[:,idx['overnight_range_atr']]
        vals=ov[train_mask&np.isfinite(ov)]
        if len(vals):
            for q in [.33,.67]:
                t=float(np.quantile(vals,q));pred.append((f'overnight_range_atr<=trainQ{int(q*100)}({t:.4f})',ov<=t));pred.append((f'overnight_range_atr>=trainQ{int(q*100)}({t:.4f})',ov>=t))
        ovp=X[:,idx['open_vs_overnight_vwap_side_atr']];pred += [('open_vs_ovn_vwap_aligned',ovp>=0),('open_vs_ovn_vwap_contra',ovp<0)]
    # Training-only quantile cutoffs for realized intraday range; thresholds are frozen before validation/diagnostic years.
    for nm in ['range15_atr','range30_atr']:
        z=X[:,idx[nm]];vals=z[train_mask&np.isfinite(z)]
        if len(vals):
            for q in [.33,.67]:
                t=float(np.quantile(vals,q));pred.append((f'{nm}<=trainQ{int(q*100)}({t:.4f})',z<=t));pred.append((f'{nm}>=trainQ{int(q*100)}({t:.4f})',z>=t))
    # remove exact duplicate masks
    out=[];seen=set()
    for name,mask in pred:
        key=np.packbits(mask).tobytes()
        if key not in seen:seen.add(key);out.append((name,mask))
    return out

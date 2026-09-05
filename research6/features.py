"""Shared R6 arrays. Pandas is only used once here for compact rolling/EMA preparation."""
from __future__ import annotations
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from registry import config

def lag(x,k):
    out=np.full_like(x,np.nan,dtype=float)
    if k>0: out[:,k:]=x[:,:-k]
    else: out[:]=x
    return out

def rolling_prior(x,n,kind):
    df=pd.DataFrame(x.T)
    r=getattr(df.rolling(n,min_periods=n),kind)().shift(1)
    return r.T.to_numpy(dtype=float)

def ema(x,span):
    return pd.DataFrame(x.T).ewm(span=span,adjust=False).mean().T.to_numpy(dtype=float)

class Features:
    def __init__(self,prepared):
        p=Path(prepared);self.meta=json.loads((p/'prepared.json').read_text())
        if self.meta.get('timestamp_convention')!='close' or self.meta.get('normalization_seconds')!=-60:
            raise ValueError('R6 requires R4 timestamp-audited close-stamp normalization')
        for name,d in self.meta['files'].items():
            if hashlib.sha256((p/name).read_bytes()).hexdigest()!=d:raise ValueError('Prepared checksum mismatch '+name)
        self.a=np.load(p/'rth.npy').astype(np.float64,copy=False)
        self.dates=np.array(self.meta['dates']);self.normal=np.array(self.meta['normal_session_mask'],dtype=bool)
        g=config();self.keep=self.normal&(self.dates>=g['development_start'])&(self.dates<=g['development_end'])
        o,h,l,c,v=(self.a[:,:,i] for i in range(5));self.o=o;self.h=h;self.l=l;self.c=c;self.v=v
        n=len(c);day_hi=np.nanmax(h,axis=1);day_lo=np.nanmin(l,axis=1);day_cl=c[:,-1]
        prev=np.r_[np.nan,day_cl[:-1]];self.prev_close=prev
        tr=np.maximum(day_hi-day_lo,np.maximum(np.abs(day_hi-prev),np.abs(day_lo-prev)))
        self.atr=pd.Series(tr).shift(1).rolling(14,min_periods=10).mean().to_numpy(dtype=float)
        self.valid=self.keep&np.isfinite(self.atr)&(self.atr>0)&np.isfinite(self.a).all(axis=(1,2))
        vx=p/'vxn_prev.npy';meta_ext=p/'r6_external.json'
        if vx.exists() and meta_ext.exists():
            ext=json.loads(meta_ext.read_text());
            if hashlib.sha256(vx.read_bytes()).hexdigest()!=ext['aligned_sha256']:raise ValueError('VXN aligned checksum mismatch')
            self.vxn=np.load(vx).astype(np.float64,copy=False)
        else:self.vxn=np.full(len(self.a),np.nan)
        total=np.cumsum(v,axis=1);money=np.cumsum(((h+l+c)/3.0)*v,axis=1)
        self.vwap=np.divide(money,total,out=np.full_like(money,np.nan),where=total>0)
        self.vwap_slope5=self.vwap-lag(self.vwap,5)
        vd=pd.DataFrame(v)
        mu=vd.shift(1).rolling(20,min_periods=10).mean();sd=vd.shift(1).rolling(20,min_periods=10).std(ddof=0)
        self.volume_z=((vd-mu)/sd.replace(0,np.nan)).to_numpy(dtype=float)
        self.ema={p:ema(c,p) for p in [5,10,20,30,60]}
        self.rh={p:rolling_prior(h,p,'max') for p in [10,20,30,60]}
        self.rl={p:rolling_prior(l,p,'min') for p in [10,20,30,60]}
        # Shorter rolling ranges needed by compression and VWAP streak checks.
        self.range_hi={p:rolling_prior(h,p,'max') for p in [3,5,10,15,20,30]}
        self.range_lo={p:rolling_prior(l,p,'min') for p in [3,5,10,15,20,30]}
        dist=c-self.vwap
        self.dist_min_prior={p:rolling_prior(dist,p,'min') for p in [5,10,20]}
        self.dist_max_prior={p:rolling_prior(dist,p,'max') for p in [5,10,20]}

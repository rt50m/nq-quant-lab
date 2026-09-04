"""Causal shared features on explicitly normalized R4 minute-open bars."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from registry import grid


def lag(x,n,kind='mean',q=.5):
    r=pd.DataFrame(x).shift(1).rolling(n,min_periods=n)
    return (r.quantile(q) if kind=='quantile' else getattr(r,kind)()).to_numpy()


class Features:
    def __init__(self,path):
        path=Path(path)
        self.meta=json.loads((path/'prepared.json').read_text())
        if self.meta['timestamp_convention']!='close' or self.meta['normalization_seconds']!=-60:
            raise ValueError('R4 requires the audited timestamp normalization')
        for name,digest in self.meta['files'].items():
            if hashlib.sha256((path/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Prepared array checksum mismatch: '+name)
        self.a=np.load(path/'rth.npy')
        self.night=np.load(path/'overnight.npy')
        self.dates=np.array(self.meta['dates'])
        self.normal=np.array(self.meta['normal_session_mask'])
        self.keep=self.normal&(self.dates>=grid()['development_start'])
        n=len(self.a)
        self.hi=np.full(n,np.nan);self.lo=self.hi.copy();self.cl=self.hi.copy()
        for d,k in enumerate(self.meta['cash_session_minutes']):
            x=self.a[d,:k]
            if np.isfinite(x).all():
                self.hi[d]=x[:,1].max();self.lo[d]=x[:,2].min();self.cl[d]=x[-1,3]
        prev=np.r_[np.nan,self.cl[:-1]]
        tr=np.maximum(self.hi-self.lo,np.maximum(abs(self.hi-prev),abs(self.lo-prev)))
        self.atr=lag(tr,14)[:,0]
        self.eligible=self.keep&np.isfinite(self.atr)&(self.atr>0)
        volume=self.a[:,:,4]
        total=np.cumsum(volume,axis=1)
        money=np.cumsum(self.a[:,:,1:4].mean(axis=2)*volume,axis=1)
        self.vwap=np.divide(money,total,out=np.full_like(total,np.nan),where=total>0)
        self.ret=np.full((n,390),np.nan)
        self.ret[:,1:]=np.log(self.a[:,1:,3]/self.a[:,:-1,3])
        self.cache={}

    def standardized(self,n):
        key=('standardized',n)
        if key not in self.cache:
            mean=lag(self.ret,n);sd=lag(self.ret,n,'std')
            self.cache[key]=np.divide(self.ret-mean,sd,out=np.full_like(sd,np.nan),where=sd>0)
        return self.cache[key]

    def jump(self,n):
        key=('jump',n)
        if key not in self.cache:
            r=self.ret
            rv=pd.DataFrame(r*r).T.rolling(n,min_periods=n).sum().T.to_numpy()
            pair=abs(r)*abs(np.roll(r,1,axis=1))
            bv=pd.DataFrame(pair).T.rolling(n-1,min_periods=n-1).sum().T.to_numpy()*np.pi/2*n/(n-1)
            self.cache[key]=np.divide(np.maximum(rv-bv,0),rv,out=np.full_like(rv,np.nan),where=rv>0)
        return self.cache[key]

    def adverse_threshold(self,n,q):
        key=('adverse',n,q)
        if key not in self.cache:
            values=[]
            for side in [1,-1]:
                r=np.where(side*self.ret<0,self.ret*self.ret,0.)
                r[~np.isfinite(self.ret)]=np.nan
                sums=pd.DataFrame(r).T.rolling(n,min_periods=n).sum().T.to_numpy()
                values.append(lag(sums,60,'quantile',q))
            self.cache[key]=np.stack(values,axis=2)
        return self.cache[key]

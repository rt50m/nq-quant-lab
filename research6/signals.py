"""Vectorized high-density trigger generation. Signals are known only after the current minute closes."""
from __future__ import annotations
import numpy as np
from features import lag

def _events(mask_long,mask_short,valid):
    ml=mask_long & valid[:,None]; ms=mask_short & valid[:,None]
    both=ml&ms; ml&=~both; ms&=~both  # opposite signals in same minute are execution-ambiguous: skip.
    dl,tl=np.where(ml); ds,ts=np.where(ms)
    if len(dl)+len(ds)==0:return np.empty((0,3),dtype=np.int32)
    x=np.vstack([np.c_[dl,tl,np.ones(len(dl),int)],np.c_[ds,ts,-np.ones(len(ds),int)]])
    return x[np.lexsort((x[:,2],x[:,1],x[:,0]))].astype(np.int32)

def build(f,s):
    c,h,l,vwap,atr=f.c,f.h,f.l,f.vwap,f.atr[:,None]
    pc=lag(c,1);ph=lag(h,1);pl=lag(l,1);pvwap=lag(vwap,1)
    fam=s['family']; L=np.zeros_like(c,dtype=bool);S=L.copy()
    if fam=='TREND_PULLBACK':
        fast=f.ema[s['fast']];slow=f.ema[s['slow']];pfast=lag(fast,1)
        slope=slow-lag(slow,10);thr=s['slope_atr']*atr
        L=(fast>slow)&(slope>thr)&(pc<=pfast)&(c>fast)
        S=(fast<slow)&(slope<-thr)&(pc>=pfast)&(c<fast)
        if s['vwap_filter']:
            L&=c>vwap;S&=c<vwap
    elif fam=='ROLLING_BREAKOUT':
        hi=f.rh[s['lookback']];lo=f.rl[s['lookback']];buf=s['buffer_atr']*atr
        L=(c>hi+buf)&(pc<=lag(hi,1)+buf);S=(c<lo-buf)&(pc>=lag(lo,1)-buf)
        if s['vwap_filter']:L&=c>vwap;S&=c<vwap
        if s['volume_z']>-90:L&=f.volume_z>=s['volume_z'];S&=f.volume_z>=s['volume_z']
    elif fam=='FAILED_BREAKOUT':
        hi=f.rh[s['lookback']];lo=f.rl[s['lookback']];phi=lag(hi,1);plo=lag(lo,1)
        over=s['overshoot_atr']*atr;rec=s['reclaim_atr']*atr
        L=(pl<plo-over)&(pc>=plo)&(c>plo+rec)
        S=(ph>phi+over)&(pc<=phi)&(c<phi-rec)
        if s['volume_z']>-90:L&=f.volume_z>=s['volume_z'];S&=f.volume_z>=s['volume_z']
    elif fam=='VWAP_STRETCH_REVERSAL':
        dist=pc-pvwap;stretch=s['stretch_atr']*atr
        L=(dist<-stretch)&(c>ph);S=(dist>stretch)&(c<pl)
        if s['max_abs_vwap_slope_atr']>=0:
            ok=np.abs(f.vwap_slope5)<=s['max_abs_vwap_slope_atr']*atr;L&=ok;S&=ok
    elif fam in ('IMPULSE_CONTINUATION','IMPULSE_REVERSAL'):
        k=s['lookback'];base=lag(c,k);move=np.divide(c-base,atr,out=np.full_like(c,np.nan),where=np.isfinite(atr)&(atr>0))
        pmove=lag(move,1);thr=s['impulse_atr']
        if fam=='IMPULSE_CONTINUATION':
            L=(move>thr)&(pmove<=thr)&(c>ph);S=(move<-thr)&(pmove>=-thr)&(c<pl)
        else:
            L=(pmove<-thr)&(c>ph);S=(pmove>thr)&(c<pl)
        if s['volume_z']>-90:L&=f.volume_z>=s['volume_z'];S&=f.volume_z>=s['volume_z']
    elif fam=='COMPRESSION_BREAKOUT':
        hi=f.range_hi[s['lookback']];lo=f.range_lo[s['lookback']];rg=hi-lo;buf=s['buffer_atr']*atr
        comp=rg<=s['max_range_atr']*atr
        L=comp&(c>hi+buf)&(pc<=lag(hi,1)+buf);S=comp&(c<lo-buf)&(pc>=lag(lo,1)-buf)
    elif fam=='VWAP_TREND_RECLAIM':
        st=s['streak'];tol=s['tolerance_atr']*atr;sl=s['slope_atr']*atr
        # Prior streak excludes the immediately preceding pullback bar by shifting the prior rolling extrema one extra minute.
        prior_min=lag(f.dist_min_prior[st],1);prior_max=lag(f.dist_max_prior[st],1)
        touchL=(pl<=pvwap+tol)&(pc>=pvwap);touchS=(ph>=pvwap-tol)&(pc<=pvwap)
        L=(prior_min>0)&touchL&(c>ph)&(f.vwap_slope5>sl)
        S=(prior_max<0)&touchS&(c<pl)&(f.vwap_slope5<-sl)
    elif fam=='VXN_BAND_REVERSION':
        vx=f.vxn[:,None];base=f.prev_close[:,None];pct=s['band_mult']*vx/1600.0
        upper=base*(1+pct);lower=base*(1-pct);reg=s['regime']
        regime=np.isfinite(vx)
        if reg=='LOW20':regime&=vx<20
        elif reg=='HIGH30':regime&=vx>=30
        elif reg=='EXTREMES':regime&=((vx<20)|(vx>=30))
        if s['entry']=='BREACH':
            # Fade the first completed close that crosses outside the implied daily band.
            S=regime&(c>upper)&(pc<=upper);L=regime&(c<lower)&(pc>=lower)
        else:
            # Wait for a completed close back inside after the prior minute was outside.
            S=regime&(pc>upper)&(c<=upper);L=regime&(pc<lower)&(c>=lower)
    else: raise ValueError(fam)
    # Need next-bar entry and at least one minute before the hard flat.
    L[:,-1]=False;S[:,-1]=False
    return _events(L,S,f.valid)

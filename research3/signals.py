"""Ten causal NQ hypotheses. Every array index denotes a future executable open.

Forecasts train on completed prior days. No full-sample state smoothing, scaling,
threshold selection or backfilled pivots. None of the models requests ES data.
"""
import json
import hashlib
import math
from pathlib import Path
import numpy as np
import pandas as pd
from numba import njit
from registry import grid, study_hash

def lagmean(x,n,minimum=None):
    return pd.DataFrame(x).shift().rolling(n,min_periods=n if minimum is None else minimum).mean().to_numpy()

class Features:
    def __init__(self,path):
        path=Path(path);self.meta=json.loads((path/'prepared.json').read_text())
        if self.meta['study_hash']!=study_hash():raise ValueError('Prepared code/grid mismatch')
        if hashlib.sha256((path/'bars.npy').read_bytes()).hexdigest()!=self.meta['bars_sha256']:raise ValueError('Prepared bars checksum mismatch')
        full=np.load(path/'bars.npy');self.a=np.ascontiguousarray(full[:,570:960])
        self.dates=np.array(self.meta['dates']);n=len(self.a)
        closes=np.array(self.meta['cash_close_minutes'])
        self.op=self.a[:,0,0];self.cl=full[np.arange(n),closes-1,3]
        self.prev=np.r_[np.nan,self.cl[:-1]]
        self.gap=self.op/self.prev-1
        self.prior=np.r_[np.nan,(self.cl/self.op-1)[:-1]]
        complete=np.array([np.isfinite(full[i,570:closes[i],:]).all() for i in range(n)])
        hi=np.array([np.max(full[i,570:closes[i],1]) for i in range(n)])
        lo=np.array([np.min(full[i,570:closes[i],2]) for i in range(n)])
        tr=np.maximum(hi-lo,np.maximum(abs(hi-self.prev),abs(lo-self.prev)))
        tr[~complete]=np.nan
        self.atr=lagmean(tr,14)[:,0]
        self.keep=(self.dates>=grid()['development_start'])&np.array(self.meta['normal_session_mask'])
        self.eligible=self.keep&np.isfinite(self.atr)&(self.atr>0)
        volume=self.a[:,:,4];money=self.a[:,:,:4][:,:,1:4].mean(axis=2)*volume
        sums=np.cumsum(volume,axis=1)
        self.vwap=np.divide(np.cumsum(money,axis=1),sums,out=np.full_like(sums,np.nan),where=sums>0)
        self.daily=self.cl/self.prev-1;self.cache={}

    def vol(self,n):
        key=('vol',n)
        if key not in self.cache:self.cache[key]=pd.Series(self.daily).shift().rolling(n).std(ddof=0).to_numpy()
        return self.cache[key]

    def noise(self,n):
        key=('noise',n)
        if key not in self.cache:self.cache[key]=lagmean(abs(self.a[:,:,3]/self.op[:,None]-1),n)
        return self.cache[key]

def regression(x,y,history,ridge=.1,minimum=80,intercept=False):
    """Prior-only ridge and residual forecast uncertainty; invalid rows never imputed."""
    n=len(y);pred=np.full(n,np.nan);unc=np.full(n,np.nan)
    for d in range(n):
        left=max(0,d-history) if history else 0
        xx=x[left:d];yy=y[left:d]
        good=np.isfinite(xx).all(axis=1)&np.isfinite(yy)
        if good.sum()<minimum or not np.isfinite(x[d]).all():continue
        xx=xx[good];yy=yy[good]
        if intercept:
            pred[d]=yy.mean();unc[d]=yy.std()/np.sqrt(len(yy));continue
        mu=xx.mean(axis=0);sd=xx.std(axis=0);sd=np.where(sd>1e-10,sd,1)
        z=np.c_[np.ones(len(xx)),(xx-mu)/sd];zz=np.r_[1,(x[d]-mu)/sd]
        penalty=np.eye(z.shape[1])*ridge*len(z);penalty[0,0]=0
        inv=np.linalg.pinv(z.T@z+penalty)
        beta=inv@z.T@yy;pred[d]=zz@beta
        residual=yy-z@beta
        unc[d]=np.sqrt(max(0,np.mean(residual**2)*(zz@inv@zz)))
    return pred,unc

def markov_forecast(x,y,history,states):
    """Two Gaussian regression regimes, EM using training-only forward/backward.

    The final training-day FILTERED probability is propagated one step. EM smoothing
    is confined to the training window. Refit every 21 sessions, filter new realized
    observations between fits. Abort unstable fits, never silently select a best state.
    """
    if states==1:return regression(x[:,None],y,history,minimum=126)
    n=len(y);pred=np.full(n,np.nan);unc=np.full(n,np.nan)
    beta=None;prob=None;last=-999;P=np.array([[.95,.05],[.05,.95]])
    for d in range(n):
        if d-last>=21 or beta is None:
            start=max(0,d-history) if history else 0
            xx=x[start:d];yy=y[start:d]
            # State time is successive observed closing windows. Short sessions
            # have no closing-window observation and do not reset all estimation.
            good=np.isfinite(xx)&np.isfinite(yy)
            xx=xx[good];yy=yy[good]
            if len(yy)<126:beta=None;continue
            mu=xx.mean();sd=max(xx.std(),1e-8);z=np.c_[np.ones(len(xx)),(xx-mu)/sd]
            base=np.linalg.lstsq(z,yy,rcond=None)[0]
            beta=np.vstack([base,base]);beta[:,0]+=np.array([-1,1])*yy.std()*.4
            variance=np.full(2,max(yy.var(),1e-10));P=np.array([[.95,.05],[.05,.95]])
            okay=True
            for iteration in range(100):
                error=yy[:,None]-z@beta.T
                likelihood=np.exp(np.clip(-.5*error**2/variance,-700,0))/np.sqrt(variance)
                alpha=np.zeros_like(likelihood);alpha[0]=likelihood[0]*.5;alpha[0]/=alpha[0].sum()
                for t in range(1,len(yy)):
                    alpha[t]=(alpha[t-1]@P)*likelihood[t];alpha[t]/=max(alpha[t].sum(),1e-300)
                back=np.ones_like(alpha)
                for t in range(len(yy)-2,-1,-1):
                    back[t]=P@(likelihood[t+1]*back[t+1]);back[t]/=max(back[t].sum(),1e-300)
                weight=alpha*back;weight/=np.maximum(weight.sum(axis=1,keepdims=True),1e-300)
                if weight.sum(axis=0).min()<20:okay=False;break
                transitions=np.zeros((2,2))
                for t in range(len(yy)-1):
                    joint=alpha[t,:,None]*P*(likelihood[t+1]*back[t+1])[None,:]
                    transitions+=joint/max(joint.sum(),1e-300)
                P=(transitions+.5)/(transitions.sum(axis=1,keepdims=True)+1)
                change=0.
                for k in range(2):
                    w=weight[:,k];mat=z.T@(w[:,None]*z)+np.diag([1e-8,.01])
                    b=np.linalg.solve(mat,z.T@(w*yy));change=max(change,np.max(abs(b-beta[k])))
                    beta[k]=b;variance[k]=max(np.sum(w*(yy-z@b)**2)/w.sum(),1e-10)
                if iteration>=4 and change<1e-6:break
            # No output from nonconverged or degenerate state fits.
            if not okay or iteration==99 or not np.isfinite(beta).all():beta=None;continue
            # Recompute filtered terminal state with FINAL fitted parameters.
            prob=np.ones(2)/2
            for t in range(len(yy)):
                if t:prob=prob@P
                likelihood=np.exp(np.clip(-.5*(yy[t]-z[t]@beta.T)**2/variance,-700,0))/np.sqrt(variance)
                prob*=likelihood;prob/=max(prob.sum(),1e-300)
            last=d
        elif np.isfinite(y[d-1]) and np.isfinite(x[d-1]):
            zz=np.array([1,(x[d-1]-mu)/sd]);pr=prob@P
            pr*=np.exp(np.clip(-.5*(y[d-1]-zz@beta.T)**2/variance,-700,0))/np.sqrt(variance)
            prob=pr/max(pr.sum(),1e-300)
        # If the preceding close was unavailable, keep the last observed filtered
        # distribution; the next observed target advances this event-time chain.
        if not np.isfinite(x[d]):continue
        pr=prob@P;means=np.array([1,(x[d]-mu)/sd])@beta.T
        pred[d]=pr@means;unc[d]=np.sqrt(pr@(variance+(means-pred[d])**2))/np.sqrt(126)
    return pred,unc

@njit(cache=True)
def level_commands(a,atr,window,bounces,max_age,hold,width,ignore):
    n=len(a);cmd=np.full((n,390),np.nan);st=np.full_like(cmd,np.nan);tar=st.copy();end=np.full_like(cmd,389)
    for d in range(n):
        if not np.isfinite(atr[d]):continue
        levels=np.zeros(390);born=np.zeros(390,dtype=np.int64);count=np.zeros(390,dtype=np.int64)
        pending=np.zeros(390,dtype=np.int64);entered=np.zeros(390,dtype=np.int64);kinds=np.zeros(390,dtype=np.int64)
        total=0;w=max(.25,atr[d]*width);last_signal=-1
        for t in range(window,388):
            # Pivot at t-2 is confirmed by t-1 and t; eligible only now.
            j=t-2
            if not np.isfinite(a[d,t,3]):break
            for kind in [-1,1]:
                val=a[d,j,2] if kind==1 else a[d,j,1]
                lo=max(0,j-window)
                extrem=True
                for v in range(lo,t+1):
                    if v==j:continue
                    if not np.isfinite(a[d,v,0]):extrem=False;break
                    if (kind==1 and a[d,v,2]<val) or (kind==-1 and a[d,v,1]>val):extrem=False;break
                if extrem:
                    duplicate=False
                    for z in range(total):
                        if kinds[z]==kind and t-born[z]<=max_age and abs(levels[z]-val)<2*w:duplicate=True
                    if not duplicate and total<390:
                        levels[total]=val;born[total]=t;kinds[total]=kind;total+=1
            for z in range(total):
                if t-born[z]>max_age or t==born[z]:continue
                level=levels[z];kind=kinds[z];c=a[d,t,3]
                touch=a[d,t,2]<=level+w and a[d,t,1]>=level-w
                if pending[z] and t>entered[z]:
                    rejection=(c>level+w if kind==1 else c<level-w)
                    broken=(c<level-w if kind==1 else c>level+w)
                    if rejection:
                        # The current bounce cannot count as a PRIOR bounce.
                        if (ignore or count[z]>=bounces) and last_signal<t:
                            cmd[d,t+1]=kind;end[d,t+1]=min(389,t+1+hold)
                            tar[d,t+1]=c+kind*2*w;last_signal=t+hold
                        count[z]+=1;pending[z]=0
                    elif broken:pending[z]=0
                elif touch:pending[z]=1;entered[z]=t
    return cmd,st,tar,end

def build(f,s):
    a=f.a;n=len(a);family=s['family'];kind=s.get('kind','');eligible=f.eligible.copy()
    cmd=np.full((n,390),np.nan);st=cmd.copy();target=cmd.copy();end=np.full((n,390),389.)
    diagnostics={};entries=1;close=a[:,:,3]
    if family=='M01':
        vol=f.vol(s['lookback']);eligible &= np.isfinite(vol)&(vol>0)
        for t in range(s['spacing']-1,388,s['spacing']):
            mean=np.mean(close[:,t-s['spacing']+1:t+1],axis=1)
            score=(mean/f.prev-1)/vol
            c=np.where(abs(score)>=s['threshold'],np.sign(score),np.where(abs(score)<=s['threshold']*s['exit_ratio'],0,np.nan))
            if s['strength']:c*=np.minimum(1,np.maximum(.5,abs(score)/(2*s['threshold'])))
            if kind=='long':c[:]=1
            cmd[:,t+1]=c
        entries=26
    elif family=='M02':
        h=s['horizon'];y=a[:,h,0]/a[:,1,0]-1
        weekday=pd.to_datetime(f.dates).dayofweek.to_numpy()==0
        x=np.c_[f.prior,f.gap,f.vol(20),weekday]
        if s['interaction']:x=np.c_[x,np.sign(f.prior)*np.sign(f.gap),f.prior*f.gap]
        key=('reg2',s['history'],h,s['interaction'],s['ridge'],kind=='intercept')
        if key not in f.cache:f.cache[key]=regression(x,y,s['history'],s['ridge'],intercept=kind=='intercept')
        pred,unc=f.cache[key];cost=1.5/f.op
        c=np.where(abs(pred)>cost+s['gate']*unc,np.sign(pred),0)
        if kind=='gap_sign':c=np.sign(f.gap)
        eligible &= np.isfinite(pred) if kind!='gap_sign' else np.isfinite(f.gap)
        cmd[:,1]=c;end[:,1]=h
    elif family=='M03':
        x=close[:,29]/f.prev-1;y=a[:,389,0]/a[:,360,0]-1
        if kind=='opening_only':x=close[:,29]/f.op-1
        if kind=='gap_only':x=f.gap.copy()
        if kind=='late_momentum':x=close[:,359]/f.prev-1
        if s['method']=='linear':
            key=('reg3',s['history'])
            if key not in f.cache:f.cache[key]=regression(x[:,None],y,s['history'])
            pred,unc=f.cache[key];eligible &=np.isfinite(pred);c=np.where(abs(pred)>1.5/f.op,np.sign(pred),0)
        else:c=np.sign(x)
        q=pd.Series(abs(x)).shift().rolling(s['history'],min_periods=80).quantile(s['quantile']).to_numpy()
        if s['quantile']>0:c=np.where(abs(x)>=q,c,0);eligible &= np.isfinite(q)
        if kind=='long':c[:]=1
        eligible &=np.isfinite(x);cmd[:,360]=c
    elif family=='M04':
        key=('reg4',s['history'],s['states']);y=a[:,389,0]/a[:,360,0]-1
        if key not in f.cache:f.cache[key]=markov_forecast(f.gap,y,s['history'],s['states'])
        pred,unc=f.cache[key];eligible &=np.isfinite(pred)
        cmd[:,360]=np.where(abs(pred)>1.5/f.op+s['gate']*unc,np.sign(pred),0)
        if kind=='gap_sign':cmd[:,360]=np.sign(f.gap);eligible=f.eligible&np.isfinite(f.gap)
        diagnostics['forecast_unavailable_days']=int((f.eligible&~eligible).sum())
    elif family=='M05':
        noise=f.noise(s['lookback']);upper=np.maximum(f.op,f.prev)[:,None]*(1+s['multiplier']*noise)
        lower=np.minimum(f.op,f.prev)[:,None]*(1-s['multiplier']*noise)
        eligible &=np.isfinite(noise[:,29])
        state=np.zeros(n)
        for t in range(29,388):
            if (t+1)%s['spacing']==0:
                c=np.where(close[:,t]>upper[:,t],1,np.where(close[:,t]<lower[:,t],-1,0))
                # New signals only: unchanged direction does not reopen each decision.
                cmd[:,t+1]=np.where(c!=state,c,np.nan);state=c
            if kind!='fixed_exit':
                long_stop=np.maximum(upper[:,t],f.vwap[:,t]) if s['vwap_exit'] else upper[:,t]
                short_stop=np.minimum(lower[:,t],f.vwap[:,t]) if s['vwap_exit'] else lower[:,t]
                st[:,t+1]=np.where(state==1,long_stop,np.where(state==-1,short_stop,np.nan))
        entries=s['max_entries']
    elif family=='M06':
        state=np.zeros(n)
        for t in range(s['spacing']-1,388,s['spacing']):
            diff=close[:,t]-f.vwap[:,t];band=s['buffer']*f.atr
            c=np.where(diff>band,1,np.where(diff<-band,-1,np.where(abs(diff)<=band*s['exit_ratio'],0,state)))
            if kind=='long':c[:]=1
            cmd[:,t+1]=np.where(c!=state,c,np.nan);state=c
        entries=s['max_entries']
    elif family=='M07':
        key=('jump',s['sampling'])
        if key not in f.cache:
            score=np.full(n,np.nan);largest=np.zeros(n,dtype=bool)
            for d in range(1,n):
                prices=np.r_[f.op[d-1],close[d-1,s['sampling']-1::s['sampling']]]
                r=np.diff(np.log(prices))
                if not np.isfinite(r).all() or not np.isfinite(f.gap[d]):continue
                # Empirical jump score: use an overnight-inclusive RV/BV contrast.
                # Unequal interval durations mean this is NOT a calibrated BNS p-value.
                largest[d]=abs(np.log1p(f.gap[d]))>=np.max(abs(r))
                r=np.r_[r,np.log1p(f.gap[d])];m=len(r);rv=np.sum(r*r)
                bv=np.pi/2*m/(m-1)*np.sum(abs(r[1:]*r[:-1]))
                mu43=2**(2/3)*math.gamma(7/6)/np.sqrt(np.pi)
                trip=m*m/(m-2)*np.sum(abs(r[2:]*r[1:-1]*r[:-2])**(4/3))/mu43**3
                denom=np.sqrt(((np.pi/2)**2+np.pi-5)/m*max(1,trip/max(bv*bv,1e-20)))
                score[d]=(rv-bv)/max(rv,1e-20)/max(denom,1e-20)
            f.cache[key]=(score,largest)
        score,largest=f.cache[key];select=(score>s['threshold'])&largest
        if kind=='matched_gap':
            select=np.zeros(n,dtype=bool)
            for d in range(126,n):
                prior=score[max(0,d-252):d];gaps=abs(f.gap[max(0,d-252):d]);good=np.isfinite(prior)&np.isfinite(gaps)
                if good.sum()<80:continue
                rate=np.mean((prior[good]>s['threshold'])&largest[max(0,d-252):d][good])
                select[d]=rate>0 and abs(f.gap[d])>=np.quantile(gaps[good],1-rate)
        t=s['wait'];side=-np.sign(f.gap)
        if t==5:select &= side*(close[:,4]-f.op)>0
        # Require the opening gap to be the largest absolute component of the
        # augmented series; a prior-day jump must not be mislabeled an opening jump.
        eligible &=np.isfinite(score)&np.isfinite(f.gap)
        cmd[:,t]=np.where(select,side,0);end[:,t]=np.minimum(389,t+s['hold'])
        target[:,t]=f.op+s['closure']*(f.prev-f.op)
        # A target already passed before entry is no longer the proposed gap setup.
        cmd[:,t]=np.where(side*(target[:,t]-a[:,t,0])>0,cmd[:,t],0)
    elif family=='M08':
        L=s['opening'];hi=np.max(a[:,:L,1],axis=1);lo=np.min(a[:,:L,2],axis=1)
        for d in range(n):
            if not np.isfinite(hi[d]+lo[d]) or hi[d]<=lo[d]:continue
            direction=0;born=-1;exc=0.;boundary=0.
            for t in range(L-1,329):
                c=close[d,t]
                if not np.isfinite(c):break
                if direction==0:
                    if c>hi[d]:direction=1;boundary=hi[d];born=t
                    elif c<lo[d]:direction=-1;boundary=lo[d];born=t
                    if direction and kind=='immediate':
                        entry=t+1;cmd[d,entry]=direction;st[d,entry]=lo[d] if direction==1 else hi[d]
                        distance=direction*(a[d,entry,0]+direction*.25-st[d,entry])
                        target[d,entry]=a[d,entry,0]+direction*(.25+max(.25,distance)*s['target_r']);break
                    continue
                exc=max(exc,direction*((a[d,t,1] if direction==1 else a[d,t,2])-boundary))
                if t-born>s['deadline'] or exc>s['excursion']*(hi[d]-lo[d]):break
                touch=a[d,t,2]<=boundary+s['tolerance'] if direction==1 else a[d,t,1]>=boundary-s['tolerance']
                if touch and direction*(c-boundary)>0:
                    entry=t+1;cmd[d,entry]=direction
                    stop=boundary-direction*.25 if s['stop_type']=='boundary' else (a[d,t,2]-.25 if direction==1 else a[d,t,1]+.25)
                    st[d,entry]=stop;distance=direction*(a[d,entry,0]+direction*.25-stop)
                    if distance<=0:cmd[d,entry]=0;break
                    target[d,entry]=a[d,entry,0]+direction*(.25+np.ceil(distance*4)/4*s['target_r']);break
    elif family=='M09':
        cmd,st,target,end=level_commands(a,f.atr,s['window'],s['bounces'],s['age'],s['hold'],s['width'],kind=='no_age_count')
        entries=3
    elif family=='M10':
        t=s['slot'];exit_t=min(389,t+30);ret=a[:,exit_t,0]/a[:,max(1,t),0]-1
        pred=np.full(n,np.nan);unc=pred.copy()
        for d in range(n):
            hist=ret[:min(d,126)] if kind=='static_clock' else ret[max(0,d-s['history']):d]
            if len(hist)<(126 if kind=='static_clock' else s['history']) or not np.isfinite(hist).all():continue
            w=np.exp(np.linspace(-2,0,len(hist))) if s['decay'] else np.ones(len(hist));w/=w.sum()
            pred[d]=.5*(w@hist);unc[d]=np.sqrt(w@((hist-w@hist)**2)/len(hist))
        eligible &=np.isfinite(pred);cmd[:,max(1,t)]=np.where(abs(pred)>1.5/f.op+s['gate']*unc,np.sign(pred),0)
        end[:,max(1,t)]=exit_t
    else:raise ValueError(family)
    # Mark only unavailable observations actually required by this signal. A missing
    # unrelated morning bar must not invalidate a fixed closing-window strategy.
    required=np.zeros(390,dtype=bool)
    if family in ['M01','M05','M06','M09']:required[:389]=True
    elif family=='M08':required[:330]=True
    elif family=='M02':required[0]=True
    elif family=='M03':required[359 if kind=='late_momentum' else 29]=True
    elif family=='M04':required[0]=True
    elif family=='M07':required[:s['wait']]=True
    missing=~np.isfinite(a).all(axis=2)
    cmd[missing & required[None,:]]=np.inf
    # Tradable tick rounding. Entry-generated target formulas use base slippage;
    # stress executions keep the same nominal signal levels (no hindsight repricing).
    target=np.round(target*4)/4
    diagnostics['eligible_days']=int(eligible.sum())
    diagnostics['command_days']=int((np.any(np.isfinite(cmd)&(cmd!=0),axis=1)&eligible).sum())
    return cmd,st,target,end,eligible,entries,diagnostics

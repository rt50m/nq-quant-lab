"""R4 candidate events. Minute t confirms at t+1; orders never use future candles."""
import math
import numpy as np
import pandas as pd
from numba import njit
from features import lag
import model31


@njit(cache=True)
def cusum(z,k):
    out=np.full((len(z),390,2),np.nan)
    for d in range(len(z)):
        plus=0.;minus=0.
        for t in range(1,390):
            if not np.isfinite(z[d,t]):plus=0.;minus=0.;continue
            plus=max(0.,plus+z[d,t]-k);minus=max(0.,minus-z[d,t]-k)
            out[d,t,0]=plus;out[d,t,1]=minus
    return out


@njit(cache=True)
def vr_score(r,n,q):
    out=np.full_like(r,np.nan)
    for d in range(len(r)):
        for t in range(n,390):
            x=r[d,t-n+1:t+1]
            if not np.isfinite(x).all():continue
            x=x-np.mean(x);ss=np.sum(x*x)
            if ss<=0:continue
            vr=0.;theta=0.
            for j in range(1,q):
                w=2*(1-j/q)
                vr+=w*np.sum(x[j:]*x[:-j])/ss
                theta+=w*w*np.sum(x[j:]**2*x[:-j]**2)/(ss*ss)
            if theta>0:out[d,t]=vr/math.sqrt(theta)
    return out


@njit(cache=True)
def smooth_close(close,k):
    # Trailing local linear fit, evaluated at the last observed point.
    n=len(close);out=np.full(n,np.nan)
    x=np.arange(k,dtype=np.float64);weight=np.arange(1,k+1,dtype=np.float64)
    xm=np.sum(weight*x)/np.sum(weight);den=np.sum(weight*(x-xm)**2)
    for t in range(k-1,n):
        y=close[t-k+1:t+1]
        if not np.isfinite(y).all():continue
        ym=np.sum(weight*y)/np.sum(weight)
        slope=np.sum(weight*(x-xm)*(y-ym))/den
        out[t]=ym+slope*(k-1-xm)
    return out


@njit(cache=True)
def orb_events(a,eligible,atr,night,vwap,number,p,daily,aux):
    result=np.full((len(a),390,4),np.nan)
    for d in range(len(a)):
        if not eligible[d]:continue
        o=a[d,:,0];h=a[d,:,1];l=a[d,:,2];c=a[d,:,3]
        opening=int(p[0])
        if number==4:
            if not np.isfinite(daily[d,0]):continue
            cum=0.;opening=0
            for t in range(45):
                if not np.isfinite(a[d,t]).all():break
                cum+=a[d,t,4]
                if t>=4 and cum>=daily[d,0]:opening=t+1;break
            if opening==0:continue
        if number==16:opening=int(p[2])
        if not np.isfinite(a[d,:opening]).all():continue
        H=np.max(h[:opening]);L=np.min(l[:opening]);W=H-L
        if W<=0:continue
        if number==1 and daily[d,0]!=1:continue
        if number in [2,14] and not np.isfinite(night[d]).all():continue
        smooth=smooth_close(c,int(p[1])) if number==21 else c
        piv=np.empty(5);pt=np.empty(5,dtype=np.int64);npiv=0;lastkind=0;shape=-1
        first=0;first_t=-1;returned=False;inside_count=0;extreme=0.;boxh=np.nan;boxl=np.nan;box_t=-1
        denied=np.zeros(2,np.bool_);done=np.zeros(2,np.bool_)
        visits=np.zeros(2,np.int64);away=np.ones(2,np.bool_)
        stages=np.zeros(2,np.int64);starts=np.full(2,-1,np.int64);holds=np.zeros(2,np.int64)
        alarms=np.full(2,-1000,np.int64)
        large=0;small=0;large_ext=c[opening-1];small_ext=large_ext;dc_stage=0;dc_direction=0;dc_t=-1
        for t in range(opening,389):
            if not np.isfinite(a[d,t]).all():break
            side=1 if c[t]>H else -1 if c[t]<L else 0
            if first==0 and side:
                first=side;first_t=t;extreme=h[t] if side==1 else l[t]
            if number==21:
                delay=int(p[2]);i=t-delay
                if i-delay>=opening and np.isfinite(smooth[i-delay:t+1]).all():
                    kind=1 if smooth[i]>np.max(smooth[i-delay:i]) and smooth[i]>np.max(smooth[i+1:t+1]) else -1 if smooth[i]<np.min(smooth[i-delay:i]) and smooth[i]<np.min(smooth[i+1:t+1]) else 0
                    if kind and L<smooth[i]<H:
                        if kind==lastkind and npiv:
                            if kind*(smooth[i]-piv[npiv-1])>0:piv[npiv-1]=smooth[i];pt[npiv-1]=i
                        else:
                            if npiv==5:piv[:4]=piv[1:5];pt[:4]=pt[1:5];npiv=4
                            piv[npiv]=smooth[i];pt[npiv]=i;npiv+=1;lastkind=kind
                        if npiv==5 and shape<0:
                            high_ok=True;low_ok=True
                            for j in range(2,5):
                                is_high=(lastkind==1 and j%2==0) or (lastkind==-1 and j%2==1)
                                if is_high and piv[j]>=piv[j-2]:high_ok=False
                                if not is_high and piv[j]<=piv[j-2]:low_ok=False
                            first_width=abs(piv[1]-piv[0]);last_width=abs(piv[4]-piv[3])
                            if high_ok and low_ok and first_width>0 and last_width<=(1-p[3])*first_width:shape=t
            if number==22:
                for j in range(2):
                    if np.isfinite(aux[d,t,j]) and aux[d,t,j]>daily[d,j]:alarms[j]=t
            if number==28:
                big=p[1]*p[2]*atr[d];little=p[1]*atr[d]
                for which in range(2):
                    state=large if which==0 else small;ex=large_ext if which==0 else small_ext;delta=big if which==0 else little
                    prior_state=state
                    if state==0:
                        if c[t]>=ex+delta:state=1;ex=c[t]
                        elif c[t]<=ex-delta:state=-1;ex=c[t]
                    elif state==1:
                        ex=max(ex,c[t])
                        if c[t]<=ex-delta:state=-1;ex=c[t]
                    else:
                        ex=min(ex,c[t])
                        if c[t]>=ex+delta:state=1;ex=c[t]
                    if which==0:
                        if state!=prior_state:dc_stage=0;dc_direction=state;dc_t=t
                        large=state;large_ext=ex
                    else:
                        if large and state!=prior_state:
                            if state==-large:dc_stage=1;dc_direction=large;dc_t=t
                            elif state==large and dc_stage==1:dc_stage=2;dc_t=t
                        small=state;small_ext=ex
            if number in [7,8,9,17,24] and first:
                extreme=max(extreme,h[t]) if first==1 else min(extreme,l[t])
            for j in range(2):
                direction=1 if j==0 else -1;boundary=H if direction==1 else L
                if done[j] or denied[j]:continue
                fire=False;st=np.nan;target=np.nan;limit=np.nan
                if number==6:
                    distance=direction*(boundary-c[t])/W
                    if p[2]>=distance>=0 and away[j]:visits[j]+=1;away[j]=False
                    elif distance>=p[3]:away[j]=True
                    if side==direction:
                        fire=visits[j]>=p[1];denied[j]=not fire
                elif number==7:
                    if first and t>first_t and L<c[t]<H:returned=True
                    fire=first==-direction and returned and side==direction and t-first_t<=p[1]
                elif number==8:
                    if first==direction and t>first_t:
                        if side==-direction:denied[j]=True
                        depth=direction*(boundary-c[t])/W
                        if L<c[t]<H:
                            if depth>=p[1]:returned=True
                            if returned:inside_count+=1
                        elif side==direction:
                            fire=returned and inside_count>=p[2] and t-first_t<=p[3]
                            # This is only the second attempt, never a third retry.
                            denied[j]=True
                elif number==9:
                    if first==direction:
                        if t>first_t and direction*(c[t]-boundary)<=0:denied[j]=True
                        if t-first_t>30:denied[j]=True
                        if direction*(c[t]-boundary)>=p[1]*W and stages[j]==0:stages[j]=1;starts[j]=t
                        k=int(p[2])
                        if stages[j]==1 and t-starts[j]>=k:
                            bh=np.max(h[t-k+1:t+1]);bl=np.min(l[t-k+1:t+1])
                            external=bl>=H+.25 if direction==1 else bh<=L-.25
                            if bh-bl<=p[3]*W and external:boxh=bh;boxl=bl;box_t=t;stages[j]=2
                        elif stages[j]==2 and t>box_t:
                            fire=c[t]>boxh if direction==1 else c[t]<boxl
                elif number==12:
                    signed=direction*(c[t]-vwap[d,t])
                    if side==-direction:denied[j]=True
                    if stages[j] and t-starts[j]>p[2]:stages[j]=0
                    if stages[j]==0 and signed<0:stages[j]=1;starts[j]=t
                    elif stages[j]==1 and signed>0:stages[j]=2;holds[j]=1
                    elif stages[j]==2:
                        if signed<=0:stages[j]=0
                        else:
                            holds[j]+=1
                            if holds[j]>=p[1] and L<c[t]<H:stages[j]=3
                            elif side==direction:denied[j]=True
                    elif stages[j]==3:
                        if signed<=0:stages[j]=0
                        elif side==direction:fire=True
                elif number==17:
                    if first==-direction and t>first_t:
                        b=L if first==-1 else H
                        depth=direction*(c[t]-b)/W
                        if L<c[t]<H and depth>=p[2] and t-first_t<=p[1]:
                            fire=True;target=(H+L)/2;st=extreme
                elif number==24:
                    if first==direction:
                        if side==-direction:denied[j]=True
                        if stages[j]==0 and daily[d,0]==1 and t>first_t and t-first_t>=p[2]:
                            if np.isfinite(aux[d,t,0]) and aux[d,t,0]<=aux[d,t,1]:
                                stages[j]=1;starts[j]=t;boxh=extreme;boxl=extreme
                        elif stages[j]==1 and t>starts[j] and t-first_t<=p[4]:
                            fire=(c[t]>max(H,boxh)) if direction==1 else (c[t]<min(L,boxl))
                elif number==27:
                    k=int(p[1])
                    if side==direction and stages[j]==0:denied[j]=True
                    if t>=2*k and stages[j]==0 and aux[d,t-k,0]<-p[3] and aux[d,t,0]>p[3]:
                        stages[j]=1;starts[j]=t
                    elif stages[j]==1 and side==direction and 0<t-starts[j]<=p[4]:fire=True
                elif number==28:
                    fire=side==direction and dc_stage==2 and large==direction and dc_direction==direction and 0<t-dc_t<=p[3]
                    if side==direction and not fire:denied[j]=True
                else:
                    fire=side==direction
                    if number==2:fire=fire and direction*(night[d,j]-boundary)>=.25 and direction*(night[d,j]-boundary)<=p[1]*W and direction*(c[t]-night[d,j])>0
                    elif number==3:
                        prior=daily[d,j]
                        good=direction*(o[0]-prior)>0
                        for k in range(t+1):
                            if direction*(c[k]-prior)<=0:good=False
                        fire=fire and good
                    elif number==5:fire=fire and daily[d,0]>=p[1] and direction*daily[d,1]>0
                    elif number==11:
                        k=int(p[1]);fire=fire and t>=k and direction*(c[t]-vwap[d,t])>0 and direction*(vwap[d,t]-vwap[d,t-k])/atr[d]>p[2]
                    elif number==14:fire=fire and direction*(c[t]-vwap[d,t])>0 and direction*(vwap[d,t]-night[d,2])/atr[d]>p[1]
                    elif number==15:
                        if fire:limit=boundary-direction*p[1]*W
                    elif number==16:fire=fire and daily[d,j]==1
                    elif number==21:
                        fire=fire and shape>=0 and 0<t-shape<=p[4]
                        if side and shape<0:denied[:]=True
                    elif number==22:fire=fire and np.isfinite(daily[d,j]) and aux[d,t,j]>daily[d,j] and t-alarms[1-j]>p[4]
                    elif number==23:
                        end=opening+int(p[3]);fire=fire and t+1<end and abs(daily[d,1])>=p[5]*atr[d] and direction*(daily[d,0]-c[t])>p[6]
                    elif number==29:fire=fire and daily[d,0]<=p[2]
                    elif number==30:
                        if t<30 and side==direction:denied[j]=True
                        fire=fire and t>=30 and daily[d,0]>=0 and daily[d,0]<=daily[d,1] and daily[d,0]*c[29]<=p[4]*W
                if fire and not (denied[j] and number not in [8]):
                    result[d,t+1,0]=direction;result[d,t+1,1]=st;result[d,t+1,2]=target;result[d,t+1,3]=limit
                    done[j]=True
    return result


PARAMS={
1:['narrow'],2:['separation'],3:[],4:['quota','history'],5:['efficiency'],
6:['visits','band','away'],7:['expiry'],8:['depth','hold','expiry'],9:['impulse','box_bars','box_width'],
10:[],11:['slope_bars','slope_atr'],12:['hold','expiry'],13:[],14:['vwap_gap'],15:['limit_depth','limit_life'],
16:[],17:['expiry','depth'],18:[],19:[],20:[],21:['smooth','pivot_delay','contraction','expiry'],
22:['history','drift','alarm_quantile','expiry'],23:['volume_history','training','horizon','ridge','interaction_atr','cost_multiple'],
24:['jump_high','rebuild','jump_low','expiry'],25:[],26:[],27:['block','lag','score','expiry'],28:['small_atr','scale_ratio','expiry'],
29:['history','residual_z'],30:['history','spread_quantile','unused','spread_width']}


def build(f,s):
    number=int(s['model'][-2:])
    if number==31:return model31.build(f,s)
    opening=s.get('opening',15)
    p=np.zeros(12);p[0]=opening
    for i,key in enumerate(PARAMS[number],1):p[i]=s.get(key,0)
    n=len(f.a);daily=np.full((n,3),np.nan);aux=np.full((n,390,2),np.nan)
    if number==1:
        width=f.hi-f.lo;N=s['narrow']
        for d in range(max(2,N),n):
            daily[d,0]=float(f.hi[d-1]<f.hi[d-2] and f.lo[d-1]>f.lo[d-2] and np.isfinite(width[d-N:d]).all() and width[d-1]<=min(width[d-N:d]))
    elif number==3:daily[:,0]=np.r_[np.nan,f.hi[:-1]];daily[:,1]=np.r_[np.nan,f.lo[:-1]]
    elif number==4:
        vols=np.sum(f.a[:,:15,4],axis=1);vols[~f.normal]=np.nan
        # Use the prior N valid normal sessions, never the current opening volume.
        for d in range(n):
            v=vols[:d];v=v[np.isfinite(v)]
            if len(v)>=s['history']:daily[d,0]=np.median(v[-s['history']:])*s['quota']
    elif number==5:
        move=f.a[:,opening-1,3]-f.a[:,0,0]
        path=abs(f.a[:,0,3]-f.a[:,0,0])+np.sum(abs(np.diff(f.a[:,:opening,3],axis=1)),axis=1)
        daily[:,0]=np.divide(abs(move),path,out=np.full(n,np.nan),where=path>0);daily[:,1]=move
    elif number==16:
        short,long=s['nested'];p[1]=short;p[2]=long
        for d in range(n):
            a=f.a[d]
            if not np.isfinite(a[:long]).all():continue
            for j,side in enumerate([1,-1]):
                b=max(a[:short,1]) if side==1 else min(a[:short,2])
                ext=max(a[:long,1]) if side==1 else min(a[:long,2])
                breaks=np.flatnonzero(side*(a[short:long,3]-b)>0)
                daily[d,j]=float(len(breaks)>0 and np.all(side*(a[short+breaks[0]:long,3]-b)>0) and side*(ext-b)>=.25)
    elif number==22:
        aux=cusum(f.standardized(s['history']),s['drift'])
        for j in range(2):
            valid=np.isfinite(aux[:,:,j]).any(axis=1)
            maxima=np.max(np.where(np.isfinite(aux[:,:,j]),aux[:,:,j],-np.inf),axis=1)
            maxima[~valid]=np.nan;daily[:,j]=lag(maxima,s['history'],'quantile',s['alarm_quantile'])[:,0]
    elif number==23:
        vol=np.sum(f.a[:,:opening,4],axis=1)
        mean=lag(vol,s['volume_history'])[:,0];sd=lag(vol,s['volume_history'],'std')[:,0]
        v=np.divide(vol-mean,sd,out=np.full(n,np.nan),where=sd>0)
        x=(f.a[:,opening-1,3]-f.a[:,0,0])/f.atr
        end=opening+s['horizon']
        y=(f.a[:,end,0]-f.a[:,opening-1,3])/f.atr
        X=np.c_[x,x*v]
        for d in range(n):
            left=max(0,d-s['training']);xx=X[left:d];yy=y[left:d]
            good=np.isfinite(xx).all(axis=1)&np.isfinite(yy)
            if good.sum()<80 or not np.isfinite(X[d]).all():continue
            xx=xx[good];yy=yy[good];mean=xx.mean(axis=0);scale=xx.std(axis=0)
            if (scale<=0).any():continue
            Z=np.c_[np.ones(len(xx)),(xx-mean)/scale]
            penalty=np.diag([0.,s['ridge']*len(xx),s['ridge']*len(xx)])
            beta=np.linalg.solve(Z.T@Z+penalty,Z.T@yy)
            pred=np.r_[1.,(X[d]-mean)/scale]@beta
            daily[d,0]=f.a[d,opening-1,3]+pred*f.atr[d]
            daily[d,1]=beta[2]/scale[1]*X[d,1]*f.atr[d]
        p[6]=s['cost_multiple']*(.5+.5) # two sides of slippage plus conservative MNQ fees in points
    elif number==24:
        jump=f.jump(opening-1)[:,opening-1]
        threshold=lag(jump,60,'quantile',s['jump_high'])[:,0]
        daily[:,0]=np.where(np.isfinite(threshold),jump>=threshold,np.nan)
        aux[:,:,0]=f.jump(s['rebuild']);aux[:,:,1]=lag(aux[:,:,0],60,'quantile',s['jump_low'])
    elif number==27:
        score=vr_score(f.ret,s['block'],s['lag']);scale=lag(score,60,'std')
        aux[:,:,0]=np.divide(score,scale,out=np.full_like(score,np.nan),where=scale>0)
    elif number==29:
        money=f.a[:,:opening,4]*f.a[:,:opening,3]*20
        r=abs(f.ret[:,1:opening]);money=money[:,1:]
        ratio=np.divide(r,money,out=np.full_like(r,np.nan),where=money>0)
        impact=np.mean(ratio,axis=1)
        value=np.log(np.where(impact>0,impact,np.nan))
        mean=lag(value,s['history'])[:,0];sd=lag(value,s['history'],'std')[:,0]
        daily[:,0]=np.divide(value-mean,sd,out=np.full(n,np.nan),where=sd>0)
    elif number==30:
        H1=np.max(f.a[:,:15,1],axis=1);L1=np.min(f.a[:,:15,2],axis=1)
        H2=np.max(f.a[:,15:30,1],axis=1);L2=np.min(f.a[:,15:30,2],axis=1)
        beta=np.log(H1/L1)**2+np.log(H2/L2)**2;gamma=np.log(np.maximum(H1,H2)/np.minimum(L1,L2))**2
        denom=3-2*np.sqrt(2);alpha=(np.sqrt(2*beta)-np.sqrt(beta))/denom-np.sqrt(gamma/denom)
        spread=2*np.tanh(alpha/2)
        spread[(alpha<0)|(H1<=L1)|(H2<=L2)]=np.nan
        daily[:,0]=spread;daily[:,1]=lag(spread,s['history'],'quantile',s['spread_quantile'])[:,0]
    return orb_events(f.a,f.eligible,f.atr,f.night,f.vwap,number,p,daily,aux)

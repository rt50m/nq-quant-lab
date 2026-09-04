"""Whole-contract, one-episode replay with conservative minute-bar ordering."""
import math
import numpy as np
from numba import njit


@njit(cache=True)
def outward(value,side):
    return math.floor(value*4+1e-8)/4 if side==1 else math.ceil(value*4-1e-8)/4


@njit(cache=True)
def size(distance,budget,slip,nqfee,mnqfee,maxnq,maxmnq):
    if distance<=0 or budget<=0:return 0,2.,mnqfee
    q=min(maxnq,int(budget//((distance+slip)*20+2*nqfee)))
    if q:return q,20.,nqfee
    return min(maxmnq,int(budget//((distance+slip)*2+2*mnqfee))),2.,mnqfee


@njit(cache=True)
def posterior_path(z,hazard,recent):
    """Gaussian known-variance BOCPD, N(0,1) mean prior on standardized returns.

    Keep every possible run length in this single-session horizon. The event is
    posterior run length 1..recent AND adverse mean, excluding constant reset mass.
    """
    n=len(z);out=np.full((n,2),np.nan)
    probability=np.zeros(n+1);probability[0]=1.
    mean=np.zeros(n+1);precision=np.ones(n+1)
    for t in range(n):
        if not np.isfinite(z[t]):break
        k=t+1;predict=np.empty(k)
        for r in range(k):
            variance=1+1/precision[r]
            predict[r]=math.exp(-.5*(z[t]-mean[r])**2/variance)/math.sqrt(2*math.pi*variance)
        weight=probability[:k]*predict
        new=np.zeros(n+1);new[0]=np.sum(weight)*hazard
        new[1:k+1]=weight*(1-hazard)
        total=np.sum(new)
        if total<=0:break
        new/=total
        for r in range(k,0,-1):
            mean[r]=(mean[r-1]*precision[r-1]+z[t])/(precision[r-1]+1)
            precision[r]=precision[r-1]+1
        mean[0]=0.;precision[0]=1.;probability=new
        neg=0.;pos=0.
        for r in range(1,min(recent,k)+1):
            below=.5*(1+math.erf(-mean[r]*math.sqrt(precision[r]/2)))
            neg+=probability[r]*below;pos+=probability[r]*(1-below)
        out[t,0]=neg;out[t,1]=pos
    return out


# output: net, trades, win$, loss$, wins, ambiguity, unknown, qty_skips,
# nq entries, mnq entries, maxqty, max planned risk, protections, final minute,
# worst liquidation P&L, long net, short net, eligible entry events, partials, adds.
@njit(cache=True)
def replay(a,events,atr,vwap,adverse,bayes,number,c,p,account,enforce,slip):
    # c risk, stopATR, targetR, flat(index), cutoff(index), direction, stopbuffer,
    # location(0/1/2 or -1), minimumRR, maxhold. p holds model management settings.
    n=len(a);out=np.zeros((n,20));out[:,13]=-1
    balance=account[0];peak=balance;floor=balance-account[1];status=0;failed=-1
    pointer=0
    for d in range(n):
        if enforce and status:break
        while pointer<len(events) and int(events[pointer,0])<d:pointer+=1
        start=pointer
        while pointer<len(events) and int(events[pointer,0])==d:pointer+=1
        if start==pointer:continue
        day=0.;worst=0.;traded=False
        for e in range(start,pointer):
            if traded:break
            t=int(events[e,1]);side=int(events[e,2]);reference=events[e,3];target=events[e,4];limit=events[e,5]
            H=events[e,6];L=events[e,7]
            if c[5]!=0 and side!=c[5]:continue
            if t>c[4] or t>=c[3] or t>=389:continue
            out[d,17]+=1
            # Resting limit becomes active at the minute after its signal.
            limit_fill=False;entry_t=t
            if number==15:
                found=False
                for k in range(t,min(389,int(min(c[3],c[4]+1,t+p[0])))):
                    if not np.isfinite(a[d,k]).all():break
                    o,h,l,close=a[d,k,0],a[d,k,1],a[d,k,2],a[d,k,3]
                    # Trade-through one tick; a touch alone is not a fill.
                    crossed=l<=limit-.25 if side==1 else h>=limit+.25
                    if crossed:
                        entry_t=k;found=True;limit_fill=True;break
                    if (close<L if side==1 else close>H):break
                if not found:continue
            if not np.isfinite(a[d,entry_t]).all():continue
            o=a[d,entry_t,0]
            fill=(min(o,limit) if side==1 else max(o,limit)) if limit_fill else o+side*slip
            if c[1]>0:
                stop=outward(fill-side*c[1]*atr[d],side)
            else:
                if not np.isfinite(reference):continue
                stop=outward(reference-side*c[6]*.25,side)
            distance=side*(fill-stop)
            if distance<=0:continue
            if number==31:
                if not L<fill<H:continue
                v=(fill-L)/(H-L) if side==1 else (H-fill)/(H-L)
                location=0 if v<=.25 else 2 if v>=.75 else 1
                if location!=int(c[7]):continue
                if side*(target-fill)/distance<c[8]:continue
            if number not in [17,31]:target=fill+side*c[2]*distance if c[2]>0 else np.nan
            if np.isfinite(target):
                # Limit targets round toward entry, never promise extra reward.
                target=math.floor(target*4+1e-8)/4 if side==1 else math.ceil(target*4-1e-8)/4
                if side*(target-fill)<=0:continue
            allowance=balance-floor-account[7] if enforce else 1e15
            budget=min(c[0],account[3],allowance)
            initial_fraction=p[0] if number==20 else 1.
            q,pv,fee=size(distance,budget*initial_fraction,slip,account[4],account[5],int(account[6]),int(account[8]))
            if q<1:out[d,7]+=1;continue
            fraction=p[0] if number==19 else p[3] if number==25 else 0.
            partial_qty=int(math.floor(q*fraction+1e-9))
            if number in [19,25] and (partial_qty<1 or partial_qty>=q):out[d,7]+=1;continue
            if np.isfinite(target) and side*(target-fill)*pv<=2*fee+slip*pv:continue
            deadline=min(int(c[3]),entry_t+int(c[9]) if number==31 else 389)
            if number==23:deadline=min(deadline,int(p[0]))
            if entry_t>=deadline:continue
            traded=True;entry=fill;initial=fill;initial_q=q;initial_distance=distance
            day=-q*fee;max_close=0.;high=a[d,entry_t,1];low=a[d,entry_t,2]
            out[d,8 if pv==20 else 9]=1;out[d,10]=q
            out[d,11]=(distance+slip)*q*pv+2*q*fee
            partial_done=False;added=0;pending_exit=False;pending_partial=False;pending_add=False
            for k in range(entry_t,390):
                if not np.isfinite(a[d,k]).all():out[d,6]=1;break
                o,h,l,close=a[d,k,0],a[d,k,1],a[d,k,2],a[d,k,3]
                active=stop
                headroom=balance-floor-account[7] if enforce else 1e15
                effective=min(account[3],headroom)
                protective=entry+side*(-effective-day+q*fee+slip*q*pv)/(q*pv)
                protective=math.ceil(protective*4-1e-8)/4 if side==1 else math.floor(protective*4+1e-8)/4
                protection=side*(protective-active)>0
                if protection:active=protective
                price=np.nan;why=0
                # A limit filled after the open cannot use an earlier opening quote
                # as an exit. That entry bar uses conservative stop-first handling.
                at_open=(k>entry_t or not limit_fill or side*(o-limit)<=0)
                if at_open and side*(o-active)<=0:price=o-side*slip;why=1
                elif at_open and np.isfinite(target) and side*(o-target)>=0:price=target;why=2
                elif k>=deadline or k==389 or pending_exit:price=o-side*slip;why=3
                if why==0 and pending_partial:
                    amount=min(partial_qty,q-1)
                    if amount>0:
                        price_partial=o-side*slip
                        day+=side*(price_partial-entry)*amount*pv-amount*fee;q-=amount;out[d,18]+=1
                    pending_partial=False;partial_done=True
                if why==0 and pending_add and number==20:
                    cap=int(account[6]) if pv==20 else int(account[8])
                    newfill=o+side*slip;newdist=side*(newfill-stop)
                    if newdist>0 and side*(newfill-initial)>0:
                        # Preserve reserved tranche budgets and cap worst episode
                        # loss including all paid fees and future liquidation fees.
                        current_loss=-day+side*(entry-stop)*q*pv+q*fee+slip*q*pv
                        room=min(budget-current_loss,account[3]-current_loss,headroom-current_loss)
                        tranche=budget*(1-p[0])/p[1]
                        extra=min(cap-q,int(max(0.,min(room,tranche))//((newdist+slip)*pv+2*fee)))
                        if extra>0:
                            entry=(entry*q+newfill*extra)/(q+extra);q+=extra;day-=extra*fee
                            out[d,19]+=1;out[d,10]=max(out[d,10],q)
                            planned=-day+side*(entry-stop)*q*pv+q*fee+slip*q*pv
                            out[d,11]=max(out[d,11],planned)
                    added+=1;pending_add=False
                if why==0:
                    hitstop=l<=active if side==1 else h>=active
                    hittarget=np.isfinite(target) and (h>=target if side==1 else l<=target)
                    partial_level=initial+side*p[1]*initial_distance if number==19 else np.nan
                    hitpartial=number==19 and not partial_done and (h>=partial_level if side==1 else l<=partial_level)
                    if hitstop:
                        price=active-side*slip;why=1
                        if hittarget or hitpartial or (limit_fill and k==entry_t):out[d,5]+=1
                    elif hittarget:
                        price=target;why=2
                        if limit_fill and k==entry_t:
                            # Intrabar target may precede the resting-limit fill.
                            # Do not credit that same-minute target; preserve exposure.
                            price=np.nan;why=0;out[d,5]+=1
                    elif hitpartial:
                        partial_level=math.floor(partial_level*4+1e-8)/4 if side==1 else math.ceil(partial_level*4-1e-8)/4
                        day+=side*(partial_level-entry)*partial_qty*pv-partial_qty*fee;q-=partial_qty
                        out[d,18]+=1;partial_done=True
                if why:
                    day+=side*(price-entry)*q*pv-q*fee;worst=min(worst,day);out[d,13]=k
                    if why==1 and protection:out[d,12]+=1
                    q=0;break
                adverse_price=l if side==1 else h
                worst=min(worst,day+side*(adverse_price-entry)*q*pv-q*fee-slip*q*pv)
                # Completed-candle management below takes effect NEXT minute.
                max_close=max(max_close,side*(close-initial));high=max(high,h);low=min(low,l)
                if number==10 and k-entry_t+1==int(p[0]) and max_close<p[1]*initial_distance:pending_exit=True
                elif number==13 and np.isfinite(vwap[d,k]):
                    candidate=outward(vwap[d,k]-side*p[0]*atr[d],side)
                    stop=max(stop,candidate) if side==1 else min(stop,candidate)
                elif number==18:
                    look=int(p[0])
                    if k>=look and np.isfinite(a[d,k-look:k+1]).all():
                        tr=0.
                        for j in range(k-look+1,k+1):tr+=max(a[d,j,1]-a[d,j,2],abs(a[d,j,1]-a[d,j-1,3]),abs(a[d,j,2]-a[d,j-1,3]))
                        candidate=outward((high if side==1 else low)-side*p[1]*tr/look,side)
                        stop=max(stop,candidate) if side==1 else min(stop,candidate)
                elif number==20 and added<int(p[1]) and side*(close-initial)>=(added+1)*p[2]*initial_distance:pending_add=True
                elif number==25 and not partial_done:
                    look=int(p[0])
                    if k-entry_t>=look:
                        total=0.;bad=0.
                        for j in range(k-look+1,k+1):
                            r=math.log(a[d,j,3]/a[d,j-1,3]);total+=r*r
                            if side*r<0:bad+=r*r
                        threshold=adverse[d,k,0 if side==1 else 1]
                        if total>0 and bad/total>=p[1] and np.isfinite(threshold) and bad>threshold:pending_partial=True
                elif number==26 and k-entry_t+1>=int(p[3]):
                    probability=bayes[d,k,0 if side==1 else 1]
                    if np.isfinite(probability) and probability>=p[2]:pending_exit=True
            if q or out[d,6]:
                out[d,6]=1
                if enforce:status=2;failed=d
                break
            out[d,0]=day;out[d,1]=1;out[d,2]=max(day,0);out[d,3]=min(day,0);out[d,4]=day>0
            out[d,14]=worst;out[d,15 if side==1 else 16]=day
            if enforce and balance+worst<=floor:status=1;failed=d
            balance+=day;peak=max(peak,balance);floor=max(floor,min(account[2],peak-account[1]))
    return out,balance,status,failed


def parameters(config):
    c=config;s=config
    number=int(s['model'][-2:])
    location={'origin':0,'interior':1,'destination':2}
    values=np.array([c['risk'],c.get('stop_atr',0),c.get('target_r',0),c.get('flat',959)-570,
                     c['cutoff']-570,c['direction'],c.get('stop_buffer',0),location.get(c.get('location'),-1),
                     c.get('min_rr',0),c.get('max_hold',390)],dtype=float)
    p=np.zeros(5)
    if number==10:p[:2]=[s['progress_minutes'],s['progress_r']]
    elif number==13:p[0]=s['vwap_offset']
    elif number==15:p[0]=s['limit_life']
    elif number==18:p[:2]=[s['atr_bars'],s['chandelier']]
    elif number==19:p[:2]=[s['partial'],s['partial_r']]
    elif number==20:p[:3]=[s['initial_fraction'],s['additions'],s['add_r']]
    elif number==23:p[0]=s['opening']+s['horizon']
    elif number==25:p[:4]=[s['observe'],s['adverse_share'],s['magnitude_quantile'],s['partial']]
    elif number==26:p[:4]=[s['hazard'],s['recent_run'],s['posterior'],s['minimum_observations']]
    return values,p


def event_rows(f,signals,opening=15):
    days,times=np.where(np.isfinite(signals[:,:,0])&(signals[:,:,0]!=0))
    if not len(days):return np.empty((0,8))
    H=np.max(f.a[:,:opening,1],axis=1);L=np.min(f.a[:,:opening,2],axis=1)
    return np.ascontiguousarray(np.c_[days,times,signals[days,times],H[days],L[days]])

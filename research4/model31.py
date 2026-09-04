"""One-minute inside-range candidate events. All decisions use completed bars only."""
import numpy as np
from numba import njit


@njit(cache=True)
def displacement(o,h,l,c,t,m,b):
    if t<20 or h[t]<=l[t] or c[t]<=o[t]:return False
    history=np.abs(c[t-20:t]-o[t-20:t])
    if not np.isfinite(history).all():return False
    reference=np.median(history)
    return reference>0 and c[t]-o[t]>=m*reference and (c[t]-o[t])/(h[t]-l[t])>=b and (h[t]-c[t])/(h[t]-l[t])<=.2


@njit(cache=True)
def candidates(a,eligible,family,p):
    # p: expiry, edge, lookback, hold, gap ticks, age, formation(0/1),
    # schedule(0/1), displacement, body multiple/fraction, excursion, separation,
    # tolerance, box bars/width. Output columns side, stop reference, target, limit.
    result=np.full((len(a),390,4),np.nan)
    for d in range(len(a)):
        if not eligible[d] or not np.isfinite(a[d,:15]).all():continue
        for side in [1,-1]:
            o=a[d,:,0]*side;c=a[d,:,3]*side
            h=a[d,:,1 if side==1 else 2]*side;l=a[d,:,2 if side==1 else 1]*side
            H=np.max(h[:15]);L=np.min(l[:15]);W=H-L;mid=(H+L)/2
            if W<=0:continue
            volume=a[d,:,4];cumv=0.;cumm=0.;vw=np.full(390,np.nan)
            for t in range(390):
                cumv+=volume[t];cumm+=(h[t]+l[t]+c[t])/3*volume[t]
                if cumv>0:vw[t]=cumm/cumv
            state=0;start=-1;count=0;low=0.;anchor=0.;neck=0.;reclaim=0
            gaplo=np.full(390,np.nan);gaphi=gaplo.copy();live=np.zeros(390,np.bool_)
            selected=-1;inverted=-1
            for t in range(2,389):
                if not np.isfinite(a[d,t]).all():
                    state=0;selected=-1;live[:]=False;continue
                inside=L<c[t]<H;fire=False;stop=np.nan
                if family==4 or family==6:
                    valid3=np.isfinite(a[d,t-2:t+1]).all()
                    # D needs an opposing (bearish, in reflected coordinates) gap.
                    lo=h[t] if family==4 else h[t-2]
                    hi=l[t-2] if family==4 else l[t]
                    allowed=(p[6]==0 and t<15) or (p[6]==1 and t>=15) if family==4 else t>=15
                    if valid3 and allowed and hi-lo>=p[4]*.25 and (family==4 or L<lo<hi<H):
                        gaplo[t]=lo;gaphi[t]=hi;live[t]=True
                    if family==4:
                        newest=-1
                        for g in range(2,t):
                            if not live[g]:continue
                            if t-g>p[5]:live[g]=False;continue
                            if c[t]>gaphi[g]:
                                live[g]=False
                                if t>=15:newest=g
                        if selected>=0:
                            g=selected
                            if t-inverted>p[0] or c[t]<gaplo[g] or h[t]>=H:selected=-1
                            elif t>inverted and l[t]<=gaphi[g] and h[t]>=gaplo[g] and c[t]>gaphi[g]:
                                fire=inside;stop=np.min(l[g-2:t+1]);selected=-1
                        if newest>=0 and selected<0 and not fire:
                            g=newest
                            strong=p[8]==0 or displacement(o,h,l,c,t,p[9],p[10])
                            if strong and inside:
                                if p[7]==0:fire=True;stop=np.min(l[g-2:t+1])
                                else:selected=g;inverted=t
                    else:
                        latest=-1
                        for g in range(15,t):
                            if live[g] and (t-g>p[0] or c[t]<gaplo[g] or h[t]>=H):live[g]=False
                            if live[g]:latest=g
                        if latest>=0:
                            g=latest
                            if l[t]<=gaphi[g] and h[t]>=gaplo[g] and c[t]>gaphi[g]:
                                fire=inside;stop=np.min(l[g-2:t+1]);live[g]=False
                if t<15:continue
                if state and t-start>p[0]:state=0;count=0
                if family==1:
                    if state:
                        low=min(low,l[t]);k=int(p[2])
                        if inside and c[t]<mid and c[t]>np.max(h[t-k:t]):fire=True;stop=low;state=0
                    elif inside and l[t]<=L+p[1]*W:state=1;start=t;low=l[t]
                elif family==2:
                    if state:
                        low=min(low,l[t])
                        if c[t]>=H:state=0
                        elif inside:
                            if state==1:state=2;count=0
                            else:
                                count+=1
                                if count>=p[3]:fire=True;stop=low;state=0
                        else:state=1;count=0
                    elif c[t]<L:state=1;start=t;low=l[t]
                elif family==3 or family==9:
                    ref=mid if family==3 else vw[t]
                    valid=inside and np.isfinite(ref) and L<ref<H
                    if not valid:state=0;count=0
                    elif state==0:
                        if c[t]<ref:state=1;start=t;count=1
                    elif state==1:
                        if c[t]<ref:count+=1
                        elif c[t]>ref and count>=2:state=2;count=0;low=l[t]
                        else:state=0;count=0
                    elif state==2:
                        low=min(low,l[t])
                        if c[t]<=ref:state=0;count=0
                        else:
                            count+=1
                            if count>=p[3]:fire=True;stop=low;state=0
                elif family==5:
                    fire=inside and displacement(o,h,l,c,t,p[9],p[10]);stop=l[t]
                elif family==7:
                    if state:
                        low=min(low,l[t])
                        if not inside or h[t]>=H:state=0
                        elif c[t]>anchor:fire=True;stop=low;state=0
                    elif L<c[t-1]<H and l[t]<=L-p[11]*.25 and inside:
                        if p[7]==0:fire=True;stop=l[t]
                        else:state=1;start=t;low=l[t];anchor=h[t]
                elif family==8:
                    if state:
                        low=min(low,l[t])
                        if not inside or h[t]>=H:state=0
                        elif state==1:
                            neck=max(neck,h[t])
                            if c[t]>=anchor+p[12]*W:state=2
                        elif state==2:
                            if abs(l[t]-anchor)<=p[13]*W and L<neck<H:state=3
                            else:neck=max(neck,h[t])
                        elif c[t]>neck:fire=True;stop=low;state=0
                    elif inside and l[t]<=L+p[1]*W:
                        state=1;start=t;anchor=l[t];low=l[t];neck=-np.inf
                elif family==10:
                    k=int(p[14])
                    if t>=15+k and np.isfinite(a[d,t-k:t]).all():
                        upper=np.max(h[t-k:t]);lower=np.min(l[t-k:t])
                        if L<lower<upper<H and upper-lower<=p[15]*W and upper<c[t]<H:fire=True;stop=lower
                if fire and inside and np.isfinite(stop):
                    # If both directions confirm together, cancel that timestamp.
                    if np.isfinite(result[d,t+1,0]):result[d,t+1,0]=0.
                    else:
                        result[d,t+1,0]=side
                        result[d,t+1,1]=stop*side
                        result[d,t+1,2]=H*side
    return result


def build(f,s):
    p=np.array([s.get('expiry',0),s.get('edge',0),s.get('lookback',1),s.get('hold',1),
                s.get('min_gap',1),s.get('max_age',0),0 if s.get('formation')=='opening' else 1,
                int(s.get('schedule') in ['retest','confirmed']),int(s.get('displacement',False)),
                s.get('body_multiple',1.5),s.get('body_fraction',.6),s.get('excursion_ticks',1),
                s.get('separation',.1),s.get('tolerance',.025),s.get('box_bars',3),s.get('box_width',.1)],dtype=float)
    return candidates(f.a,f.eligible,ord(s['family'])-64,p)

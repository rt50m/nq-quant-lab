from __future__ import annotations
import numpy as np

COST={
    'slip':0.25,'nq_pv':20.0,'mnq_pv':2.0,'nq_comm':3.5,'mnq_comm':1.0,'max_nq':4,'max_mnq':40
}


def trade_sizing(trades,mode,spec):
    n=len(trades);pv=np.zeros(n);comm=np.zeros(n);qty=np.zeros(n,dtype=int);exposure=np.zeros(n,dtype=int);ok=np.zeros(n,dtype=bool)
    if mode=='MNQ':
        q=int(spec);ok[:]=q>0;qty[:]=q;pv[:]=COST['mnq_pv'];comm[:]=COST['mnq_comm'];exposure[:]=q
    elif mode=='NQ':
        q=int(spec);ok[:]=q>0;qty[:]=q;pv[:]=COST['nq_pv'];comm[:]=COST['nq_comm'];exposure[:]=10*q
    elif mode=='RISK':
        b=float(spec)
        for i,t in enumerate(trades):
            stop=float(t[6]);nr=(stop+COST['slip'])*COST['nq_pv']+COST['nq_comm'];mr=(stop+COST['slip'])*COST['mnq_pv']+COST['mnq_comm']
            qn=min(COST['max_nq'],int(b//nr));qm=min(COST['max_mnq'],int(b//mr));en=10*qn;em=qm
            if en<=0 and em<=0:continue
            if en>=em:qty[i]=qn;pv[i]=COST['nq_pv'];comm[i]=COST['nq_comm'];exposure[i]=en
            else:qty[i]=qm;pv[i]=COST['mnq_pv'];comm[i]=COST['mnq_comm'];exposure[i]=em
            ok[i]=True
    else:raise ValueError(mode)
    return ok,pv,comm,qty,exposure


def build_physical_path(trades,a,mode,spec,ndays):
    T=ndays*390;delta=np.zeros(T,dtype=np.float32);adverse=np.zeros(T,dtype=np.float32);expo=np.zeros(T,dtype=np.uint8)
    ok,pv,comm,qty,eq=trade_sizing(trades,mode,spec);trade_pnl=[]
    for i,t in enumerate(trades):
        if not ok[i]:continue
        d,entry_i,exit_i,side=int(t[0]),int(t[1]),int(t[2]),int(t[3]);pvv=float(pv[i]);q=int(qty[i]);fee=float(comm[i])*q
        pnl=float(t[4])*pvv*q-fee;worst=float(t[5])*pvv*q-fee
        idx=d*390+exit_i;delta[idx]+=pnl;trade_pnl.append(pnl)
        for k in range(entry_i,exit_i+1):
            if not np.isfinite(a[d,k]).all():continue
            if side==1:wp=float(a[d,k,2])-COST['slip']-float(t[7])
            else:wp=float(t[7])-(float(a[d,k,1])+COST['slip'])
            wp=min(0.0,wp)
            val=min(wp*pvv*q-fee,worst)
            j=d*390+k;adverse[j]+=val
            v=int(expo[j])+int(eq[i]);expo[j]=np.uint8(min(255,v))
    return delta,adverse,expo,np.asarray(trade_pnl,dtype=float),ok


def path_stats_from_trade_pnl(trade_pnl):
    p=np.asarray(trade_pnl,dtype=float);gp=p[p>0].sum();gl=-p[p<0].sum()
    return {'trades':int(len(p)),'profit_factor':float(gp/gl) if gl>0 else (99.0 if gp>0 else 0.0)}

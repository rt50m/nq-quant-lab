"""Manual GitHub batch: verification, all ten families, resumable blocks, analysis."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
from registry import grid, groups, manifest, atomic_json, study_hash, digest
from data import download, prepare
from signals import Features, build
from execution import replay

def evaluate(f,c,sig,enforce=False,slip=None):
    cmd,st,tar,end,eligible,entries,_=sig
    g=grid();a=g['account'];cost=g['costs']
    return replay(f.a,cmd,st,tar,end,eligible,f.atr,c['risk'],c['stop_atr'],entries,
        cost['slippage_per_side_points'] if slip is None else slip,
        cost['nq_commission_per_side'],cost['mnq_commission_per_side'],a['start'],a['max_loss'],
        a['locked_floor'],min(a['daily_loss'],a['personal_daily_stop']),a['account_buffer'],
        a['max_nq'],a['max_mnq'],enforce)

def describe(f,r):
    known=r[:,7]==0;daily=np.where(known,r[:,0],0);eq=np.r_[0,np.cumsum(daily)]
    loss=-r[known,4].sum();sd=daily[f.keep].std(ddof=1)
    result={'net_profit':round(float(daily.sum()),4),'trades':int(r[known,2].sum()),
        'event_days':int(((r[:,10]>0)&known).sum()),
        'profit_factor':float(r[known,3].sum()/loss) if loss>0 else None,
        'max_drawdown':float(np.min(eq-np.maximum.accumulate(eq))),
        'worst_day':float(daily.min()),'win_rate':float(r[known,5].sum()/max(1,r[known,2].sum())),
        'daily_sharpe':float(daily[f.keep].mean()/sd*np.sqrt(252)) if sd>0 else None,
        'missing_path_days':int(r[:,7].sum()),'ambiguous_exits':int(r[:,6].sum()),
        'quantity_zero_skips':int(r[:,8].sum()),'blocked_commands':int(r[:,9].sum()),
        'nq_entries':int(r[:,12].sum()),'mnq_entries':int(r[:,13].sum()),
        'long_net':float(r[known,17].sum()),'short_net':float(r[known,18].sum()),
        'worst_intraday_closed_drawdown':float(r[:,19].min()),
        'max_planned_episode_risk':float(r[:,20].max())}
    for y in ['2023','2024','2025']:
        mask=np.char.startswith(f.dates,y);result['net_'+y]=float(daily[mask].sum())
        result['events_'+y]=int(((r[:,10]>0)&known&mask).sum())
    return result

def run_group(f,index,s,configs,out):
    sig=build(f,s);rows=[];daily=[];account_daily=[];known=[];events=[];account_known=[]
    for c in configs:
        raw,*_=evaluate(f,c,sig)
        account,balance,status,fail=evaluate(f,c,sig,True)
        stats=describe(f,raw);acc=describe(f,account)
        row={'id':c['id'],'group':index,'family':s['family'],'control':s['control'],
             'risk':c['risk'],**stats,'account_balance':float(balance),
             'account_net_profit':acc['net_profit'],'account_event_days':acc['event_days'],
             'account_status':['SURVIVED','BREACHED','NEEDS_DATA'][status],
             'account_stop_date':str(f.dates[fail]) if fail>=0 else None,
             'account_quantity_zero_skips':acc['quantity_zero_skips'],
             'account_protection_exits':int(account[:,14].sum()),
             'account_worst_intraday_closed_drawdown':acc['worst_intraday_closed_drawdown'],
             'account_worst_liquidation_day':float(account[:,1].min()),
             'eligible_days':sig[-1]['eligible_days'],'config':c}
        row['prop_screen_pass']=bool(status==0 and stats['missing_path_days']==0 and
            acc['event_days']>=grid()['minimum_event_days'] and balance>grid()['account']['start'] and
            stats['max_drawdown']>-grid()['account']['max_loss'])
        rows.append(row);daily.append(raw[:,0]);account_daily.append(account[:,0])
        known.append(raw[:,7]==0);events.append(raw[:,10]>0)
        mask=account[:,7]==0
        if fail>=0:mask[fail:]=False
        account_known.append(mask)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    name=f'group-{index:04d}'
    tmp=out/(name+'.tmp.npz');final=out/(name+'.npz')
    np.savez_compressed(tmp,ids=np.array([c['id'] for c in configs]),daily=np.array(daily),
        known=np.array(known),events=np.array(events),account_daily=np.array(account_daily),
        account_known=np.array(account_known),eligible=sig[4],dates=f.dates)
    os.replace(tmp,final)
    # Commit marker is written LAST. A partially written group is recomputed.
    atomic_json(out/(name+'.json'),{'study_hash':study_hash(),'data_hash':f.meta['data_hash'],
        'index':index,'npz_sha256':hashlib.sha256(final.read_bytes()).hexdigest(),
        'rows':rows,'diagnostics':sig[-1]})
    return rows

def verified_group(path,expected,data_hash):
    path=Path(path);npz=path.with_suffix('.npz')
    if not path.exists() or not npz.exists():return None
    data=json.loads(path.read_text())
    if data['study_hash']!=study_hash() or data['data_hash']!=data_hash:raise ValueError('Checkpoint version mismatch')
    if [r['config'] for r in data['rows']]!=expected:raise ValueError('Checkpoint manifest mismatch')
    if hashlib.sha256(npz.read_bytes()).hexdigest()!=data['npz_sha256']:raise ValueError('Corrupt checkpoint array')
    return data

def shard(prepared,out,index,count,seconds=14400,limit=0):
    if count<1 or not 0<=index<count:raise ValueError('Invalid shard')
    f=Features(prepared);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    identity={'study_hash':study_hash(),'data_hash':f.meta['data_hash'],'index':index,'count':count,'limit':limit}
    ip=out/'identity.json'
    if ip.exists() and json.loads(ip.read_text())!=identity:raise ValueError('Resume assignment mismatch')
    atomic_json(ip,identity);start=time.monotonic();done=0;expected=0;complete=True
    assigned=[v for v in groups() if v[0]%count==index]
    if limit:assigned=assigned[:limit]
    for i,s,cs in assigned:
        expected+=len(cs)
        if verified_group(out/f'group-{i:04d}.json',cs,f.meta['data_hash']):done+=len(cs);continue
        if time.monotonic()-start>seconds:complete=False;continue
        run_group(f,i,s,cs,out);done+=len(cs)
        atomic_json(out/'status.json',{**identity,'complete':False,'completed':done,'elapsed':time.monotonic()-start})
        print(f'shard {index}: group {i}, {s["family"]}, completed {done}',flush=True)
    atomic_json(out/'status.json',{**identity,'complete':complete and done==expected,'completed':done,'expected':expected})
    if done!=expected:raise SystemExit(2)

def smoke(prepared,out):
    f=Features(prepared);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    seen=set();rows=[]
    for i,s,cs in groups():
        key=s['family']
        # Exercise the two-state implementation as well as each family baseline.
        if key=='M04' and s['states']==2:key='M04_TWO_STATE'
        if s['control'] or key in seen:continue
        sig=build(f,s);c=next(c for c in cs if c['risk']==200)
        r,b,status,fail=evaluate(f,c,sig,True);raw,*_=evaluate(f,c,sig)
        if not np.isfinite(r).all() or not np.isfinite(raw).all():raise AssertionError('Nonfinite execution')
        if (r[:,15]>389).any():raise AssertionError('Late liquidation')
        if (r[:,11]>40).any():raise AssertionError('Contract cap')
        if raw[:,2].sum()==0:raise AssertionError(f'No executable smoke trades: {key}')
        # Change prices strictly after a cutoff on the final day. Earlier signals,
        # and fixed forecasts formed before that cutoff, must remain unchanged.
        altered=copy.copy(f);altered.a=f.a.copy();altered.vwap=f.vwap.copy();altered.cache={}
        altered.a[-1,180:,:4]*=1.1;altered.vwap[-1,180:]*=1.1
        other=build(altered,s)
        for field in range(4):
            np.testing.assert_allclose(sig[field][-1,:180],other[field][-1,:180],equal_nan=True)
        if s['family'] in ['M02','M03','M04','M10']:
            np.testing.assert_allclose(sig[0][-1],other[0][-1],equal_nan=True)
        rows.append({'family':key,'config':c,**describe(f,raw),'account_status':int(status),**sig[-1]})
        seen.add(key);print('smoke '+key,flush=True)
        if len(seen)==11:break
    if len(seen)!=11:raise AssertionError('Missing model smoke')
    atomic_json(out/'smoke.json',{'status':'PASS','rows':rows,'study_hash':study_hash()})
    (out/'summary.md').write_text('# Research #3 verification\n\nTen families and two-state forecast executed.\n\n'+
        '\n'.join(f'- {r["family"]}: {r["trades"]} trades, {r["missing_path_days"]} unresolved dates' for r in rows),encoding='utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['download','prepare','manifest','smoke','shard','aggregate'])
    p.add_argument('--out',type=Path,required=True);p.add_argument('--data',type=Path);p.add_argument('--prepared',type=Path)
    p.add_argument('--parts',type=Path);p.add_argument('--index',type=int,default=0);p.add_argument('--count',type=int,default=32)
    p.add_argument('--seconds',type=int,default=14400);p.add_argument('--limit',type=int,default=0)
    a=p.parse_args()
    if a.mode=='download':download(a.out)
    elif a.mode=='prepare':prepare(a.data,a.out)
    elif a.mode=='manifest':print(json.dumps(manifest(a.out)))
    elif a.mode=='smoke':smoke(a.prepared,a.out)
    elif a.mode=='shard':shard(a.prepared,a.out,a.index,a.count,a.seconds,a.limit)
    else:
        from analysis import aggregate
        aggregate(a.parts,a.prepared,a.out)

if __name__=='__main__':main()

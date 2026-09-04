"""Manual full R4 study, atomic resumable groups and exact completion checks."""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
from registry import grid,groups,manifest,study_hash,atomic_json,require_execution_ready
from features import Features
from evaluate import context,evaluate,describe,row


def save(path,obj):
    path=Path(path);temp=path.with_suffix('.tmp')
    temp.write_bytes(gzip.compress(json.dumps(obj,allow_nan=False,separators=(',',':')).encode()))
    os.replace(temp,path)


def read(path,identity,configs):
    if not path.exists():return []
    obj=json.loads(gzip.decompress(path.read_bytes()))
    if obj['identity']!=identity:raise ValueError('Checkpoint code/data/assignment mismatch')
    rows=obj['rows']
    if len(rows)>len(configs) or any(r['config']!=c for r,c in zip(rows,configs)):
        raise ValueError('Checkpoint config mismatch')
    return rows


def shard(prepared,out,index,count,seconds):
    require_execution_ready()
    if not 0<=index<count:raise ValueError('Invalid shard')
    f=Features(prepared);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    identity={'study_hash':study_hash(),'data_hash':f.meta['data_hash'],'index':index,'count':count}
    start=time.monotonic();completed=0;expected=0;cached=None;ctx=None;timed=False
    for i,s,cs in groups():
        if i%count!=index:continue
        expected+=len(cs);path=out/f'group-{i:06d}.json.gz'
        group_identity={**identity,'group':i}
        rows=read(path,group_identity,cs)
        if len(rows)==len(cs):completed+=len(rows);continue
        if timed or time.monotonic()-start>=seconds:timed=True;completed+=len(rows);continue
        if s!=cached:ctx=context(f,s);cached=s
        for c in cs[len(rows):]:
            if time.monotonic()-start>=seconds:timed=True;break
            stats=row(f,c,ctx)
            rows.append({'config':c,**stats})
            if len(rows)%16==0:save(path,{'identity':group_identity,'rows':rows})
        save(path,{'identity':group_identity,'rows':rows});completed+=len(rows)
        print(f'shard {index}, group {i}, completed {completed}',flush=True)
    status={**identity,'complete':completed==expected,'completed':completed,'expected':expected}
    atomic_json(out/'status.json',status)
    if completed!=expected:raise SystemExit(2)


def smoke(prepared,out):
    f=Features(prepared);rows=[]
    for model in grid()['models']:
        blocks=model['blocks'] if model['id']=='R4-31' else model['blocks'][:1]
        for block in blocks:
            c={k:v[0] for k,v in block.items()};c.update(model=model['id'],risk=200,cutoff=780)
            if 'flat' in c:c['flat']=959
            ctx=context(f,c);raw,*_=evaluate(f,c,ctx);account,*_=evaluate(f,c,ctx,True)
            if not np.isfinite(raw).all() or not np.isfinite(account).all():raise AssertionError('Nonfinite execution')
            if raw[:,13].max()>389:raise AssertionError('Late exit')
            if raw[:,11].max()>c['risk']+1e-6:raise AssertionError('Episode risk exceeded')
            altered=copy.copy(f);altered.a=f.a.copy();altered.ret=f.ret.copy();altered.vwap=f.vwap.copy();altered.cache={}
            altered.a[-1,180:,:4]*=1.1;altered.ret[-1,180:]*=-2;altered.vwap[-1,180:]*=1.1
            other=context(altered,c)[0]
            before=ctx[0][(ctx[0][:,0]==len(f.a)-1)&(ctx[0][:,1]<180)]
            after=other[(other[:,0]==len(f.a)-1)&(other[:,1]<180)]
            np.testing.assert_allclose(before,after,equal_nan=True)
            rows.append({'model':model['id'],'family':c.get('family'),'events':len(ctx[0]),**describe(f,raw)})
            print('smoke',model['id'],c.get('family',''),flush=True)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    atomic_json(out/'smoke.json',{'status':'PASS','study_hash':study_hash(),'rows':rows})
    (out/'summary.md').write_text('# R4 verification\n\nAll 31 families and ten model31 entry families executed; future-perturbation and execution checks passed. Zero-event settings remain zero-event findings. This is verification, not the full search.\n',encoding='utf-8')


def aggregate(prepared,parts,out,count):
    f=Features(prepared);parts=Path(parts);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    h=study_hash();total=0;expected=0;best={};prop={};by_model={};missing=[]
    identity={'study_hash':h,'data_hash':f.meta['data_hash'],'count':count}
    files={}
    for path in parts.rglob('group-*.json.gz'):files.setdefault(path.name,[]).append(path)
    with gzip.open(out/'all-results.jsonl.gz','wt',encoding='utf-8',compresslevel=3) as stream:
        for i,s,cs in groups():
            expected+=len(cs);paths=files.get(f'group-{i:06d}.json.gz',[])
            if len(paths)!=1:missing.append(i);continue
            rows=read(paths[0],{**identity,'index':i%count,'group':i},cs)
            if len(rows)!=len(cs):missing.append(i)
            for r in rows:
                total+=1;m=s['model'];by_model[m]=by_model.get(m,0)+1
                stream.write(json.dumps(r,allow_nan=False,separators=(',',':'))+'\n')
                if r['unknown_days']==0 and r['trades']>0 and (m not in best or r['net_profit']>best[m]['net_profit']):best[m]=r
                if r['prop_screen_pass'] and (m not in prop or r['account_net_profit']>prop[m]['account_net_profit']):prop[m]=r
    complete=total==expected and not missing
    report={'complete':complete,'completed':total,'expected':expected,'missing_groups':missing,'models':by_model,'best_profit':best,'best_prop':prop}
    if complete:
        finalists={r['config']['id']:r for r in [*best.values(),*prop.values()]}
        diagnostics={}
        for cid,r in finalists.items():
            c=r['config'];ctx=context(f,c)
            raw,*_=evaluate(f,c,ctx);acc,b,status,fail=evaluate(f,c,ctx,True)
            np.savez_compressed(out/(cid+'.npz'),dates=f.dates,raw=raw,account=acc)
            stressed=[]
            for slip in [.5,1.]:
                rr,*_=evaluate(f,c,ctx,False,slip);aa,bb,ss,ff=evaluate(f,c,ctx,True,slip)
                stressed.append({'slippage_per_side_points':slip,**describe(f,rr),'account_balance':float(bb),'account_status':int(ss)})
            diagnostics[cid]={'config':c,'cost_stresses':stressed}
        atomic_json(out/'finalist-diagnostics.json',diagnostics)
    atomic_json(out/'report.json',report)
    lines=['# Research 4 — all 31 models',f'\nCompleted **{total:,} / {expected:,}** unique configurations.',
           '\n'+('COMPLETE finite development search.' if complete else 'INCOMPLETE — do not rank as a completed study; resume the saved run.'),
           '\nHistorical winners are selected on reused development data. Prop screen means modeled trading-risk survival, not evaluation pass or payout qualification. Higher-cost stress is finalist-only.',
           '\n| Model | Best historical profit | Net | Best prop variant | Account net |',
           '|---|---|---:|---|---:|']
    for m in grid()['models']:
        k=m['id'];a=best.get(k);b=prop.get(k)
        lines.append(f"| {k} | {a['config']['id'] if a else 'NONE'} | {a['net_profit'] if a else 0:,.2f} | {b['config']['id'] if b else 'NONE'} | {b['account_net_profit'] if b else 0:,.2f} |")
    lines.append('\nMissing paths are not zero-profit trades. Timestamp labeling is empirically inferred. Minute OHLCV cannot establish intrabar ordering; ambiguous resting-limit results do not qualify for the prop shortlist. Annual metrics, full settings and all trial rows are in the artifact. No independent unseen-period edge claim is made.')
    (out/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    if not complete:raise SystemExit(2)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['manifest','smoke','shard','aggregate'])
    p.add_argument('--prepared',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--parts',type=Path)
    p.add_argument('--index',type=int,default=0);p.add_argument('--count',type=int,default=64);p.add_argument('--seconds',type=int,default=2400)
    a=p.parse_args()
    if a.mode=='manifest':print(json.dumps(manifest(a.out)))
    elif a.mode=='smoke':smoke(a.prepared,a.out)
    elif a.mode=='shard':shard(a.prepared,a.out,a.index,a.count,a.seconds)
    else:aggregate(a.prepared,a.parts,a.out,a.count)

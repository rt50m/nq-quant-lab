"""R6 manifest, smoke, deterministic resumable shards, and exact aggregation."""
from __future__ import annotations
import argparse,gzip,json,os,time
from pathlib import Path
import numpy as np
from registry import config,signal_groups,execution_configs,manifest,atomic_json,digest
from features import Features
from signals import build
from execution import outcomes,select
from sizing import evaluate

def save_gz(path,obj):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_bytes(gzip.compress(json.dumps(obj,allow_nan=False,separators=(',',':')).encode(),compresslevel=3));os.replace(tmp,path)
def load_gz(path):return json.loads(gzip.decompress(Path(path).read_bytes()))

def identity(f,index,count):
    return {'grid_hash':digest(config()),'data_hash':f.meta['data_hash'],'index':index,'count':count}

def evaluate_group(f,gi,s):
    events=build(f,s); ex=list(execution_configs());rows=[];cache={}
    slip=config()['costs']['slippage_per_side_points'];maxtr=config()['objective']['max_trades_per_day']
    for ei,e in enumerate(ex):
        key=(e['stop_atr'],e['target_r'],e['hold'])
        if key not in cache:
            cache[key]=outcomes(f.a,f.atr,events,*key,slip,config()['objective']['hard_flat_rth_index'])
        trades=select(cache[key],e['window_start'],e['window_end'],e['direction'],maxtr)
        stats=evaluate(trades,f.dates)
        row={'id':f'R6-{gi:04d}-{ei:03d}','group':gi,'signal':s,'execution':e,
             'signal_events':int(len(events)),'selected_trades':int(len(trades))}
        if stats is None:row.update(status='NO_TRADES',pass_scale=False,net_profit=0.0,max_drawdown=0.0,profit_factor=0.0,profit_to_dd=0.0)
        else:row.update(status='OK',**stats)
        rows.append(row)
    return rows

def smoke(prepared,out):
    f=Features(prepared);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    reps={}
    for i,s in enumerate(signal_groups()):reps.setdefault(s['family'],(i,s))
    report=[]
    for fam,(i,s) in reps.items():
        ev=build(f,s)
        # one moderate execution setting for engine verification
        o=outcomes(f.a,f.atr,ev,0.35,1.5,30,config()['costs']['slippage_per_side_points'],389)
        tr=select(o,5,360,0,12);st=evaluate(tr,f.dates)
        if len(tr) and (np.any(tr[:,2]<=tr[:,1]) or np.any(tr[:,3]<tr[:,2])):raise AssertionError('Noncausal entry/exit ordering')
        report.append({'family':fam,'events':len(ev),'trades':len(tr),'best_sizing':st})
        print('smoke',fam,'events',len(ev),'trades',len(tr),flush=True)
    atomic_json(out/'smoke.json',{'status':'PASS','families':report})
    (out/'summary.md').write_text('# R6 smoke PASS\n\nAll eight high-density families generated/evaluated on the audited real-data preparation. This is engine verification, not research performance.\n',encoding='utf-8')

def shard(prepared,out,index,count,seconds):
    f=Features(prepared);out=Path(out);out.mkdir(parents=True,exist_ok=True);ident=identity(f,index,count)
    start=time.monotonic();expected=completed=0;timed=False
    for gi,s in enumerate(signal_groups()):
        if gi%count!=index:continue
        expected+=1;path=out/f'group-{gi:04d}.json.gz';gid={**ident,'group':gi,'signal':s}
        if path.exists():
            obj=load_gz(path)
            if obj.get('identity')!=gid:raise ValueError('Checkpoint identity mismatch')
            if obj.get('complete') and len(obj.get('rows',[]))==sum(1 for _ in execution_configs()):completed+=1;continue
        if timed or time.monotonic()-start>=seconds:timed=True;continue
        rows=evaluate_group(f,gi,s)
        save_gz(path,{'identity':gid,'complete':True,'rows':rows});completed+=1
        print(f'shard {index}: group {gi} {s["family"]} done ({completed}/{expected})',flush=True)
    status={**ident,'complete':completed==expected,'completed_groups':completed,'expected_groups':expected}
    atomic_json(out/'status.json',status)
    if completed!=expected:raise SystemExit(2)

def aggregate(prepared,parts,out,count):
    f=Features(prepared);parts=Path(parts);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    groups=list(signal_groups());nex=sum(1 for _ in execution_configs());ident_base={'grid_hash':digest(config()),'data_hash':f.meta['data_hash'],'count':count}
    files={}
    for p in parts.rglob('group-*.json.gz'):files.setdefault(p.name,[]).append(p)
    missing=[];total=0;passes=[];best_family={};global_best=None
    with gzip.open(out/'all-results.jsonl.gz','wt',encoding='utf-8',compresslevel=3) as stream:
        for gi,s in enumerate(groups):
            ps=files.get(f'group-{gi:04d}.json.gz',[])
            if len(ps)!=1:missing.append(gi);continue
            obj=load_gz(ps[0]);want={**ident_base,'index':gi%count,'group':gi,'signal':s}
            if obj.get('identity')!=want or not obj.get('complete') or len(obj.get('rows',[]))!=nex:
                missing.append(gi);continue
            for r in obj['rows']:
                total+=1;stream.write(json.dumps(r,allow_nan=False,separators=(',',':'))+'\n')
                if r.get('status')!='OK':continue
                fam=s['family']
                if fam not in best_family or r['net_profit']>best_family[fam]['net_profit']:best_family[fam]=r
                if global_best is None or r['net_profit']>global_best['net_profit']:global_best=r
                if r.get('pass_scale'):passes.append(r)
    expected=len(groups)*nex;complete=total==expected and not missing
    passes.sort(key=lambda r:(r['net_profit'],r['profit_to_dd']),reverse=True)
    top=sorted(best_family.values(),key=lambda r:r['net_profit'],reverse=True)
    atomic_json(out/'scale-passes.json',{'count':len(passes),'passes':passes[:200]})
    atomic_json(out/'best-by-family.json',{'families':top,'global_best':global_best})
    report={'complete':complete,'completed':total,'expected':expected,'missing_groups':missing,'scale_passes':len(passes),
            'global_best':global_best}
    atomic_json(out/'report.json',report)
    lines=['# Research 6 — High-Density Scale Search',f'\nCompleted **{total:,} / {expected:,}** execution configurations.',
           '\n'+('COMPLETE.' if complete else 'INCOMPLETE — do not interpret rankings; resume checkpoints.'),
           f"\nHard objective: **net ≥ ${config()['objective']['min_net_profit']:,.0f} with conservative intratrade MDD strictly under ${config()['objective']['max_drawdown']:,.0f}**.",
           '\nSizing is NOT fixed at $300. Every execution path is evaluated with fixed NQ/MNQ quantity scaling and a frozen fixed-dollar-risk budget grid; the most profitable sizing that remains inside the drawdown cap is retained.',
           f'\n**PASS_SCALE configurations: {len(passes):,}.**',
           '\n## Best achievable under $2k MDD by family','\n| Family | Config | Net | MDD | P/DD | PF | Trades | Sizing | 2023 | 2024 | 2025 |',
           '|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|']
    for r in top:
        sizing=(f"{r['quantity']} {r['symbol']}" if r['mode']=='FIXED_QTY' else f"risk ${r['risk_budget']:.0f} best NQ/MNQ")
        lines.append(f"| {r['signal']['family']} | {r['id']} | {r['net_profit']:,.0f} | {r['max_drawdown']:,.0f} | {r['profit_to_dd']:.1f} | {r['profit_factor']:.2f} | {r['trades']} | {sizing} | {r.get('net_2023',0):,.0f} | {r.get('net_2024',0):,.0f} | {r.get('net_2025',0):,.0f} |")
    if passes:
        lines += ['\n## Hard scale passes','\n| Config | Family | Net | MDD | P/DD | PF | Trades | Sizing |','|---|---|---:|---:|---:|---:|---:|---|']
        for r in passes[:25]:
            sizing=(f"{r['quantity']} {r['symbol']}" if r['mode']=='FIXED_QTY' else f"risk ${r['risk_budget']:.0f}")
            lines.append(f"| {r['id']} | {r['signal']['family']} | {r['net_profit']:,.0f} | {r['max_drawdown']:,.0f} | {r['profit_to_dd']:.1f} | {r['profit_factor']:.2f} | {r['trades']} | {sizing} |")
    lines.append('\nPASS_SCALE is only the requested development hurdle, not untouched OOS validation. One-minute OHLCV cannot resolve all intrabar ordering; stop-first handling and adverse open gaps are conservative. NQ data is also used as the MNQ price proxy.')
    (out/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    if not complete:raise SystemExit(2)

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['manifest','smoke','shard','aggregate']);p.add_argument('--prepared',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--parts',type=Path);p.add_argument('--index',type=int,default=0);p.add_argument('--count',type=int,default=16);p.add_argument('--seconds',type=int,default=4800)
    a=p.parse_args()
    if a.mode=='manifest':print(json.dumps(manifest(a.out),indent=2))
    elif a.mode=='smoke':smoke(a.prepared,a.out)
    elif a.mode=='shard':shard(a.prepared,a.out,a.index,a.count,a.seconds)
    else:aggregate(a.prepared,a.parts,a.out,a.count)
if __name__=='__main__':main()

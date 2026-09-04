"""Research #2: reproducible finite grids, causal signals, resumable shards.

All price research is a transfer/reconstruction, NOT a claimed paper replication.
Only the frozen development interval is loaded. Future data requires a new study.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from engine import simulate

ROOT=Path(__file__).resolve().parent
ET='America/New_York'
FAMILIES=['ORB_BASE','ORB_VWAP','ORB_RVOL','ORB_VOL','ORB_GAP','ORB_OPEN_TREND',
          'CLOSE_MOMENTUM','NOISE_MOMENTUM','GAP_REVERSAL','OPEN_SHOCK_REVERSAL','OVERNIGHT_DRIFT']


@lru_cache(maxsize=1)
def read_grid():
    return json.loads((ROOT/'grid.json').read_text())


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def atomic_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')
    os.replace(tmp,path)


def study_hash():
    return digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in [ROOT/'grid.json',ROOT/'run.py',ROOT/'engine.py',ROOT/'requirements.txt']})


def fetch(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url,timeout=40) as r:
                return r.read()
        except Exception:
            if attempt==3: raise
            time.sleep(2**attempt)


def download(out):
    """Anonymous public data only: no local Git, credentials, tokens or auth helpers."""
    grid=read_grid();out.mkdir(parents=True,exist_ok=True)
    base=f"https://raw.githubusercontent.com/MeNameek/AnooReplay/{grid['source_commit']}/public/data/NQ"
    dates=json.loads(fetch(base+'/dates.json'))
    dates=[d for d in dates if '2022-12-26'<=d<=grid['development_end']]
    atomic_json(out/'dates.json',dates)
    def one(d):
        p=out/f'{d}.json'
        if not p.exists():
            payload=fetch(base+f'/{d}.json')
            json.loads(payload)
            p.write_bytes(payload)
        return d,hashlib.sha256(p.read_bytes()).hexdigest()
    hashes={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i,(d,h) in enumerate(pool.map(one,dates),1):
            hashes[d]=h
            if i%100==0: print(f'download {i}/{len(dates)}',flush=True)
    atomic_json(out/'provenance.json',{'source_commit':grid['source_commit'],
        'files':hashes,'data_hash':digest(hashes),'source':'Public research mirror; exchange provenance/roll treatment unverified'})


def signal_specs(grid):
    for family in FAMILIES:
        gates=grid['gates'].get(family,{})
        for values in itertools.product(*gates.values()):
            gate=dict(zip(gates,values))
            lengths=grid['opening_minutes'] if family.startswith('ORB_') else [0]
            confirms=grid['confirmation_bars'] if family.startswith('ORB_') or family=='NOISE_MOMENTUM' else [1]
            dirs=[1] if family=='OVERNIGHT_DRIFT' else grid['directions']
            for length,confirmation,direction in itertools.product(lengths,confirms,dirs):
                yield dict(family=family,length=length,confirmation=confirmation,direction=direction,**gate)


def all_configs(grid):
    i=0
    for signal in signal_specs(grid):
        family=signal['family']
        exits=([959] if family=='CLOSE_MOMENTUM' else
               [signal['exit_minute']] if family=='OVERNIGHT_DRIFT' else grid['rth_exit_minutes'])
        for risk,stop,target,trail,exit_minute in itertools.product(
                grid['risk_budgets'],grid['stop_atr_fractions'],grid['target_R'],grid['trailing'],exits):
            yield {'id':f'R2-{i:07d}','signal':signal,'risk':risk,'stop':stop,'target':target,
                   'trail':trail,'exit':exit_minute}
            i+=1


def manifest(out):
    out.mkdir(parents=True,exist_ok=True)
    counts={f:0 for f in FAMILIES};grid=read_grid()
    with (out/'manifest.jsonl').open('w',encoding='utf-8') as f:
        for cfg in all_configs(grid):
            f.write(json.dumps(cfg,separators=(',',':'))+'\n')
            counts[cfg['signal']['family']]+=1
    info={'study_hash':study_hash(),'grid_hash':digest(grid),'counts':counts,'total':sum(counts.values()),
          'exclusions':['TOUCH entries require event-order data and are outside v1',
                        'One position/trade per session, no pyramiding/re-entry in v1',
                        'Holiday and shortened US cash sessions excluded by calendar',
                        'No cross-products of distinct model-family filters',
                        'No post-2025 data is searched or presented as holdout',
                        'No payout, funded LucidScale, evaluation pass or live-order model'],
          'interpretation':'Exhaustive only within the declared grid; development screen, not deployable validation'}
    atomic_json(out/'manifest_summary.json',info)
    print(json.dumps(info),flush=True)
    return info


def prepare(data_dir,out):
    grid=read_grid();out.mkdir(parents=True,exist_ok=True)
    provenance=json.loads((data_dir/'provenance.json').read_text())
    if provenance['source_commit']!=grid['source_commit']:
        raise ValueError('Data commit differs from frozen grid')
    chunks=[]
    for d in json.loads((data_dir/'dates.json').read_text()):
        p=data_dir/f'{d}.json'
        if hashlib.sha256(p.read_bytes()).hexdigest()!=provenance['files'][d]:
            raise ValueError(f'Changed cached data: {d}')
        x=np.asarray(json.loads(p.read_text()),dtype=float)
        if len(x): chunks.append(x)
    raw=pd.DataFrame(np.concatenate(chunks),columns=['time','open','high','low','close','volume'])
    if raw.isna().any().any(): raise ValueError('Nonfinite raw values')
    if not np.isfinite(raw.to_numpy()).all(): raise ValueError('Infinite data')
    raw=raw.drop_duplicates()
    if raw.time.duplicated().any(): raise ValueError('Conflicting timestamp duplicates')
    if ((raw.time%60)!=0).any(): raise ValueError('Not minute-open timestamps')
    if ((raw.high<raw[['open','close','low']].max(axis=1)) | (raw.low>raw[['open','close','high']].min(axis=1)) | (raw.volume<0)).any():
        raise ValueError('Invalid OHLCV')
    raw=raw.sort_values('time')
    ts=pd.to_datetime(raw.time,unit='s',utc=True).dt.tz_convert(ET)
    raw['date']=ts.dt.strftime('%Y-%m-%d');raw['minute']=ts.dt.hour*60+ts.dt.minute
    # This is an intentional cash-session trading restriction, not a CME calendar claim.
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2022-12-26',end_date=grid['development_end'])
    opens=schedule.market_open.dt.tz_convert(ET);closes=schedule.market_close.dt.tz_convert(ET)
    normal=(opens.dt.hour==9)&(opens.dt.minute==30)&(closes.dt.hour==16)&(closes.dt.minute==0)
    dates=schedule.index.strftime('%Y-%m-%d').tolist()
    a=np.full((len(dates),960,5),np.nan)
    for i,d in enumerate(dates):
        rows=raw[(raw.date==d)&(raw.minute<960)]
        a[i,rows.minute.to_numpy(int)]=rows[['open','high','low','close','volume']].to_numpy()
    np.save(out/'bars.npy',a)
    rth_missing=np.isnan(a[:,570:960,0]).sum(axis=1)
    overnight_missing=np.isnan(a[:,120:241,0]).sum(axis=1)
    quality={'source_commit':grid['source_commit'],'data_hash':provenance['data_hash'],
        'dates':dates,'normal_session_mask':normal.tolist(),
        'cash_close_minutes':(closes.dt.hour*60+closes.dt.minute).tolist(),
        'first':dates[0],'last':dates[-1],'normal_cash_sessions':int(normal.sum()),
        'omitted_short_sessions':schedule.index[~normal].strftime('%Y-%m-%d').tolist(),
        'rth_incomplete':{d:int(v) for d,v in zip(dates,rth_missing) if v},
        'overnight_incomplete':{d:int(v) for d,v in zip(dates,overnight_missing) if v},
        'raw_rows':len(raw),'study_hash':study_hash(),
        'status':'PROVISIONAL_MIRROR_DATA',
        'limitations':['Timestamp convention inferred from mirror, not exchange certified',
                      'NQ roll/adjustment and MNQ fill equivalence require independent validation',
                      'Missing active-trade bars flag NEEDS_DATA and stop account replay']}
    atomic_json(out/'prepared.json',quality)
    manifest(out)
    print(f"prepared {len(dates)} dates; {int((rth_missing>0).sum())} incomplete RTH sessions",flush=True)


class Features:
    def __init__(self,prepared):
        self.meta=json.loads((prepared/'prepared.json').read_text())
        if self.meta['study_hash']!=study_hash(): raise ValueError('Prepared state belongs to another code/grid version')
        self.a=np.load(prepared/'bars.npy')
        self.dates=np.array(self.meta['dates'])
        self.keep=(self.dates>=read_grid()['development_start'])&np.array(self.meta['normal_session_mask'])
        a=self.a;n=len(a)
        self.op=a[:,570,0]
        closes=np.array(self.meta['cash_close_minutes'])
        self.cl=a[np.arange(n),closes-1,3]
        self.prev=pd.Series(self.cl).shift().to_numpy()
        self.prevret=pd.Series(self.cl/self.op-1).shift().to_numpy()
        self.gap=self.op/self.prev-1
        # Entire RTH summaries are only used after a one-session shift.
        full=np.array([np.isfinite(a[i,570:closes[i],:4]).all() for i in range(n)])
        hi=np.array([np.max(a[i,570:closes[i],1]) for i in range(n)])
        lo=np.array([np.min(a[i,570:closes[i],2]) for i in range(n)])
        tr=np.maximum(hi-lo,np.maximum(abs(hi-self.prev),abs(lo-self.prev)))
        tr[~full]=np.nan
        self.atr=pd.Series(tr).shift().rolling(14,min_periods=14).mean().to_numpy()
        typical=(a[:,:,1]+a[:,:,2]+a[:,:,3])/3
        volume=a[:,:,4].copy();volume[:,:570]=0
        money=typical*volume;money[:,:570]=0
        sums=np.cumsum(volume,axis=1)
        self.vwap=np.divide(np.cumsum(money,axis=1),sums,out=np.full_like(sums,np.nan),where=sums>0)
        self.ret=pd.Series(self.cl).pct_change(fill_method=None)
        self.cache={}

    def rolling(self,kind,length,lookback):
        key=(kind,length,lookback)
        if key not in self.cache:
            if kind=='volume':
                values=np.sum(self.a[:,570:570+length,4],axis=1)
                self.cache[key]=pd.Series(values).shift().rolling(lookback,min_periods=lookback).mean().to_numpy()
            elif kind=='noise':
                moves=abs(self.a[:,:,3]/self.op[:,None]-1)
                self.cache[key]=pd.DataFrame(moves).shift().rolling(lookback,min_periods=lookback).mean().to_numpy()
            elif kind=='vol':
                self.cache[key]=self.ret.shift().rolling(lookback,min_periods=lookback).std(ddof=0)
        return self.cache[key]


def signals(f,s):
    a=f.a;n=len(a);family=s['family'];direction=s['direction']
    side=np.zeros((n,960),dtype=np.int8)
    valid=np.isfinite(f.atr)&(f.atr>0)
    if family.startswith('ORB_'):
        L=s['length'];end=570+L
        hi=np.max(a[:,570:end,1],axis=1);lo=np.min(a[:,570:end,2],axis=1)
        side=np.where(a[:,:,3]>hi[:,None],1,np.where(a[:,:,3]<lo[:,None],-1,0)).astype(np.int8)
        side[:,:end]=0
        if family=='ORB_VWAP':
            good=(a[:,:,3]-f.vwap)*side>=s['buffer_atr']*f.atr[:,None]
            side=np.where(good,side,0)
        elif family=='ORB_RVOL':
            rv=np.sum(a[:,570:end,4],axis=1)/f.rolling('volume',L,s['lookback'])
            valid &= rv>=s['minimum']
        elif family=='ORB_VOL':
            v=f.rolling('vol',0,s['lookback'])
            q=float(s['state'][-2:])/100
            threshold=v.shift().rolling(126,min_periods=40).quantile(q)
            valid &= (v<=threshold if s['state'].startswith('LOW') else v>=threshold).to_numpy()
        elif family=='ORB_GAP':
            valid &= abs(f.gap)>=s['minimum']
            if s['prior_relation']!='ANY':
                same=f.gap*f.prevret>0
                valid &= same if s['prior_relation']=='SAME' else f.gap*f.prevret<0
            wanted=np.sign(f.gap)*(1 if s['mode']=='FOLLOW' else -1)
            side=np.where(side==wanted[:,None],side,0)
        elif family=='ORB_OPEN_TREND':
            body=a[:,end-1,3]-f.op
            strength=np.divide(abs(body),hi-lo,out=np.zeros(n),where=hi>lo)
            valid &= strength>=s['minimum_body_fraction']
            side=np.where(side==np.sign(body)[:,None],side,0)
    elif family=='NOISE_MOMENTUM':
        noise=f.rolling('noise',0,s['lookback'])*s['multiplier']
        upper=np.maximum(f.op,f.prev)[:,None]*(1+noise)
        lower=np.minimum(f.op,f.prev)[:,None]*(1-noise)
        side=np.where((a[:,:,3]>upper)&(a[:,:,3]>f.vwap),1,
             np.where((a[:,:,3]<lower)&(a[:,:,3]<f.vwap),-1,0)).astype(np.int8)
        side[:,:600]=0
    elif family in ('GAP_REVERSAL','CLOSE_MOMENTUM'):
        t=s['entry_minute']-1
        move=f.gap if family=='GAP_REVERSAL' else a[:,t,3]/f.prev-1
        valid &= abs(move)>=s['minimum']
        if family=='GAP_REVERSAL' and s['prior_relation']!='ANY':
            rel=f.gap*f.prevret
            valid &= rel>0 if s['prior_relation']=='SAME' else rel<0
        side[:,t]=np.nan_to_num(np.sign(move)*( -1 if family=='GAP_REVERSAL' else 1)).astype(np.int8)
    elif family=='OPEN_SHOCK_REVERSAL':
        t=570+s['observation_minutes']-1
        move=a[:,t,3]-f.op
        valid &= abs(move)>=s['minimum_atr']*f.atr
        side[:,t]=np.nan_to_num(-np.sign(move)).astype(np.int8)
    elif family=='OVERNIGHT_DRIFT':
        valid &= f.prevret<=s['previous_return_max']
        side[:,s['entry_minute']-1]=1
    else: raise ValueError(family)
    side[~valid]=0
    if direction: side=np.where(side==direction,side,0)
    if s['confirmation']==2:
        previous=np.roll(side,1,axis=1);previous[:,0]=0
        side=np.where(side==previous,side,0)
    if family.startswith('ORB_') or family=='NOISE_MOMENTUM':
        side[:,read_grid()['entry_cutoff_minute']:]=0
    # A signal exists only after that minute's close; enter next minute's OPEN.
    side[:,-1]=0
    exists=(side!=0).any(axis=1)
    idx=np.argmax(side!=0,axis=1)
    wanted=side[np.arange(n),idx].astype(np.int64)
    entries=np.where(exists,idx+1,-1).astype(np.int64)
    # Do not replace an unobservable earlier entry opportunity with a later clean one.
    # A missing signal/formation bar makes that date unresolved, not a no-trade day.
    if family.startswith('ORB_') or family=='NOISE_MOMENTUM':
        start=570
        end=read_grid()['entry_cutoff_minute']
    elif family=='OPEN_SHOCK_REVERSAL':
        start=570;end=570+s['observation_minutes']
    else:
        start=s['entry_minute']-1;end=s['entry_minute']
    missing=~np.isfinite(a[:,start:end,:]).all(axis=2)
    for d in range(n):
        # Scan only up to the chosen signal; later bars cannot contaminate that signal.
        stop=min(end,int(entries[d])) if entries[d]>=0 else end
        if valid[d] and missing[d,:max(0,stop-start)].any():
            entries[d]=-2-start-int(np.argmax(missing[d,:max(0,stop-start)]))
    entries[~f.keep]=-1
    return entries,wanted


def evaluate(f,cfg,entry,sides,enforce=False,slip_override=None):
    g=read_grid();acc=g['account'];cost=g['costs']
    exits=np.full(len(entry),min(cfg['exit'],acc['research_flat_minute']),dtype=np.int64)
    return simulate(f.a,entry,sides,f.atr,exits,cfg['risk'],cfg['stop'],cfg['target'],
        int(cfg['trail']!='NONE'),cost['slippage_per_side_points'] if slip_override is None else slip_override,
        cost['nq_commission_per_side'],cost['mnq_commission_per_side'],acc['start'],acc['max_loss'],
        acc['locked_floor'],min(acc['daily_loss'],acc['personal_daily_stop']),acc['account_buffer'],
        acc['max_nq'],acc['max_mnq'],enforce)


def describe(f,r):
    known=(r[:,4]>0)&(r[:,3]!=7)
    pnl=r[:,0];profit=float(pnl.sum());loss=-float(pnl[pnl<0].sum())
    eq=np.r_[0,np.cumsum(pnl)]
    dd=float(np.min(eq-np.maximum.accumulate(eq)))
    daily=pnl[f.keep];sd=float(np.std(daily,ddof=1)) if len(daily)>1 else 0
    out={'trades':int(known.sum()),'net_profit':round(profit,4),
         'profit_factor':round(float(pnl[pnl>0].sum()/loss),5) if loss>0 else None,
         'max_drawdown':round(dd,4),'daily_sharpe':round(float(np.mean(daily)/sd*np.sqrt(252)),5) if sd>0 else None,
         'ambiguous_exit_trades':int(r[:,6].sum()),'missing_path_trades':int(r[:,7].sum()),
         'size_skips':int((r[:,3]==6).sum()),'worst_trade':round(float(pnl.min()),4)}
    for y in ['2023','2024','2025']:
        m=np.char.startswith(f.dates,y)
        out['net_'+y]=round(float(pnl[m].sum()),4)
        out['trades_'+y]=int(known[m].sum())
    return out


def shard(prepared,out,index,count,limit=0,family=None,seconds=14400):
    g=read_grid();f=Features(prepared);out.mkdir(parents=True,exist_ok=True)
    name=f'shard-{index:03d}'
    identity={'study_hash':study_hash(),'data_hash':f.meta['data_hash'],'index':index,'count':count,
              'family':family,'limit':limit}
    ip=out/(name+'-identity.json')
    if ip.exists() and json.loads(ip.read_text())!=identity: raise ValueError('Checkpoint identity mismatch')
    atomic_json(ip,identity)
    path=out/(name+'.jsonl');done=set()
    if path.exists():
        # Accept only complete JSON lines; truncate a crash-interrupted final write.
        with path.open('rb+') as p:
            while True:
                pos=p.tell();line=p.readline()
                if not line: break
                try: row=json.loads(line)
                except json.JSONDecodeError:
                    p.truncate(pos);break
                if row['id'] in done: raise ValueError('Duplicate checkpoint ID')
                done.add(row['id'])
    total=0;selected=0;cached=None;entry=sides=None;started=time.monotonic();finished=True
    with path.open('a',encoding='utf-8') as p:
        for i,cfg in enumerate(all_configs(g)):
            if family and cfg['signal']['family']!=family: continue
            if i%count!=index: continue
            if limit and selected>=limit: break
            selected+=1
            if cfg['id'] in done: continue
            if time.monotonic()-started>seconds:
                finished=False;break
            sigkey=json.dumps(cfg['signal'],sort_keys=True)
            if sigkey!=cached:
                entry,sides=signals(f,cfg['signal']);cached=sigkey
            raw,_,_,_,_=evaluate(f,cfg,entry,sides)
            stat=describe(f,raw)
            # All configurations get an actual path replay, not clipped P&L.
            account,balance,failed,fail_day,protect=evaluate(f,cfg,entry,sides,enforce=True)
            row={'id':cfg['id'],'family':cfg['signal']['family'],'risk':cfg['risk'],**stat,
                 'account_balance':round(float(balance),4),'account_status':['SURVIVED','BREACHED','NEEDS_DATA'][failed],
                 'account_stop_date':str(f.dates[fail_day]) if fail_day>=0 else None,
                 'account_protection_exits':int(protect),
                 'screen_pass':bool(cfg['risk']==300 and stat['trades']>=80 and stat['trades_2024']>=20
                                    and stat['max_drawdown']>-2000 and stat['missing_path_trades']==0),
                 'config':cfg}
            p.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n')
            total+=1;done.add(cfg['id'])
            if total%100==0:
                p.flush();os.fsync(p.fileno())
                atomic_json(out/(name+'-status.json'),{**identity,'completed':len(done),'complete':False})
            if total%500==0: print(f'{name} completed {len(done)} ({time.monotonic()-started:.0f}s)',flush=True)
    status={**identity,'completed':len(done),'complete':finished,'elapsed_seconds':round(time.monotonic()-started,2)}
    atomic_json(out/(name+'-status.json'),status)
    print(json.dumps(status),flush=True)
    if not finished: raise SystemExit(2)


def aggregate(parts,prepared,out,smoke=False):
    out.mkdir(parents=True,exist_ok=True);f=Features(prepared)
    expected={c['id']:c for c in all_configs(read_grid())};seen={};identities=[]
    for p in parts.rglob('shard-*-identity.json'):
        identity=json.loads(p.read_text());identities.append(identity)
        if identity['study_hash']!=study_hash() or identity['data_hash']!=f.meta['data_hash']:
            raise ValueError('Mixed versions/data in aggregation')
        if not smoke and identity['limit']: raise ValueError('Smoke results cannot complete full study')
    if not identities: raise ValueError('No shard identities')
    for p in parts.rglob('shard-*.jsonl'):
        for line in p.open(encoding='utf-8'):
            row=json.loads(line);cid=row['id']
            if cid not in expected or row['config']!=expected[cid]: raise ValueError('Manifest mismatch')
            if cid in seen and row!=seen[cid]: raise ValueError('Conflicting duplicate results')
            seen[cid]=row
    complete=len(seen)==len(expected) and not smoke
    missing=[i for i in expected if i not in seen]
    atomic_json(out/'missing_ids.json',missing)
    flat=[{k:v for k,v in r.items() if k!='config'} for r in seen.values()]
    results=pd.DataFrame(flat)
    results.to_csv(out/'all_results.csv',index=False)
    ranked=results.sort_values('net_profit',ascending=False) if len(results) else results
    if len(ranked):
        ranked.groupby('family',sort=False).head(20).to_csv(out/'top20_development_per_family.csv',index=False)
        ranked[ranked.screen_pass].to_csv(out/'historical_screen_qualifiers.csv',index=False)
    summary={'status':'SMOKE_ONLY' if smoke else 'COMPLETE_DEVELOPMENT_GRID' if complete else 'INCOMPLETE',
        'expected':len(expected),'completed':len(seen),'missing':len(missing),'study_hash':study_hash(),
        'data_hash':f.meta['data_hash'],'holdout_status':'NOT_AVAILABLE; 2023-2025 previously examined',
        'live_ready':False}
    atomic_json(out/'completion.json',summary)
    lines=['# Research #2 run summary','',f"Status: **{summary['status']}**",
           f"Completed: {len(seen):,} / {len(expected):,}",'',
           'Development results only. No pristine holdout, live-readiness, pass-rate or payout claim.',
           'Prop outputs use an explicit LucidPro 50K evaluation reference and modeled fills.',
           'Full completion requires exact manifest coverage. Missing IDs are retained for recovery.','']
    if len(results):
        lines += ['| Family | Completed | Historical screen qualifiers |','|---|---:|---:|']
        for family,g in results.groupby('family'):
            lines.append(f'| {family} | {len(g):,} | {int(g.screen_pass.sum()):,} |')
    (out/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary),flush=True)
    if not complete and not smoke: raise SystemExit(2)


def smoke_check(prepared,out):
    out.mkdir(parents=True,exist_ok=True);f=Features(prepared)
    wanted=set(FAMILIES);rows=[]
    for cfg in all_configs(read_grid()):
        family=cfg['signal']['family']
        if family not in wanted or cfg['risk']!=300 or cfg['stop']!=0.1 or cfg['target']!=1.5 or cfg['trail']!='NONE':
            continue
        if family!='OVERNIGHT_DRIFT' and cfg['exit']!=959: continue
        entries,sides=signals(f,cfg['signal'])
        raw,_,_,_,_=evaluate(f,cfg,entries,sides)
        account,balance,status,_,_=evaluate(f,cfg,entries,sides,True)
        stat=describe(f,raw)
        if not np.isfinite(raw).all() or not np.isfinite(account).all():
            raise ValueError(f'Nonfinite execution: {family}')
        if ((raw[:,2]>=read_grid()['account']['firm_flat_minute'])&(raw[:,4]>0)).any():
            raise ValueError('Position held past firm cutoff')
        if (raw[:,4]>np.where(raw[:,5]==20,4,40)).any(): raise ValueError('Contract cap')
        rows.append({'family':family,'config':cfg,**stat,'account_status':int(status),'account_balance':float(balance)})
        wanted.remove(family)
        if not wanted: break
    if wanted: raise ValueError(f'Untested families: {wanted}')
    atomic_json(out/'smoke.json',{'status':'PASS','study_hash':study_hash(),'rows':rows,
        'interpretation':'Execution smoke, not profitability validation; data gaps remain explicit'})
    (out/'summary.md').write_text('# Research #2 verification\n\nAll 11 families executed; risk/time invariants passed.\n\n'+
        '\n'.join(f"- {r['family']}: {r['trades']} trades; {r['missing_path_trades']} missing paths" for r in rows),encoding='utf-8')
    print(json.dumps({'smoke':'PASS','families':len(rows)}),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['download','manifest','prepare','shard','aggregate','smoke'])
    p.add_argument('--out',type=Path,required=True);p.add_argument('--data',type=Path)
    p.add_argument('--prepared',type=Path);p.add_argument('--parts',type=Path)
    p.add_argument('--index',type=int,default=0);p.add_argument('--count',type=int,default=1)
    p.add_argument('--limit',type=int,default=0);p.add_argument('--family',choices=FAMILIES)
    p.add_argument('--seconds',type=int,default=14400);p.add_argument('--smoke',action='store_true')
    a=p.parse_args()
    if a.count<1 or not 0<=a.index<a.count: p.error('Invalid shard index/count')
    if a.mode=='download':download(a.out)
    elif a.mode=='manifest':manifest(a.out)
    elif a.mode=='prepare':prepare(a.data,a.out)
    elif a.mode=='shard':shard(a.prepared,a.out,a.index,a.count,a.limit,a.family,a.seconds)
    elif a.mode=='aggregate':aggregate(a.parts,a.prepared,a.out,a.smoke)
    elif a.mode=='smoke':smoke_check(a.prepared,a.out)


if __name__=='__main__': main()

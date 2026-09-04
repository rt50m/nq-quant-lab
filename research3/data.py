"""Shared R2 raw-data validation, frozen independently for R3. Anonymous downloads only."""
import json
import hashlib
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from registry import grid as read_grid, digest, atomic_json, study_hash, manifest
ET='America/New_York'
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
    quality['bars_sha256']=hashlib.sha256((out/'bars.npy').read_bytes()).hexdigest()
    atomic_json(out/'prepared.json',quality)
    manifest(out)
    print(f"prepared {len(dates)} dates; {int((rth_missing>0).sum())} incomplete RTH sessions",flush=True)

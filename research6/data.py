"""Self-contained anonymous NQ downloader plus causal previous-close VXN alignment."""
from __future__ import annotations
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,csv,hashlib,io,json,time,urllib.request
import numpy as np
from registry import config,digest,atomic_json

def fetch(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url,timeout=40) as r:return r.read()
        except Exception:
            if attempt==3: raise
            time.sleep(2**attempt)

def download(out:Path):
    g=config();out.mkdir(parents=True,exist_ok=True)
    base=f"https://raw.githubusercontent.com/MeNameek/AnooReplay/{g['source_commit']}/public/data/NQ"
    dates=json.loads(fetch(base+'/dates.json'));dates=[d for d in dates if '2022-12-26'<=d<=g['development_end']]
    atomic_json(out/'dates.json',dates)
    def one(d):
        p=out/f'{d}.json'
        if not p.exists():
            b=fetch(base+f'/{d}.json');json.loads(b);p.write_bytes(b)
        return d,hashlib.sha256(p.read_bytes()).hexdigest()
    hashes={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i,(d,h) in enumerate(pool.map(one,dates),1):
            hashes[d]=h
            if i%100==0:print(f'download {i}/{len(dates)}',flush=True)
    atomic_json(out/'provenance.json',{'source_commit':g['source_commit'],'files':hashes,
        'data_hash':digest(hashes),'source':'Public research mirror; exchange provenance/roll treatment unverified'})

def vxn(prepared:Path):
    """Download FRED VXNCLS and align strictly prior available close to each RTH date."""
    g=config();meta=json.loads((prepared/'prepared.json').read_text());raw=fetch(g['external_data']['vxn_fred_csv'])
    text=raw.decode('utf-8-sig');reader=csv.DictReader(io.StringIO(text));obs=[]
    for row in reader:
        d=row.get('observation_date') or row.get('DATE');v=row.get('VXNCLS') or row.get('VALUE')
        if not d or not v or v=='.':continue
        try:obs.append((d,float(v)))
        except ValueError:pass
    obs.sort();dates=[x[0] for x in obs];vals=[x[1] for x in obs]
    aligned=np.full(len(meta['dates']),np.nan);j=0;last=np.nan
    for i,d in enumerate(meta['dates']):
        while j<len(dates) and dates[j]<d:
            last=vals[j];j+=1
        aligned[i]=last
    if not np.isfinite(aligned[np.array(meta['normal_session_mask'],dtype=bool)&(np.array(meta['dates'])>='2023-01-01')]).all():
        raise ValueError('Missing prior VXN close inside R6 development sessions')
    np.save(prepared/'vxn_prev.npy',aligned)
    atomic_json(prepared/'r6_external.json',{'series':'VXNCLS','source':'FRED / CBOE','url':g['external_data']['vxn_fred_csv'],
        'causal_alignment':'strictly previous available daily close','raw_sha256':hashlib.sha256(raw).hexdigest(),
        'aligned_sha256':hashlib.sha256((prepared/'vxn_prev.npy').read_bytes()).hexdigest(),'observations':len(obs)})
    print(json.dumps({'vxn_observations':len(obs),'aligned_sessions':int(np.isfinite(aligned).sum()),'raw_sha256':hashlib.sha256(raw).hexdigest()},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['download','vxn']);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();download(a.out) if a.mode=='download' else vxn(a.out)

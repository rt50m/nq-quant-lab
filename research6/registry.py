"""Frozen R6 signal/execution grids and deterministic identities."""
from __future__ import annotations
from pathlib import Path
import hashlib, itertools, json, os

ROOT = Path(__file__).resolve().parent

def config():
    return json.loads((ROOT/'config.json').read_text(encoding='utf-8'))

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def atomic_json(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    os.replace(tmp,path)

def signal_groups():
    # High-density, trigger-based families only. Each event is causal at bar close and enters next bar open.
    for fast,slow,slope,vwap in itertools.product([5,10,20],[30,60],[0.0,0.03,0.06,0.10],[0,1]):
        yield {'family':'TREND_PULLBACK','fast':fast,'slow':slow,'slope_atr':slope,'vwap_filter':vwap}
    for look,buffer,vwap,volz in itertools.product([10,20,30,60],[0.0,0.03,0.06,0.10],[0,1],[-99.0,0.0,1.0]):
        yield {'family':'ROLLING_BREAKOUT','lookback':look,'buffer_atr':buffer,'vwap_filter':vwap,'volume_z':volz}
    for look,overshoot,reclaim,volz in itertools.product([10,20,30,60],[0.0,0.03,0.06],[0.0,0.03],[-99.0,0.0]):
        yield {'family':'FAILED_BREAKOUT','lookback':look,'overshoot_atr':overshoot,'reclaim_atr':reclaim,'volume_z':volz}
    for stretch,slope in itertools.product([0.20,0.30,0.40,0.55,0.70],[-1.0,0.02,0.05]):
        yield {'family':'VWAP_STRETCH_REVERSAL','stretch_atr':stretch,'max_abs_vwap_slope_atr':slope}
    for look,impulse,volz in itertools.product([3,5,10,15],[0.08,0.12,0.18,0.25],[-99.0,0.0,1.0]):
        yield {'family':'IMPULSE_CONTINUATION','lookback':look,'impulse_atr':impulse,'volume_z':volz}
        yield {'family':'IMPULSE_REVERSAL','lookback':look,'impulse_atr':impulse,'volume_z':volz}
    for look,maxrange,buffer in itertools.product([10,20,30],[0.15,0.25,0.35,0.50],[0.0,0.03,0.06]):
        yield {'family':'COMPRESSION_BREAKOUT','lookback':look,'max_range_atr':maxrange,'buffer_atr':buffer}
    for streak,tol,slope in itertools.product([5,10,20],[0.02,0.05,0.10],[0.0,0.02,0.05]):
        yield {'family':'VWAP_TREND_RECLAIM','streak':streak,'tolerance_atr':tol,'slope_atr':slope}
    for mult,regime,entry in itertools.product([0.75,1.0,1.25],['ALL','LOW20','HIGH30','EXTREMES'],['BREACH','RECLAIM']):
        yield {'family':'VXN_BAND_REVERSION','band_mult':mult,'regime':regime,'entry':entry}

def execution_configs():
    g=config()['execution']
    for stop,target,hold,(wname,window),direction in itertools.product(
        g['stop_atr'],g['target_r'],g['max_hold_minutes'],g['windows'].items(),g['directions']):
        yield {'stop_atr':stop,'target_r':target,'hold':hold,'window':wname,
               'window_start':window[0],'window_end':window[1],'direction':direction}

def group_count(): return sum(1 for _ in signal_groups())
def execution_count(): return sum(1 for _ in execution_configs())
def total_count(): return group_count()*execution_count()

def manifest(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    fam={}; groups=list(signal_groups()); ex=list(execution_configs())
    with (out/'manifest.jsonl').open('w',encoding='utf-8') as f:
        for gi,s in enumerate(groups):
            fam[s['family']]=fam.get(s['family'],0)+len(ex)
            for ei,e in enumerate(ex):
                row={'id':f'R6-{gi:04d}-{ei:03d}','group':gi,'signal':s,'execution':e}
                f.write(json.dumps(row,separators=(',',':'))+'\n')
    result={'version':config()['version'],'groups':len(groups),'execution_per_group':len(ex),
            'total':len(groups)*len(ex),'family_configs':fam,'grid_hash':digest(config()),
            'objective':'maximize net profit across sizing modes subject to conservative intratrade MDD < $2,000; PASS_SCALE requires net >= $50,000'}
    atomic_json(out/'manifest_summary.json',result);return result

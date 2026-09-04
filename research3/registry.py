"""Finite, versioned R3 search. Signal identities keep all risk variants together."""
from pathlib import Path
import hashlib
import itertools
import json
import os

ROOT = Path(__file__).resolve().parent

def grid():
    return json.loads((ROOT / 'grid.json').read_text(encoding='utf-8'))

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def atomic_json(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)

def study_hash():
    names = ['registry.py', 'data.py', 'signals.py', 'execution.py', 'run.py',
             'analysis.py', 'grid.json', 'requirements.txt']
    return digest({n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names})

def signals():
    for family, axes in grid()['models'].items():
        for values in itertools.product(*axes.values()):
            yield dict(family=family, control=False, **dict(zip(axes, values)))
    # Controls are explicitly separate from the ten hypotheses; no hidden eleventh model.
    for family, specs in grid()['controls'].items():
        for spec in specs:
            yield dict(family=family, control=True, **spec)

def groups():
    g=grid()
    for i, signal in enumerate(signals()):
        stops=[0] if signal['family']=='M08' else g['protective_stop_atr']
        configs=[]
        for j,(stop,risk) in enumerate(itertools.product(stops,g['risk_budgets'])):
            configs.append({'id':f'R3-{i:04d}-{j:02d}', 'group':i,
                            'signal':signal, 'stop_atr':stop, 'risk':risk})
        yield i,signal,configs

def manifest(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    counts={}; controls={}; ng=0
    with (out/'manifest.jsonl').open('w',encoding='utf-8') as f:
        for i,s,cs in groups():
            ng+=1
            target=controls if s['control'] else counts
            target[s['family']]=target.get(s['family'],0)+len(cs)
            for c in cs: f.write(json.dumps(c,separators=(',',':'))+'\n')
    result={'version':grid()['version'],'study_hash':study_hash(), 'grid_hash':digest(grid()),
            'groups':ng,'models':counts,'controls':controls,
            'total':sum(counts.values())+sum(controls.values()),
            'scope':'Finite development study; not all conceivable settings or pristine holdout'}
    atomic_json(out/'manifest_summary.json',result)
    return result

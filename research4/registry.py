"""Finite parameter registry. Preparation is not execution or validation."""
from pathlib import Path
from itertools import product
import hashlib
import json
import math
import os
from functools import lru_cache

ROOT = Path(__file__).resolve().parent


def grid():
    return json.loads((ROOT/'grid.json').read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    os.replace(temp, path)


def configs(model):
    """Streaming enumeration. Full policy canonicalization is a separate gate."""
    for block in model['blocks']:
        for values in product(*block.values()):
            params = dict(zip(block, values))
            yield {'model': model['id'], **params}


def preparation_manifest(out):
    g = grid()
    rows = []
    for model in g['models']:
        blocks = []
        for block in model['blocks']:
            n = math.prod(len(v) for v in block.values())
            blocks.append({'family': block.get('family', [None])[0], 'raw_combinations': n})
        rows.append({'id': model['id'], 'name': model['name'],
                     'raw_combinations': sum(v['raw_combinations'] for v in blocks),
                     'blocks': blocks, 'implementation': model['implementation'],
                     'requires_overnight': model['requires_overnight']})
    result = {'status': 'PREPARATION_ONLY', 'grid_hash': digest(g), 'models': rows,
              'model_count': len(rows), 'raw_combinations': sum(r['raw_combinations'] for r in rows),
              'unique_executable_combinations': None, 'completed_backtests': 0,
              'note': 'Raw Cartesian counts include possible semantic aliases and incompatible settings. Not an executable manifest or a completion claim.'}
    atomic_json(Path(out)/'preparation_manifest.json', result)
    return result


def require_execution_ready():
    pending = [m['id'] for m in grid()['models'] if m['implementation'] != 'IMPLEMENTED']
    if pending:
        raise RuntimeError('Full research disabled: missing validated implementations: '+', '.join(pending))


EXECUTION={'risk','stop_atr','target_r','flat','cutoff','direction','stop_buffer','location','min_rr','max_hold'}


def study_hash():
    names=['grid.json','registry.py','features.py','signals.py','model31.py','execution.py','evaluate.py','run.py','data.py','timestamps.py','DATA_PROVENANCE.json']
    return digest({n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names})


def groups():
    index=0
    for model in grid()['models']:
        for block in model['blocks']:
            keys=[k for k in block if k not in EXECUTION]
            ekeys=[k for k in block if k in EXECUTION]
            templates=[dict(zip(ekeys,v)) for v in product(*(block[k] for k in ekeys))]
            for values in product(*(block[k] for k in keys)):
                signal={'model':model['id'],**dict(zip(keys,values))}
                unique={}
                for template in templates:
                    c={**signal,**template}
                    if 'flat' in c:
                        if model['id']=='R4-23':c['flat']=min(c['flat'],570+c['opening']+c['horizon'])
                        c['cutoff']=min(c['cutoff'],c['flat']-1)
                    key=json.dumps(c,sort_keys=True,separators=(',',':'))
                    if key in unique:unique[key][1]+=1
                    else:unique[key]=[c,1]
                entries=list(unique.values())
                for left in range(0,len(entries),256):
                    cs=[]
                    for j,(c,aliases) in enumerate(entries[left:left+256]):
                        cs.append({**c,'id':f'R4-{index:06d}-{j:03d}','aliases':aliases})
                    yield index,signal,cs
                    index+=1


def manifest(out):
    counts={};raw={};ng=0
    for i,s,cs in groups():
        ng+=1;m=s['model'];counts[m]=counts.get(m,0)+len(cs)
        raw[m]=raw.get(m,0)+sum(c['aliases'] for c in cs)
    result={'study_hash':study_hash(),'groups':ng,'models':counts,'raw_models':raw,
            'total':sum(counts.values()),'raw_total':sum(raw.values()),
            'aliases_collapsed':sum(raw.values())-sum(counts.values()),
            'scope':'Finite grid; cutoff/deadline aliases removed; related models are not independent edges'}
    atomic_json(Path(out)/'manifest.json',result)
    return result

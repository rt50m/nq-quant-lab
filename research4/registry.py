"""Finite parameter registry. Preparation is not execution or validation."""
from pathlib import Path
from itertools import product
import hashlib
import json
import math
import os

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
    pending = [m['id'] for m in grid()['models'] if m['implementation'] != 'VALIDATED']
    if pending:
        raise RuntimeError('Full research disabled: missing validated implementations: '+', '.join(pending))

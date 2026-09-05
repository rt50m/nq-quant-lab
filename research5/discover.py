"""Interpretable state discovery: univariate edge maps + shallow regression-tree leaves."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from sklearn.tree import DecisionTreeRegressor, _tree

EXCLUDE = {'day_index','year'}

@dataclass
class Rule:
    id: str
    horizon: int
    direction: int
    conditions: list
    train_n: int
    train_mean: float
    val_n: int
    val_mean: float
    test_n: int
    test_mean: float
    source: str


def mask_rule(X, names, conditions):
    mask = np.ones(len(X), dtype=bool)
    lookup = {n:i for i,n in enumerate(names)}
    for name, op, value in conditions:
        z = X[:, lookup[name]]
        mask &= np.isfinite(z)
        mask &= z <= value if op == '<=' else z > value
    return mask


def _leaf_conditions(tree, names):
    t = tree.tree_
    out = {}
    def walk(node, conds):
        if t.feature[node] == _tree.TREE_UNDEFINED:
            out[node] = list(conds); return
        name = names[t.feature[node]]; thr = float(t.threshold[node])
        walk(t.children_left[node], conds + [(name, '<=', thr)])
        walk(t.children_right[node], conds + [(name, '>', thr)])
    walk(0, [])
    return out


def discover_tree(X, names, y, years, horizon, min_leaf=80, max_depth=4):
    feature_idx = [i for i,n in enumerate(names) if n not in EXCLUDE]
    finite = np.isfinite(y) & np.isfinite(X[:, feature_idx]).all(axis=1)
    train = finite & (years == 2023); val = finite & (years == 2024); test = finite & (years == 2025)
    if train.sum() < min_leaf * 4: return []
    model = DecisionTreeRegressor(max_depth=max_depth, min_samples_leaf=min_leaf, random_state=5)
    model.fit(X[train][:, feature_idx], y[train])
    local_names = [names[i] for i in feature_idx]
    rules = []
    for leaf, conds in _leaf_conditions(model, local_names).items():
        m = mask_rule(X, names, conds) & finite
        for direction in (1, -1):
            tm, vm, xm = m & train, m & val, m & test
            if tm.sum() < min_leaf or vm.sum() < 35 or xm.sum() < 35: continue
            train_mean = direction * float(np.mean(y[tm])); val_mean = direction * float(np.mean(y[vm])); test_mean = direction * float(np.mean(y[xm]))
            if train_mean <= 0 or val_mean <= 0: continue
            rid = f'T{horizon}-{leaf}-' + ('L' if direction == 1 else 'S')
            rules.append(Rule(rid,horizon,direction,conds,int(tm.sum()),train_mean,int(vm.sum()),val_mean,int(xm.sum()),test_mean,'tree'))
    return rules


def discover_univariate(X, names, y, years, horizon, bins=5, min_n=80):
    rules=[]; rid=0
    train_year = years == 2023
    for j,name in enumerate(names):
        if name in EXCLUDE or name in {'minute','time_frac'}: continue
        z=X[:,j]; base=np.isfinite(z)&np.isfinite(y)
        tr=base&train_year
        if tr.sum()<bins*min_n: continue
        q=np.unique(np.nanquantile(z[tr],np.linspace(0,1,bins+1)))
        if len(q)<3: continue
        for b in range(len(q)-1):
            cond=[(name,'>',float(q[b]))] if b==len(q)-2 else [(name,'>',float(q[b])),(name,'<=',float(q[b+1]))]
            m=mask_rule(X,names,cond)&base
            for direction in (1,-1):
                vals=[]; counts=[]; ok=True
                for yr in (2023,2024,2025):
                    k=m&(years==yr); counts.append(int(k.sum())); vals.append(direction*float(np.mean(y[k])) if k.any() else np.nan)
                    if counts[-1] < (min_n if yr==2023 else 35): ok=False
                if ok and vals[0]>0 and vals[1]>0:
                    rid+=1; rules.append(Rule(f'U{horizon}-{rid}-'+('L' if direction==1 else 'S'),horizon,direction,cond,counts[0],vals[0],counts[1],vals[1],counts[2],vals[2],'univariate'))
    return rules


def all_rules(ds):
    X=ds['X']; names=ds['feature_names']; years=X[:,names.index('year')].astype(int)
    rules=[]
    for hz in (15,30,60):
        y=ds[f'y{hz}']
        rules.extend(discover_tree(X,names,y,years,hz))
        rules.extend(discover_univariate(X,names,y,years,hz))
    # Rank by 2024 expectancy with a sample-size stabilizer; 2025 is not used in selection.
    rules.sort(key=lambda r:r.val_mean*np.sqrt(r.val_n),reverse=True)
    return rules

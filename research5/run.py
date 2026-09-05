"""Research 5 end-to-end discovery and extracted-strategy backtest."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from features import build
from discover import all_rules
from backtest import simulate


def jdump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')


def rule_dict(r):
    return {'id':r.id,'horizon':r.horizon,'direction':r.direction,'conditions':r.conditions,'train_n':r.train_n,'train_mean':r.train_mean,'val_n':r.val_n,'val_mean':r.val_mean,'test_n':r.test_n,'test_mean':r.test_mean,'source':r.source}


def main(prepared,out,top_rules=40):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    ds=build(prepared); X=ds['X'];names=ds['feature_names']
    np.savez_compressed(out/'feature-matrix.npz',X=X,**{f'y{h}':ds[f'y{h}'] for h in (15,30,60)})
    (out/'feature-names.json').write_text(json.dumps(names,indent=2))
    rules=all_rules(ds)
    selected=rules[:top_rules]
    jdump(out/'discovered-rules.json',{'count':len(rules),'selected':len(selected),'rules':[rule_dict(r) for r in selected]})

    results=[]
    for r in selected:
        for stop_atr in (0.20,0.30,0.45,0.60):
            for target_r in (1.0,1.5,2.0,3.0):
                for hold in sorted(set((r.horizon,30,60))):
                    s=simulate(ds,r,stop_atr,target_r,hold)
                    if s is None: continue
                    results.append({'rule':r.id,'source':r.source,'horizon':r.horizon,'direction':r.direction,'stop_atr':stop_atr,'target_r':target_r,'hold':hold,**s})
    # Hard minimums; rank on 2024, not 2025. 2025 remains diagnostic.
    eligible=[r for r in results if r['trades_2024']>=35 and r['trades_2025']>=35 and r['pf_2024']>1 and r['net_2024']>0]
    eligible.sort(key=lambda r:(r['net_2024'],r['profit_factor']),reverse=True)
    jdump(out/'strategy-results.json',{'tested':len(results),'eligible':len(eligible),'top':eligible[:100]})

    robust=[]
    for r in eligible:
        # Simple promotion filter: positive in both forward years, DD under current research reference,
        # and no collapse below PF 1 in 2025. This is development triage, not OOS validation.
        if r['net_2025']>0 and r['pf_2025']>1 and r['max_drawdown']>-2000 and r['trades']>=80:
            robust.append(r)
    robust.sort(key=lambda r:(min(r['pf_2024'],r['pf_2025']),r['net_profit']),reverse=True)
    jdump(out/'promotion-candidates.json',{'count':len(robust),'candidates':robust[:30]})

    lines=['# Research 5 — Conditional Edge Discovery',
           f'\nFeature rows: **{len(X):,}** at 5-minute decision snapshots.',
           f'\nDiscovered positive train+2024 state rules: **{len(rules):,}**; extracted top **{len(selected)}**.',
           f'\nExecutable strategy variants tested: **{len(results):,}**; 2024-positive minimum-sample variants: **{len(eligible):,}**.',
           f'\nPromotion-triage candidates: **{len(robust):,}**.',
           '\nSelection uses 2023 discovery and 2024 ranking. 2025 is already-examined development data and is diagnostic only.',
           '\n## Top state rules (ranked without using 2025)',
           '\n| Rule | Source | Hz | Side | 2023 n/mean | 2024 n/mean | 2025 n/mean |',
           '|---|---|---:|---|---:|---:|---:|']
    for r in selected[:15]:
        side='LONG' if r.direction==1 else 'SHORT'
        lines.append(f'| {r.id} | {r.source} | {r.horizon} | {side} | {r.train_n} / {r.train_mean:.5f} | {r.val_n} / {r.val_mean:.5f} | {r.test_n} / {r.test_mean:.5f} |')
    lines += ['\n## Top extracted strategies','\n| Rule | Stop ATR | Target R | Hold | Trades | Net | PF | MDD | PF 2024 | PF 2025 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in robust[:15]:
        lines.append(f"| {r['rule']} | {r['stop_atr']:.2f} | {r['target_r']:.1f} | {r['hold']} | {r['trades']} | {r['net_profit']:,.2f} | {r['profit_factor']:.2f} | {r['max_drawdown']:,.2f} | {r['pf_2024']:.2f} | {r['pf_2025']:.2f} |")
    lines.append('\nA candidate here is only a signal to investigate further. No untouched OOS claim is made; macro-event features are deferred until a verified event calendar is added.')
    (out/'summary.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepared',required=True);p.add_argument('--out',required=True);p.add_argument('--top-rules',type=int,default=40)
    a=p.parse_args();main(a.prepared,a.out,a.top_rules)

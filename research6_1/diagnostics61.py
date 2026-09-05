from __future__ import annotations
import json
import numpy as np
from core61 import path_stats

def _bucket_stats(values,edges,pnl,worst,executed,days,years):
    out=[]
    for name,mask in edges:
        z=executed&mask
        st=path_stats(pnl,worst,z,days,years)
        out.append({'bucket':name,'stats':st})
    return out

def baseline_diagnostics(X,names,sizing):
    p,w,x,days,years=sizing['pnl'],sizing['worst'],sizing['executed'],sizing['days'],sizing['years'];idx={n:i for i,n in enumerate(names)}
    report={}
    m=X[:,idx['signal_minute']]
    report['time_30m']=_bucket_stats(m,[(f'{lo}-{hi}',(m>=lo)&(m<hi)) for lo,hi in [(30,60),(60,90),(90,120),(120,150),(150,180),(180,210),(210,240),(240,270)]],p,w,x,days,years)
    side=X[:,idx['side']];report['side']=_bucket_stats(side,[('long',side==1),('short',side==-1)],p,w,x,days,years)
    for nm,cuts in [('impulse_atr',[.08,.12,.18,.25,.35,999]),('volume_z',[-999,-.5,0,.5,1,999]),('vwap_side_atr',[-999,0,.25,.5,1,999]),('vwap_slope_side_atr',[-999,0,.01,.03,.06,999]),('session_move_side_atr',[-999,0,.25,.5,1,999]),('vxn',[-999,20,25,30,40,999]),('overnight_range_atr',[0,.5,1,1.5,2,999]),('open_vs_overnight_vwap_side_atr',[-999,0,.25,.5,1,999])]:
        z=X[:,idx[nm]];edges=[]
        for a,b in zip(cuts[:-1],cuts[1:]):edges.append((f'[{a},{b})',(z>=a)&(z<b)))
        report[nm]=_bucket_stats(z,edges,p,w,x,days,years)
    if 'trade_number' in idx:
        tn=X[:,idx['trade_number']];report['trade_number']=_bucket_stats(tn,[(str(k),tn==k) for k in [1,2,3,4]]+[('5+',tn>=5)],p,w,x,days,years)
    if 'prev_funded_pnl' in idx:
        pp=X[:,idx['prev_funded_pnl']];report['previous_funded_trade']=_bucket_stats(pp,[('none',~np.isfinite(pp)),('previous_win',pp>0),('previous_loss',pp<0),('previous_flat',pp==0)],p,w,x,days,years)
    return report

def markdown(report,path):
    lines=['# R6.1 baseline forensic diagnostics','']
    for section,rows in report.items():
        lines += [f'## {section}','','| Bucket | Trades | Net | MDD | PF | P/DD | 2023 | 2024 | 2025 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for r in rows:
            s=r['stats']
            if not s: lines.append(f"| {r['bucket']} | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
            else: lines.append(f"| {r['bucket']} | {s['trades']} | {s['net_profit']:.0f} | {s['max_drawdown']:.0f} | {s['profit_factor']:.2f} | {s['profit_to_dd']:.2f} | {s['net_2023']:.0f} | {s['net_2024']:.0f} | {s['net_2025']:.0f} |")
        lines.append('')
    open(path,'w').write('\n'.join(lines))

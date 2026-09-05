from __future__ import annotations
import argparse,gzip,hashlib,itertools,json,os,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from core61 import cfg,enriched_outcomes,select61,sized_path,path_stats,choose_sizing,credible
from context61 import context_matrix,predicate_library
from diagnostics61 import baseline_diagnostics,markdown as diag_markdown
# Reuse the audited R6 feature/signal implementation and frozen transaction-cost assumptions.
sys.path.insert(0,str(ROOT.parent/'research6'))
from features import Features
from signals import build
from registry import config as r6config


def atomic_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');os.replace(tmp,path)
def save_gz(path,obj):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(gzip.compress(json.dumps(obj,allow_nan=False,separators=(',',':')).encode(),3));os.replace(tmp,path)
def load_gz(path):return json.loads(gzip.decompress(Path(path).read_bytes()))
def digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def signal_grid():
    c=cfg()['signal_neighborhood']
    for look,imp in itertools.product(c['lookback'],c['impulse_atr']):
        yield {'family':'IMPULSE_CONTINUATION','lookback':look,'impulse_atr':imp,'volume_z':-99.0}

def attach_extra(f,prepared):
    p=Path(prepared);ov=p/'overnight.npy'
    if ov.exists(): f.overnight=np.load(ov).astype(np.float64,copy=False)
    else: f.overnight=np.full((len(f.a),3),np.nan)
    return f

def unit_stats(trades,f):
    if len(trades)==0:return None
    p,w,x,sy,q,days,years=sized_path(trades,f.dates,'FIXED_QTY',('MNQ',1),r6config())
    return path_stats(p,w,x,days,years)

def selection_score(st,mintr):
    if not st:return None
    if st['trades_2023']<mintr or st['trades_2024']<mintr:return None
    if st['net_2023']<=0 or st['net_2024']<=0 or st['pf_2023']<=1 or st['pf_2024']<=1:return None
    p23=st['net_2023']/max(1.0,abs(st['mdd_2023']));p24=st['net_2024']/max(1.0,abs(st['mdd_2024']))
    support=min(2.0,np.sqrt(min(st['trades_2023'],st['trades_2024'])/mintr))
    return float(min(p23,p24)*support)

def baseline(prepared,out):
    c=cfg();f=attach_extra(Features(prepared),prepared);out=Path(out);out.mkdir(parents=True,exist_ok=True);b=c['baseline'];slip=r6config()['costs']['slippage_per_side_points']
    ev=build(f,b['signal']);X,names=context_matrix(f,ev,b['signal']['lookback'])
    e=b['execution'];raw=enriched_outcomes(f.a,f.atr,ev,e['stop_atr'],e['target_r'],e['hold'],slip,389)
    eligible=np.ones(len(ev),dtype=np.bool_);tr=select61(raw,eligible,e['window_start'],e['window_end'],e['direction'],e['max_trades'],e['cooldown'])
    p,w,x,sym,q,days,years=sized_path(tr,f.dates,'FIXED_RISK',b['sizing']['risk_budget'],r6config());st=path_stats(p,w,x,days,years)
    # Exact regression against the published R6 result.
    expected={'selected':1562,'executed':1264,'net':14817.5,'mdd':-1881.0}
    if len(tr)!=expected['selected'] or st['trades']!=expected['executed'] or abs(st['net_profit']-expected['net'])>1e-6 or abs(st['max_drawdown']-expected['mdd'])>1e-6:
        raise AssertionError(f'R6 baseline regression mismatch: selected={len(tr)} stats={st}')
    Xtr=X[tr[:,12].astype(int)]
    trade_no=np.zeros(len(tr));prev_funded=np.full(len(tr),np.nan);last_day=-1;seq=0;last_funded=np.nan
    for i,t in enumerate(tr):
        d=int(t[0])
        if d!=last_day:last_day=d;seq=0;last_funded=np.nan
        seq+=1;trade_no[i]=seq;prev_funded[i]=last_funded
        if x[i]:last_funded=p[i]
    Xtr=np.c_[Xtr,trade_no,prev_funded];names=names+['trade_number','prev_funded_pnl']
    diag=baseline_diagnostics(Xtr,names,{'pnl':p,'worst':w,'executed':x,'days':days,'years':years})
    frozen=choose_sizing(tr,f.dates,c,r6config(),selection_years=(2023,2024),oracle=False)
    oracle=choose_sizing(tr,f.dates,c,r6config(),selection_years=(2023,2024),oracle=True)
    atomic_json(out/'baseline.json',{'signal_events':len(ev),'selected_opportunities':len(tr),'sizing_skips':int((~x).sum()),'executed_trades':int(x.sum()),'stats':st,'expected_r6_regression':expected,
        'sizing_frozen_on_2023_2024':None if frozen is None else {'mode':frozen['mode'],'spec':frozen['spec'],'selection':frozen['selection'],'full':frozen['full']},
        'oracle_full_period_sizing':None if oracle is None else {'mode':oracle['mode'],'spec':oracle['spec'],'full':oracle['full']}})
    atomic_json(out/'diagnostics.json',diag);diag_markdown(diag,out/'diagnostics.md')
    # Complete ledger, including unfunded selected opportunities.
    with gzip.open(out/'baseline-ledger.jsonl.gz','wt') as fh:
        for i,t in enumerate(tr):
            ci=Xtr[i]
            row={'date':str(f.dates[int(t[0])]),'day_index':int(t[0]),'signal_index':int(t[1]),'entry_index':int(t[2]),'exit_index':int(t[3]),'side':int(t[4]),
                 'pnl_points':float(t[5]),'worst_points':float(t[6]),'stop_points':float(t[7]),'mfe_points':float(t[8]),'mae_points':float(t[9]),'exit_reason':int(t[10]),'hold_minutes':int(t[11]),'ambiguous_stop_target_bar':bool(t[13]),'mfe_r':float(t[8]/t[7]),'mae_r':float(t[9]/t[7]),
                 'funded':bool(x[i]),'symbol':str(sym[i]),'quantity':int(q[i]),'pnl_dollars':float(p[i]),'worst_dollars':float(w[i]),
                 'context':{n:(None if not np.isfinite(ci[j]) else float(ci[j])) for j,n in enumerate(names)}}
            fh.write(json.dumps(row,separators=(',',':'))+'\n')
    (out/'summary.md').write_text(f"# R6.1 baseline regression PASS\n\nExact R6 winner reproduced: {len(tr):,} selected opportunities, {int(x.sum()):,} funded trades at $250 fixed-risk sizing, net **${st['net_profit']:,.1f}**, MDD **${st['max_drawdown']:,.1f}**, PF **{st['profit_factor']:.3f}**.\n\n{int((~x).sum())} selected opportunities were skipped because the $250 budget could not fund even one allowed contract.\n\nSizing frozen using only 2023+2024: **{None if frozen is None else str(frozen['mode'])+' '+str(frozen['spec'])}**; its 2025 result is diagnostic only.\n")

def discover(prepared,out):
    c=cfg();f=attach_extra(Features(prepared),prepared);out=Path(out);out.mkdir(parents=True,exist_ok=True);slip=r6config()['costs']['slippage_per_side_points'];mintr=c['rule_search']['min_trades_per_selection_year']
    candidates=[]
    for gi,s in enumerate(signal_grid()):
        ev=build(f,s);X,names=context_matrix(f,ev,s['lookback']);event_year=np.array([int(str(f.dates[int(d)])[:4]) for d in ev[:,0]],dtype=int);train=event_year==2023
        preds=predicate_library(X,names,train);raw=enriched_outcomes(f.a,f.atr,ev,.35,4.0,120,slip,389)
        singles=[]
        for pi,(name,mask) in enumerate(preds):
            tr=select61(raw,mask.astype(np.bool_),30,270,0,12,0);st=unit_stats(tr,f);score=selection_score(st,mintr)
            # 2023-only rank controls which predicates are allowed into pair construction.
            p23=-1e9
            if st and st['trades_2023']>=mintr and st['net_2023']>0:p23=st['net_2023']/max(1,abs(st['mdd_2023']))
            row={'signal_index':gi,'signal':s,'conditions':[name],'predicate_indices':[pi],'score':score,'train_rank':p23,'unit_mnq_stats':st,'selected':len(tr)}
            singles.append((row,mask))
            if score is not None:candidates.append(row)
        toptrain=sorted(singles,key=lambda z:z[0]['train_rank'],reverse=True)[:c['rule_search']['top_singles_per_signal']]
        for a,b in itertools.combinations(toptrain,2):
            # Avoid pairs that are literally the same mask or contradictory zero-support masks.
            mask=a[1]&b[1]
            if mask.sum()==0:continue
            tr=select61(raw,mask.astype(np.bool_),30,270,0,12,0);st=unit_stats(tr,f);score=selection_score(st,mintr)
            if score is None:continue
            candidates.append({'signal_index':gi,'signal':s,'conditions':a[0]['conditions']+b[0]['conditions'],'predicate_indices':a[0]['predicate_indices']+b[0]['predicate_indices'],'score':score,'train_rank':None,'unit_mnq_stats':st,'selected':len(tr)})
        print('discover',gi,s,'events',len(ev),flush=True)
    # Dedupe semantically identical rows, cap dominance of any one signal neighborhood.
    candidates.sort(key=lambda r:(r['score'],r['unit_mnq_stats']['net_2024'],r['unit_mnq_stats']['trades_2023']+r['unit_mnq_stats']['trades_2024']),reverse=True)
    chosen=[];per_signal={};seen=set()
    for r in candidates:
        key=(json.dumps(r['signal'],sort_keys=True),tuple(sorted(r['conditions'])))
        if key in seen or per_signal.get(r['signal_index'],0)>=4:continue
        seen.add(key);chosen.append(r);per_signal[r['signal_index']]=per_signal.get(r['signal_index'],0)+1
        if len(chosen)>=c['rule_search']['top_rules']:break
    atomic_json(out/'rules.json',{'version':c['version'],'selection_policy':'predicates enter pairs by 2023-only ranking; final rules require positive PF/net and minimum sample in both 2023 and 2024; 2025 is unused','count':len(chosen),'rules':chosen})
    lines=['# R6.1 frozen rules','',f"Retained **{len(chosen)}** signal/filter rules. 2025 was not used to select them.",'','| Rank | Signal | Conditions | Score | 2023 trades/net/PF | 2024 trades/net/PF | 2025 diagnostic net |','|---:|---|---|---:|---|---|---:|']
    for i,r in enumerate(chosen,1):
        s=r['unit_mnq_stats'];sig=f"L{r['signal']['lookback']} I{r['signal']['impulse_atr']}"
        lines.append(f"| {i} | {sig} | {' & '.join(r['conditions'])} | {r['score']:.3f} | {s['trades_2023']}/{s['net_2023']:.0f}/{s['pf_2023']:.2f} | {s['trades_2024']}/{s['net_2024']:.0f}/{s['pf_2024']:.2f} | {s['net_2025']:.0f} |")
    (out/'summary.md').write_text('\n'.join(lines))

def management_paths():
    c=cfg()['management']
    # Static management: broad stop/target/hold neighborhood.
    for stop,target,hold in itertools.product(c['stop_atr'],c['target_r'],c['hold']):
        yield {'kind':'STATIC','stop_atr':stop,'target_r':target,'hold':hold,'be_trigger_r':0.,'trail_activate_r':0.,'trail_distance_r':0.,'progress_minutes':0,'progress_mfe_r':0.}
    # Breakeven activation, no trail.
    for stop,target,hold,be in itertools.product([.25,.35,.45],[0.,2.,4.],[60,120,180],c['be_trigger_r']):
        yield {'kind':'BREAKEVEN','stop_atr':stop,'target_r':target,'hold':hold,'be_trigger_r':be,'trail_activate_r':0.,'trail_distance_r':0.,'progress_minutes':0,'progress_mfe_r':0.}
    # Chandelier-like R trail from achieved MFE.
    for stop,hold,act,dist in itertools.product([.25,.35,.45],[60,120,180],c['trail_activate_r'],c['trail_distance_r']):
        yield {'kind':'TRAIL','stop_atr':stop,'target_r':0.,'hold':hold,'be_trigger_r':0.,'trail_activate_r':act,'trail_distance_r':dist,'progress_minutes':0,'progress_mfe_r':0.}
    # Early progress failure exits at next bar open.
    for stop,target,hold,pm,pr in itertools.product([.25,.35,.45],[0.,2.,4.],[60,120,180],c['progress_minutes'],c['progress_mfe_r']):
        yield {'kind':'PROGRESS','stop_atr':stop,'target_r':target,'hold':hold,'be_trigger_r':0.,'trail_activate_r':0.,'trail_distance_r':0.,'progress_minutes':pm,'progress_mfe_r':pr}

def selection_controls():
    c=cfg()['management']
    for cd,mt in itertools.product(c['cooldown'],c['max_trades']):yield {'cooldown':cd,'max_trades':mt}

def rebuild_rule(f,rule):
    ev=build(f,rule['signal']);X,names=context_matrix(f,ev,rule['signal']['lookback']);event_year=np.array([int(str(f.dates[int(d)])[:4]) for d in ev[:,0]],dtype=int);preds=predicate_library(X,names,event_year==2023)
    lookup={name:mask for name,mask in preds};mask=np.ones(len(ev),dtype=bool)
    for name in rule['conditions']:
        if name not in lookup:raise KeyError('Frozen predicate missing '+name)
        mask&=lookup[name]
    return ev,mask

def row_for(tr,f,c61,r6c,rule,pi,path,control):
    # Selection sizing is frozen using 2023+2024 only; full/oracle is reported separately.
    frozen=choose_sizing(tr,f.dates,c61,r6c,selection_years=(2023,2024),oracle=False)
    oracle=choose_sizing(tr,f.dates,c61,r6c,selection_years=(2023,2024),oracle=True)
    if frozen is None:return None
    full=frozen['full'];ora=oracle['full'] if oracle else None
    return {'rule_rank':rule['rank'],'signal':rule['signal'],'conditions':rule['conditions'],'path_index':pi,'management':path,'selection':control,'selected_opportunities':len(tr),
            'sizing_frozen':{'mode':frozen['mode'],'spec':frozen['spec']},'selection_stats':frozen['selection'],'full_stats':full,
            'oracle_sizing':None if oracle is None else {'mode':oracle['mode'],'spec':oracle['spec']},'oracle_full_stats':ora,
            'pass_scale_frozen':bool(full and full['net_profit']>=c61['objective']['min_net_profit'] and full['max_drawdown']>-c61['objective']['max_drawdown']),
            'pass_credible_scale_frozen':credible(full,c61)}

def shard(prepared,rules_path,out,index,count,seconds):
    c61=cfg();r6c=r6config();f=attach_extra(Features(prepared),prepared);rules=json.load(open(rules_path))['rules'];out=Path(out);out.mkdir(parents=True,exist_ok=True);slip=r6c['costs']['slippage_per_side_points'];start=time.monotonic();completed=expected=0;timed=False
    paths=list(management_paths());controls=list(selection_controls())
    for ri,rr in enumerate(rules):
        if ri%count!=index:continue
        expected+=1;dst=out/f'rule-{ri:03d}.json.gz'
        if dst.exists():completed+=1;continue
        if timed or time.monotonic()-start>=seconds:timed=True;continue
        rule=dict(rr);rule['rank']=ri+1;ev,eligible=rebuild_rule(f,rule);rows=[];cache={};provisional=[]
        for pi,path in enumerate(paths):
            key=tuple(path[k] for k in ['stop_atr','target_r','hold','be_trigger_r','trail_activate_r','trail_distance_r','progress_minutes','progress_mfe_r'])
            if key not in cache:
                cache[key]=enriched_outcomes(f.a,f.atr,ev,path['stop_atr'],path['target_r'],path['hold'],slip,389,path['be_trigger_r'],path['trail_activate_r'],path['trail_distance_r'],path['progress_minutes'],path['progress_mfe_r'])
            raw=cache[key]
            for control in controls:
                tr=select61(raw,eligible.astype(np.bool_),30,270,0,control['max_trades'],control['cooldown'])
                st=unit_stats(tr,f);score=selection_score(st,c61['rule_search']['min_trades_per_selection_year'])
                if score is not None:
                    provisional.append((score,st['net_2023']+st['net_2024'],pi,path,control,tr))
        # Expensive sizing is only applied to finalists chosen without 2025. P/DD is scale-invariant for fixed quantity, so this pruning preserves the high-efficiency paths while preventing millions of redundant sizing passes.
        provisional.sort(key=lambda z:(z[0],z[1]),reverse=True)
        finalists=provisional[:c61['rule_search']['management_finalists_per_rule']]
        for score,selnet,pi,path,control,tr in finalists:
            row=row_for(tr,f,c61,r6c,rule,pi,path,control)
            if row:
                row['presizing_selection_score']=score;rows.append(row)
        save_gz(dst,{'complete':True,'rule':rule,'provisional_count':len(provisional),'rows':rows});completed+=1;print('shard',index,'rule',ri,'provisional',len(provisional),'final',len(rows),flush=True)
    atomic_json(out/'status.json',{'index':index,'count':count,'expected_rules':expected,'completed_rules':completed,'complete':completed==expected,'version':c61['version']})
    if completed!=expected:raise SystemExit(2)

def aggregate(parts,out,count,rules_path=None):
    c=cfg();out=Path(out);out.mkdir(parents=True,exist_ok=True);rows=[]
    expected_rules=json.load(open(rules_path))['count'] if rules_path else None
    for p in Path(parts).rglob('rule-*.json.gz'):
        obj=load_gz(p)
        if not obj.get('complete'):raise ValueError('partial '+str(p))
        rows.extend(obj['rows'])
    if expected_rules is not None:
        names={p.name for p in Path(parts).rglob('rule-*.json.gz')}
        if len(names)!=expected_rules: raise ValueError(f'R6.1 incomplete rule coverage: {len(names)}/{expected_rules}')
    # Deduplicate in case artifact layout duplicates files.
    uniq={}
    for r in rows:
        key=(r['rule_rank'],r['path_index'],r['selection']['cooldown'],r['selection']['max_trades'])
        uniq[key]=r
    rows=list(uniq.values())
    def frozen_key(r):
        s=r['full_stats'];sel=r['selection_stats']
        # Ranking does not use 2025: primary selection evidence is 2023+2024 P/DD, then full is only display/tie-break after evidence.
        return (sel['profit_to_dd'],sel['net_profit'],sel['trades'])
    evidence=sorted(rows,key=frozen_key,reverse=True)
    scale=[r for r in rows if r['pass_scale_frozen']];credible_rows=[r for r in rows if r['pass_credible_scale_frozen']]
    oracle_scale=[r for r in rows if r['oracle_full_stats'] and r['oracle_full_stats']['net_profit']>=c['objective']['min_net_profit'] and r['oracle_full_stats']['max_drawdown']>-c['objective']['max_drawdown']]
    under_cap=[r for r in rows if r['full_stats']['max_drawdown']>-c['objective']['max_drawdown']]
    by_net=sorted(under_cap,key=lambda r:r['full_stats']['net_profit'],reverse=True)
    atomic_json(out/'report.json',{'rows':len(rows),'frozen_scale_passes':len(scale),'frozen_credible_scale_passes':len(credible_rows),'oracle_scale_passes':len(oracle_scale),'best_evidence':evidence[:100],'best_full_net':by_net[:100]})
    with gzip.open(out/'all-enhancements.jsonl.gz','wt') as fh:
        for r in rows:fh.write(json.dumps(r,separators=(',',':'))+'\n')
    lines=['# Research 6.1 — Impulse Continuation Enhancement','',f'Evaluated **{len(rows):,}** filtered-management combinations.','',
           '**Selection discipline:** signal/filter rules are discovered on 2023 and must confirm on 2024. Sizing is chosen using 2023+2024 only and then frozen. 2025 is diagnostic and never chooses a rule or sizing. Because all years have been viewed in prior research, this is disciplined development analysis, not pristine OOS validation.','',
           f"Frozen-sizing PASS_SCALE: **{len(scale)}**. Frozen-sizing CREDIBLE_SCALE: **{len(credible_rows)}**. Full-period oracle PASS_SCALE upper bounds: **{len(oracle_scale)}**.",'',
           '## Best by frozen full-period profit (display only — 2025 did not select)','',
           '| Rank | Net | MDD | P/DD | PF | Trades | 2023 | 2024 | 2025 | Signal | Conditions | Management | Sizing | Credible? |','|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|']
    for i,r in enumerate(by_net[:30],1):
        s=r['full_stats'];mg=r['management'];sz=r['sizing_frozen'];sig=f"L{r['signal']['lookback']} I{r['signal']['impulse_atr']}"
        lines.append(f"| {i} | {s['net_profit']:.0f} | {s['max_drawdown']:.0f} | {s['profit_to_dd']:.1f} | {s['profit_factor']:.2f} | {s['trades']} | {s['net_2023']:.0f} | {s['net_2024']:.0f} | {s['net_2025']:.0f} | {sig} | {' & '.join(r['conditions'])} | {mg['kind']} S{mg['stop_atr']} T{mg['target_r']} H{mg['hold']} cd{r['selection']['cooldown']} mt{r['selection']['max_trades']} | {sz['mode']} {sz['spec']} | {'YES' if r['pass_credible_scale_frozen'] else 'no'} |")
    lines += ['','## Best by 2023+2024 evidence score','', '| Rank | Selection net | Selection P/DD | Full net | Full MDD | Trades | 2023 | 2024 | 2025 diagnostic |','|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for i,r in enumerate(evidence[:25],1):
        a=r['selection_stats'];s=r['full_stats'];lines.append(f"| {i} | {a['net_profit']:.0f} | {a['profit_to_dd']:.1f} | {s['net_profit']:.0f} | {s['max_drawdown']:.0f} | {s['trades']} | {s['net_2023']:.0f} | {s['net_2024']:.0f} | {s['net_2025']:.0f} |")
    if not credible_rows:lines += ['','**Result:** no enhancement met the credible $50k / <$2k scale objective under sizing frozen before the 2025 diagnostic period.']
    else:lines += ['','**Result:** at least one enhancement met the predeclared credible scale hurdle. These still require robustness murder-tests and genuinely newer data before deployment claims.']
    (out/'summary.md').write_text('\n'.join(lines))

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['baseline','discover','shard','aggregate']);p.add_argument('--prepared',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--rules',type=Path);p.add_argument('--parts',type=Path);p.add_argument('--index',type=int,default=0);p.add_argument('--count',type=int,default=16);p.add_argument('--seconds',type=int,default=5000)
    a=p.parse_args()
    if a.mode=='baseline':baseline(a.prepared,a.out)
    elif a.mode=='discover':discover(a.prepared,a.out)
    elif a.mode=='shard':shard(a.prepared,a.rules,a.out,a.index,a.count,a.seconds)
    else:aggregate(a.parts,a.out,a.count,a.rules)
if __name__=='__main__':main()

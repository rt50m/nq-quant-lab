from __future__ import annotations
import argparse,json,os,sys,hashlib,itertools
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from adapters import load_r6_modules, load_r61_modules, common_r1_state, standardize_r1,standardize_r6,standardize_r61,attach_overnight
from sleeves import build_physical_path,trade_sizing,COST
from portfolio import batch_daily_metrics,exact_metrics,credible,mdd_from_daily


def cfg():return json.loads((ROOT/'config7.json').read_text())
def atomic_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');os.replace(tmp,path)
def key_choice(x):return ','.join(map(str,map(int,x)))


def scalar_path_metrics(delta,adverse,expo,dates):return exact_metrics(delta,adverse,expo,dates)


def build(prepared,out):
    c=cfg();out=Path(out);out.mkdir(parents=True,exist_ok=True);p=Path(prepared);a=np.load(p/'rth.npy').astype(float);meta=json.loads((p/'prepared.json').read_text());dates=np.array(meta['dates']);nd=len(dates)
    registry,features,signals,execution=load_r6_modules();f=attach_overnight(features.Features(prepared),prepared)
    r1state=None;raws=[];candidate_meta=[]
    for ci,can in enumerate(c['candidates']):
        if can['source']=='R1':
            if r1state is None:
                from adapters import load_r1_module
                r1=load_r1_module();r1state=common_r1_state(prepared,r1)
            tr,info=standardize_r1(prepared,can,r1state)
        elif can['source']=='R6':tr,info=standardize_r6(prepared,can,f)
        else:tr,info=standardize_r61(prepared,can,f)
        raws.append(tr);candidate_meta.append({'name':can['name'],'source':can['source'],'raw_trades':int(len(tr)),'info':info,'published':can.get('published')})
        np.save(out/f'raw-{ci:02d}.npy',tr)
        print('candidate',ci,can['name'],'raw trades',len(tr),flush=True)
    logical=[];phys_delta=[];phys_adv=[];phys_exp=[];phys_meta=[]
    fixed_mnq=c['logical_sizing']['fixed_mnq'];fixed_nq=c['logical_sizing']['fixed_nq'];risks=c['logical_sizing']['fixed_risk']
    for ci,(can,tr) in enumerate(zip(c['candidates'],raws)):
        base={}
        for label,mode,spec in [('MNQ1','MNQ',1),('NQ1','NQ',1)]+[(f'RISK{b}','RISK',b) for b in risks]:
            d,w,e,tp,ok=build_physical_path(tr,a,mode,spec,nd);pi=len(phys_delta);phys_delta.append(d);phys_adv.append(w);phys_exp.append(e)
            raw_years=np.array([int(str(dates[int(t[0])])[:4]) for t in tr],dtype=int) if len(tr) else np.array([],dtype=int)
            yc={str(y):int(np.sum(ok & (raw_years==y))) for y in (2023,2024,2025)}
            phys_meta.append({'candidate':ci,'candidate_name':can['name'],'label':label,'mode':mode,'spec':spec,'trades':int(ok.sum()),'trades_by_year':yc,'trade_pnl':tp.tolist()})
            base[label]=pi
        logical.append({'id':len(logical),'candidate':ci,'candidate_name':can['name'],'label':'OFF','physical':None,'scale':0.0,'mode':'OFF','spec':0,'max_exposure':0,'trades':0,'trades_by_year':{'2023':0,'2024':0,'2025':0}})
        for q in fixed_mnq:
            logical.append({'id':len(logical),'candidate':ci,'candidate_name':can['name'],'label':f'{q} MNQ','physical':base['MNQ1'],'scale':float(q),'mode':'MNQ','spec':q,'max_exposure':q,'trades':phys_meta[base['MNQ1']]['trades'],'trades_by_year':phys_meta[base['MNQ1']]['trades_by_year']})
        for q in fixed_nq:
            logical.append({'id':len(logical),'candidate':ci,'candidate_name':can['name'],'label':f'{q} NQ','physical':base['NQ1'],'scale':float(q),'mode':'NQ','spec':q,'max_exposure':10*q,'trades':phys_meta[base['NQ1']]['trades'],'trades_by_year':phys_meta[base['NQ1']]['trades_by_year']})
        for b in risks:
            pm=phys_meta[base[f'RISK{b}']]
            logical.append({'id':len(logical),'candidate':ci,'candidate_name':can['name'],'label':f'risk ${b}','physical':base[f'RISK{b}'],'scale':1.0,'mode':'RISK','spec':b,'max_exposure':int(np.max(phys_exp[base[f"RISK{b}"]])),'trades':pm['trades'],'trades_by_year':pm['trades_by_year']})
    delta=np.stack(phys_delta).astype(np.float32);adv=np.stack(phys_adv).astype(np.float32);exp=np.stack(phys_exp).astype(np.uint8)
    np.savez_compressed(out/'physical-paths.npz',delta=delta,adverse=adv,exposure=exp)
    # Daily logical matrix + per-year trade counts/contributions.
    daily_phys=delta.reshape(len(delta),nd,390).sum(axis=2);logical_daily=np.zeros((len(logical),nd),dtype=np.float32)
    for lo in logical:
        if lo['physical'] is not None:logical_daily[lo['id']]=daily_phys[lo['physical']]*lo['scale']
    np.save(out/'logical-daily.npy',logical_daily)
    atomic_json(out/'logical-options.json',{'options':logical,'physical':phys_meta})
    atomic_json(out/'candidates.json',{'dates':dates.tolist(),'candidates':candidate_meta,'version':c['version']})
    # Common-engine correlation uses one MNQ logical sleeve per strategy.
    one=[]
    for ci in range(len(c['candidates'])):
        x=[o for o in logical if o['candidate']==ci and o['mode']=='MNQ' and o['spec']==1][0];one.append(logical_daily[x['id']])
    corr=np.corrcoef(np.stack(one))
    atomic_json(out/'correlation.json',{'names':[x['name'] for x in c['candidates']],'daily_corr_one_mnq':corr.tolist()})
    # Regression check for R6/R6.1 published sizing using standardized paths. R1 is deliberately not asserted because timestamp normalization changed.
    checks=[]
    for ci,can in enumerate(c['candidates']):
        pub=can.get('published',{});mode=pub.get('mode');spec=pub.get('spec');tr=raws[ci]
        if mode not in ('FIXED_RISK','FIXED_QTY'):continue
        if mode=='FIXED_RISK':pmode,pspec='RISK',spec
        else:pmode,pspec=('MNQ',spec[1]) if spec[0]=='MNQ' else ('NQ',spec[1])
        d,w,e,tp,ok=build_physical_path(tr,a,pmode,pspec,nd);st=scalar_path_metrics(d,w,e,dates)
        checks.append({'name':can['name'],'published_net':pub['net'],'published_mdd':pub['mdd'],'common_net':st['net_profit'],'common_mdd':st['max_drawdown'],'net_match':abs(st['net_profit']-pub['net'])<1e-6,'mdd_match':abs(st['max_drawdown']-pub['mdd'])<1e-6})
        if can['source'] in ('R6','R6.1') and (not checks[-1]['net_match'] or not checks[-1]['mdd_match']):raise AssertionError('Common path regression failed '+str(checks[-1]))
    atomic_json(out/'regression.json',{'checks':checks})
    lines=['# Research 7 build / common-engine verification','',f"Built **{len(c['candidates'])}** candidate strategy sleeves on the same R4 timestamp-normalized data.",'',
           'R6/R6.1 published sizing is required to reproduce exactly. R1 headline P&L is not required to match because R7 deliberately replays those rules on the later timestamp-audited common engine.','',
           '## Candidates','', '| Strategy | Source | Raw trades | Published net | Published MDD |','|---|---|---:|---:|---:|']
    for x,can in zip(candidate_meta,c['candidates']):lines.append(f"| {x['name']} | {x['source']} | {x['raw_trades']} | {can.get('published',{}).get('net',0):,.0f} | {can.get('published',{}).get('mdd',0):,.0f} |")
    lines += ['','## One-MNQ daily P&L correlation','', 'See `correlation.json`. Low/negative correlations are the core R7 thesis; high correlations mean the portfolio route is likely dead.']
    (out/'summary.md').write_text('\n'.join(lines))


def load_sleeves(sleeves):
    s=Path(sleeves);obj=json.load(open(s/'logical-options.json'));logical=obj['options'];phys=obj['physical'];daily=np.load(s/'logical-daily.npy');paths=np.load(s/'physical-paths.npz');cand=json.load(open(s/'candidates.json'));dates=np.array(cand['dates']);return logical,phys,daily,paths,cand,dates


def per_candidate_options(logical,nc):
    return [[o['id'] for o in logical if o['candidate']==ci] for ci in range(nc)]


def approx_score(m):
    den=np.maximum(100.0,np.abs(m['mdd']));base=m['net']/den
    stable=(np.minimum(m['net_2023'],m['net_2024'])>0).astype(float)
    return base+stable*np.minimum(m['net_2023'],m['net_2024'])/np.maximum(500.0,np.abs(m['mdd']))


def random_choices(rng,opts,logical,n,amin,amax):
    S=len(opts);out=np.empty((n,S),dtype=np.int32)
    off=[next(i for i in x if logical[i]['mode']=='OFF') for x in opts]
    out[:]=np.array(off,dtype=np.int32)
    for r in range(n):
        k=int(rng.integers(amin,min(amax,S)+1));active=rng.choice(S,size=k,replace=False)
        for s in active:
            choices=[i for i in opts[s] if logical[i]['mode']!='OFF']
            # Bias toward smaller allocations but keep all frozen options reachable.
            weights=np.array([1.0/(1.0+logical[i]['max_exposure'])**0.55 for i in choices]);weights/=weights.sum()
            out[r,s]=rng.choice(choices,p=weights)
    return out


def deterministic_seeds(opts,logical,daily,years):
    S=len(opts);off=[next(i for i in x if logical[i]['mode']=='OFF') for x in opts];best=[]
    for s in range(S):
        scored=[]
        for oid in opts[s]:
            if logical[oid]['mode']=='OFF':continue
            d=daily[oid];sel=d[years<=2024];m=mdd_from_daily(sel);net=sel.sum();n23=d[years==2023].sum();n24=d[years==2024].sum()
            if net>0 and n23>0 and n24>0:scored.append((net/max(100,abs(m)),oid))
        best.append([x[1] for x in sorted(scored,reverse=True)[:3]])
    rows=[]
    for s in range(S):
        for o in best[s]:x=off.copy();x[s]=o;rows.append(x)
    for a,b in itertools.combinations(range(S),2):
        for oa in best[a]:
            for ob in best[b]:x=off.copy();x[a]=oa;x[b]=ob;rows.append(x)
    return np.asarray(rows,dtype=np.int32) if rows else np.empty((0,S),dtype=np.int32)


def exact_one(choice,logical,phys,paths,dates,cand):
    delta=np.zeros(paths['delta'].shape[1],dtype=float);adv=np.zeros_like(delta);expo=np.zeros(len(delta),dtype=np.int16);contrib=[];trade_pnls=[];trades=0;year_tr={2023:0,2024:0,2025:0};active=0
    years=np.array([int(str(d)[:4]) for d in dates],dtype=int)
    for oid in choice:
        o=logical[int(oid)]
        if o['physical'] is None:continue
        active+=1;pi=int(o['physical']);sc=float(o['scale']);delta+=paths['delta'][pi]*sc;adv+=paths['adverse'][pi]*sc;expo+=paths['exposure'][pi].astype(np.int16)*int(round(sc))
        d=(paths['delta'][pi]*sc).reshape(len(dates),390).sum(axis=1);contrib.append(float(d.sum()));trades+=int(o['trades']);trade_pnls.extend((np.asarray(phys[pi].get('trade_pnl',[]),dtype=float)*sc).tolist())
        for y in (2023,2024,2025): year_tr[y]+=int(o.get('trades_by_year',{}).get(str(y),0))
    st=exact_metrics(delta,adv,expo,dates)
    tp=np.asarray(trade_pnls,dtype=float);gp=float(tp[tp>0].sum()) if len(tp) else 0.0;gl=float(-tp[tp<0].sum()) if len(tp) else 0.0
    st['profit_factor']=gp/gl if gl>0 else (99.0 if gp>0 else 0.0);st['win_rate']=float(np.mean(tp>0)) if len(tp) else 0.0;st['avg_trade']=float(np.mean(tp)) if len(tp) else 0.0
    pos=[max(0,x) for x in contrib];share=max(pos)/st['net_profit'] if st['net_profit']>0 and pos else 0.0
    meta={'active_strategies':active,'portfolio_trades':trades,'max_strategy_profit_share':float(share)}
    for y in (2023,2024,2025):meta[f'trades_{y}']=int(year_tr[y])
    return st,meta,contrib


def search(sleeves,out,index,count,samples):
    c=cfg();logical,phys,daily,paths,cand,dates=load_sleeves(sleeves);cand['_sleeves']=str(sleeves);years=np.array([int(str(d)[:4]) for d in dates]);opts=per_candidate_options(logical,len(c['candidates']));rng=np.random.default_rng(c['search']['seed']+index*100003)
    allc=[]
    if index==0:allc.append(deterministic_seeds(opts,logical,daily,years))
    allc.append(random_choices(rng,opts,logical,samples,c['search']['random_active_min'],c['search']['random_active_max']))
    choices=np.vstack([x for x in allc if len(x)]);seen={};approx=[];B=2000
    for start in range(0,len(choices),B):
        ch=choices[start:start+B];dp=np.zeros((len(ch),len(dates)),dtype=np.float32);soft=np.zeros(len(ch),dtype=int)
        for s in range(ch.shape[1]):dp+=daily[ch[:,s]];soft+=np.array([logical[int(x)]['max_exposure'] for x in ch[:,s]])
        mfull=batch_daily_metrics(dp,years);msel=batch_daily_metrics(dp[:,years<=2024],years[years<=2024]);score=approx_score(msel)
        # union of evidence-ranking and full-period upper-bound ranking; exact path decides final validity.
        good=np.where((soft<=c['search']['approx_exposure_soft_cap']) & (mfull['net']>0))[0]
        if not len(good):continue
        a=good[np.argsort(score[good])[-min(120,len(good)):]];oracle=mfull['net']/np.maximum(100,np.abs(mfull['mdd']));b=good[np.argsort(oracle[good])[-min(80,len(good)):]]
        for j in np.unique(np.r_[a,b]):
            k=key_choice(ch[j]);seen[k]=ch[j].copy()
    finalists=list(seen.values());
    # Keep best approximate finalists globally before expensive minute-level replay.
    ranked=[]
    for ch in finalists:
        dp=sum((daily[int(o)] for o in ch),np.zeros(len(dates),dtype=float));sel=dp[years<=2024];ms=mdd_from_daily(sel);score=sel.sum()/max(100,abs(ms));ranked.append((score,dp.sum()/max(100,abs(mdd_from_daily(dp))),ch))
    ranked=sorted(ranked,key=lambda z:max(z[0],z[1]),reverse=True)[:c['search']['exact_finalists_per_shard']]
    rows=[]
    for _,__,ch in ranked:
        st,meta,contrib=exact_one(ch,logical,phys,paths,dates,cand)
        sel_daily=sum((daily[int(o)] for o in ch),np.zeros(len(dates),dtype=float))[years<=2024];sel_mdd=mdd_from_daily(sel_daily);sel_net=float(sel_daily.sum());n23=st['net_2023'];n24=st['net_2024'];evidence=(min(n23,n24)>0) and sel_net>0
        row={'choice':list(map(int,ch)),'labels':[logical[int(o)]['label'] for o in ch],'strategies':[logical[int(o)]['candidate_name'] for o in ch],'stats':st,'meta':meta,'contributions':contrib,
             'selection_net':sel_net,'selection_daily_mdd':sel_mdd,'selection_score':sel_net/max(100,abs(sel_mdd)) if evidence else -1e99,
             'pass_scale':bool(st['net_profit']>=c['objective']['min_net_profit'] and st['max_drawdown']>-c['objective']['max_drawdown'] and st['max_exposure_equiv_mnq']<=c['objective']['max_equivalent_mnq_exposure']),
             'pass_prop_strict':bool(st['net_profit']>=c['objective']['min_net_profit'] and st['max_drawdown']>-c['objective']['max_drawdown'] and st['worst_day']>-c['objective']['daily_loss_reference'] and st['max_exposure_equiv_mnq']<=c['objective']['max_equivalent_mnq_exposure'])}
        row['credible']=credible(st,meta,c['objective']);rows.append(row)
    rows.sort(key=lambda r:(r['selection_score'],r['stats']['net_profit']),reverse=True)
    atomic_json(Path(out)/'results.json',{'index':index,'count':count,'samples':len(choices),'exact':len(rows),'rows':rows[:250]})
    print('search shard',index,'samples',len(choices),'exact',len(rows),flush=True)


def aggregate(sleeves,parts,out,count):
    c=cfg();logical,phys,daily,paths,cand,dates=load_sleeves(sleeves);rows=[]
    files=list(Path(parts).rglob('results.json'))
    if len(files)!=count:raise ValueError(f'missing R7 search shards {len(files)}/{count}')
    for p in files:rows.extend(json.load(open(p))['rows'])
    uniq={key_choice(r['choice']):r for r in rows};rows=list(uniq.values())
    disciplined=sorted(rows,key=lambda r:(r['selection_score'],r['stats']['net_profit']),reverse=True);oracle=sorted(rows,key=lambda r:(r['stats']['net_profit'] if r['stats']['max_drawdown']>-c['objective']['max_drawdown'] and r['stats']['max_exposure_equiv_mnq']<=c['objective']['max_equivalent_mnq_exposure'] else -1e99,r['stats']['profit_to_dd']),reverse=True)
    passes=[r for r in rows if r['pass_scale']];strict=[r for r in rows if r['pass_prop_strict']];cred=[r for r in rows if r['credible']]
    atomic_json(Path(out)/'report.json',{'unique_exact_portfolios':len(rows),'scale_passes':len(passes),'prop_strict_passes':len(strict),'credible_passes':len(cred),'best_disciplined':disciplined[:100],'best_oracle':oracle[:100]})
    bestd=disciplined[0] if disciplined else None;besto=oracle[0] if oracle else None
    lines=['# Research 7 — Multi-Strategy Hedge / Portfolio Optimization','',f'Exact minute-level finalists evaluated: **{len(rows):,}**.','',
           'All candidate sleeves are replayed on the same R4 timestamp-normalized NQ data. Portfolio MDD uses a conservative one-minute adverse envelope: if multiple sleeves are open, each sleeve is marked at its own adverse bar extreme before summing. This can overstate drawdown for offsetting long/short positions but does not understate it under one-minute OHLC uncertainty.','',
           f"Hard objective: **net >= ${c['objective']['min_net_profit']:,.0f}, combined MDD strictly under ${c['objective']['max_drawdown']:,.0f}, max simultaneous exposure <= {c['objective']['max_equivalent_mnq_exposure']} MNQ-equivalents**.",'',
           f"PASS_SCALE: **{len(passes)}**. PROP_STRICT (also worst day > -${c['objective']['daily_loss_reference']:,.0f}): **{len(strict)}**. CREDIBLE_SCALE: **{len(cred)}**.",'',
           '## Disciplined leaderboard','',
           'Portfolio weights are ranked using 2023+2024 evidence only; 2025 is displayed afterward.','',
           '| Rank | Full net | MDD | P/DD | PF | Trades | 2023 | 2024 | 2025 | Worst day | Max exp | Active | Allocation |','|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for i,r in enumerate(disciplined[:25],1):
        s=r['stats'];alloc='; '.join(f"{n}: {lab}" for n,lab in zip(r['strategies'],r['labels']) if lab!='OFF')
        lines.append(f"| {i} | {s['net_profit']:,.0f} | {s['max_drawdown']:,.0f} | {s['profit_to_dd']:.1f} | {s['profit_factor']:.2f} | {r['meta']['portfolio_trades']} | {s['net_2023']:,.0f} | {s['net_2024']:,.0f} | {s['net_2025']:,.0f} | {s['worst_day']:,.0f} | {s['max_exposure_equiv_mnq']} | {r['meta']['active_strategies']} | {alloc} |")
    lines += ['','## Full-period oracle upper bound','', 'This ranking uses all 2023-2025 data and is **not** selection-valid; it answers only whether the frozen strategy set is mathematically capable of the target inside the observed sample.','',
              '| Rank | Net | MDD | P/DD | PF | Trades | 2023 | 2024 | 2025 | Max exp | Allocation |','|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for i,r in enumerate(oracle[:20],1):
        s=r['stats'];alloc='; '.join(f"{n}: {lab}" for n,lab in zip(r['strategies'],r['labels']) if lab!='OFF')
        lines.append(f"| {i} | {s['net_profit']:,.0f} | {s['max_drawdown']:,.0f} | {s['profit_to_dd']:.1f} | {s['profit_factor']:.2f} | {r['meta']['portfolio_trades']} | {s['net_2023']:,.0f} | {s['net_2024']:,.0f} | {s['net_2025']:,.0f} | {s['max_exposure_equiv_mnq']} | {alloc} |")
    if cred:lines += ['','**Result:** at least one portfolio met the predeclared credible $50k / <$2k development hurdle. It still requires robustness and genuinely newer data before deployment claims.']
    elif passes:lines += ['','**Result:** at least one mathematical scale pass exists, but none met the stricter credibility screen. Treat as a research lead, not a solved model.']
    else:lines += ['','**Result:** the current survivor set did not reach $50k / <$2k even after joint portfolio allocation. If the oracle is also far below $50k, the next research should add genuinely new information/exposure rather than keep reweighting these same NQ RTH sleeves.']
    Path(out).mkdir(parents=True,exist_ok=True);(Path(out)/'summary.md').write_text('\n'.join(lines))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['build','search','aggregate']);p.add_argument('--prepared',type=Path);p.add_argument('--sleeves',type=Path);p.add_argument('--parts',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--index',type=int,default=0);p.add_argument('--count',type=int,default=8);p.add_argument('--samples',type=int,default=None);a=p.parse_args()
    if a.mode=='build':build(a.prepared,a.out)
    elif a.mode=='search':search(a.sleeves,a.out,a.index,a.count,a.samples or cfg()['search']['samples_per_shard'])
    else:aggregate(a.sleeves,a.parts,a.out,a.count)
if __name__=='__main__':main()

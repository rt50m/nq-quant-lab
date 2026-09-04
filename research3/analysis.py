"""Exact coverage gate, all-ten breakdown, chronological selection and finalist stress."""
import json
from pathlib import Path
from statistics import NormalDist
import numpy as np
import pandas as pd
from registry import grid, groups, study_hash, atomic_json
from signals import Features, build

def performance(x):
    x=np.asarray(x,float);eq=np.r_[0,np.cumsum(x)];sd=x.std(ddof=1) if len(x)>1 else 0
    return {'net':float(x.sum()),'max_drawdown':float(np.min(eq-np.maximum.accumulate(eq))),
        'daily_sharpe':float(x.mean()/sd*np.sqrt(252)) if sd>0 else None,'days':len(x)}

def uncertainty(x,trials):
    x=np.asarray(x,float);n=len(x)
    if n<40 or x.std()==0:return {'status':'UNDERPOWERED'}
    rng=np.random.default_rng(3003);width=20
    means=[]
    for _ in range(500):
        starts=rng.integers(0,n,size=int(np.ceil(n/width)))
        sample=np.concatenate([x[(np.arange(width)+s)%n] for s in starts])[:n]
        means.append(sample.mean())
    z=(x-x.mean())/x.std();skew=np.mean(z**3);kurt=np.mean(z**4);sr=x.mean()/x.std()
    N=NormalDist();gamma=.5772156649
    benchmark=0 if trials<=1 else ((1-gamma)*N.inv_cdf(1-1/trials)+gamma*N.inv_cdf(1-1/(trials*np.e)))/np.sqrt(n-1)
    denom=np.sqrt(max(1e-12,1-skew*sr+(kurt-1)*sr*sr/4))
    dsr=N.cdf((sr-benchmark)*np.sqrt(n-1)/denom)
    return {'mean_daily_pnl_ci95_20day_block':np.quantile(means,[.025,.975]).tolist(),
        'deflated_sharpe_probability_all_rows_independent':float(dsr),
        'trial_count_upper_bound':int(trials),
        'limitations':'DSR is an approximate diagnostic with iid normalization; grid rows are correlated. CI is conditional on this reused development sample.'}

def sequential(ids,daily,known,events,dates):
    """At each month start select using preceding <=252 days only; no current-month data."""
    dates=np.asarray(dates);months=np.array([d[:7] for d in dates]);pnl=np.zeros(len(dates));chosen=[];covered=np.zeros(len(dates),bool)
    for month in np.unique(months):
        test=np.where(months==month)[0];start=int(test[0]);left=max(0,start-252)
        if start-left<126:continue
        train=daily[:,left:start];okay=known[:,left:start].all(axis=1)&(events[:,left:start].sum(axis=1)>=20)
        equity=np.cumsum(train,axis=1);peak=np.maximum.accumulate(np.c_[np.zeros(len(train)),equity],axis=1)[:,1:]
        okay &= (equity-peak).min(axis=1)>-grid()['account']['max_loss']
        score=np.where(okay,train.sum(axis=1),-np.inf)
        if not np.isfinite(score).any() or score.max()<=0:continue
        winner=int(np.argmax(score));observed=known[winner,test]
        pnl[test]=np.where(observed,daily[winner,test],0);covered[test]=observed
        chosen.append({'month':month,'id':ids[winner],'training_start':str(dates[left]),
                       'training_end':str(dates[start-1]),'unknown_test_days':int((~observed).sum())})
    return pnl,covered,chosen

def aggregate(parts,prepared,out):
    from run import verified_group,evaluate,describe
    out=Path(out);out.mkdir(parents=True,exist_ok=True);f=Features(prepared)
    expected=list(groups());paths={};rows=[];arrays=[];known=[];events=[];eligible=[];ids=[];missing=[]
    for path in Path(parts).rglob('group-*.json'):
        key=int(path.stem.split('-')[1])
        if key in paths and path.read_bytes()!=paths[key].read_bytes():raise ValueError('Conflicting duplicate group')
        paths[key]=path
    valid_indices={g[0] for g in expected}
    if set(paths)-valid_indices:raise ValueError('Foreign manifest group')
    for index,s,configs in expected:
        if index not in paths:
            missing.extend(c['id'] for c in configs);continue
        result=verified_group(paths[index],configs,f.meta['data_hash'])
        if result is None:missing.extend(c['id'] for c in configs);continue
        with np.load(paths[index].with_suffix('.npz')) as z:
            if z['ids'].tolist()!=[c['id'] for c in configs] or not np.array_equal(z['dates'],f.dates):raise ValueError('Array manifest mismatch')
            arrays.append(z['daily']);known.append(z['known']);events.append(z['events'])
            eligible.extend([z['eligible'].copy()]*len(configs));ids.extend(z['ids'].tolist())
        rows.extend(result['rows'])
    total=sum(len(v[2]) for v in expected)
    completion={'status':'INCOMPLETE' if missing else 'COMPLETE_DEVELOPMENT_GRID','expected':total,'completed':len(rows),
                'missing':len(missing),'study_hash':study_hash(),'data_hash':f.meta['data_hash'],
                'holdout':'NOT_PRISTINE; previously examined 2023-2025','live_ready':False}
    atomic_json(out/'completion.json',completion);atomic_json(out/'missing_ids.json',missing)
    if rows:pd.DataFrame([{k:v for k,v in r.items() if k!='config'} for r in rows]).to_csv(out/'all_results.csv',index=False)
    (out/'summary.md').write_text(f'# Research #3\n\n**{completion["status"]}: {len(rows):,} / {total:,}**\n\n'+
        'Development results; data quality and account qualification are separate from grid completion.\n',encoding='utf-8')
    if missing:raise SystemExit(2)
    daily=np.concatenate(arrays);known=np.concatenate(known);events=np.concatenate(events);eligible=np.array(eligible)
    # Unknown paths have no accepted P&L. Keep their masks alongside all exported arrays.
    daily=np.where(known,daily,0);df=pd.DataFrame(rows)
    summaries=[];wf={};selected_artifacts={};all_choices={};control_comparisons=[]
    text=['# Research #3 â€” all ten models','',f'Completed **{len(rows):,} / {total:,}** configurations, including explicit controls.',
          '', 'Best historical profit is selection on reused development data. Prop screen is modeled trading-risk survival, not evaluation-pass or payout qualification.',
          'Missing paths are excluded from accepted P&L and prevent qualifying the full account path. A model can have no qualifying variant.','',
          '| Model | Best profit ID | Net | Best qualifying prop ID | Account net | Decision |',
          '|---|---|---:|---|---:|---|']
    stress=[]
    for family in sorted(grid()['models']):
        ix=np.where((df.family==family)&(~df.control))[0];cand=df.iloc[ix]
        best=int(cand.net_profit.idxmax());qual=cand[cand.prop_screen_pass]
        prop=int(qual.account_net_profit.idxmax()) if len(qual) else None
        local_ids=[ids[i] for i in ix]
        w,coverage,choices=sequential(local_ids,daily[ix][:,f.keep],known[ix][:,f.keep],events[ix][:,f.keep],f.dates[f.keep])
        wf[family]=w;all_choices[family]=choices
        best_row=rows[best];state='NEEDS_DATA' if best_row['missing_path_days'] else 'UNDERPOWERED' if best_row['event_days']<grid()['minimum_event_days'] else 'REJECT'
        ci=uncertainty(w[coverage],len(ix))
        if state=='REJECT' and prop is not None and w.sum()>0 and ci.get('mean_daily_pnl_ci95_20day_block',[0])[0]>0:state='ADVANCE_TO_INDEPENDENT_DATA'
        summary={'family':family,'configurations':len(ix),'best_profit':best_row,'best_prop':rows[prop] if prop is not None else None,
            'decision':state,'sequential_development':performance(w),'selected_months':len(choices),
            'selected_known_days':int(coverage.sum()),'uncertainty':ci,
            'qualification':'A provisional screen; controls, stress and independent data still required'}
        summaries.append(summary)
        text.append(f'| {family} | {ids[best]} | {best_row["net_profit"]:,.2f} | {ids[prop] if prop is not None else "NONE"} | {rows[prop]["account_net_profit"] if prop is not None else 0:,.2f} | {state} |')
        selected=set([best]+([prop] if prop is not None else []))
        for j in selected:
            c=rows[j]['config'];sig=build(f,c['signal'])
            for slip in [.25,.5,.75]:
                r,*_=evaluate(f,c,sig,False,slip);acc,b,status,fail=evaluate(f,c,sig,True,slip)
                stress.append({'id':ids[j],'family':family,'slippage_per_side':slip,'delay_minutes':0,**describe(f,r),
                               'account_balance':float(b),'account_status':int(status)})
            delayed=list(sig)
            for field in range(3):
                delayed[field]=np.full_like(sig[field],np.nan);delayed[field][:,1:]=sig[field][:,:-1]
            delayed[3]=np.full_like(sig[3],389);delayed[3][:,1:]=sig[3][:,:-1]
            r,*_=evaluate(f,c,delayed,False,.25);acc,b,status,fail=evaluate(f,c,delayed,True,.25)
            stress.append({'id':ids[j],'family':family,'slippage_per_side':.25,'delay_minutes':1,
                           **describe(f,r),'account_balance':float(b),'account_status':int(status)})
            r,*_=evaluate(f,c,sig,False,.25)
            pd.DataFrame({'date':f.dates,'pnl':r[:,0],'known':r[:,7]==0,'entries':r[:,10],
                'worst_liquidation_pnl':r[:,1],'last_exit_rth_minute':r[:,15]}).to_csv(out/f'{ids[j]}-daily.csv',index=False)
            selected_artifacts[ids[j]]=c
        # Compare each baseline control with the selected profit candidate on shared
        # eligible, observable dates. This is descriptive, not another winner search.
        for j in np.where((df.family==family)&df.control)[0]:
            mask=known[best]&known[j]&eligible[best]&eligible[j]&f.keep
            delta=daily[best,mask]-daily[j,mask]
            control_comparisons.append({'family':family,'candidate':ids[best],'control':ids[j],
                'common_days':int(mask.sum()),'candidate_net':float(daily[best,mask].sum()),
                'control_net':float(daily[j,mask].sum()),'difference':float(delta.sum())})
        # A provisional advance also needs the chosen prop variant to remain
        # profitable under delayed entry and double/triple slippage. This gate
        # cannot be evaluated until the stress rows have actually been produced.
        if state=='ADVANCE_TO_INDEPENDENT_DATA':
            prop_stress=[v for v in stress if v['id']==ids[prop]]
            strong=all(v['net_profit']>0 and v['missing_path_days']==0 and v['account_status']==0 for v in prop_stress)
            if not strong:
                state='REJECT';summary['decision']=state
                summary['rejection_reason']='Selected prop variant failed execution stress'
                text[-1]=text[-1].replace('ADVANCE_TO_INDEPENDENT_DATA',state)
    atomic_json(out/'model_breakdown.json',summaries);atomic_json(out/'finalist_configs.json',selected_artifacts)
    atomic_json(out/'chronological_choices.json',all_choices)
    pd.DataFrame(stress).to_csv(out/'finalist_cost_stress.csv',index=False)
    pd.DataFrame(control_comparisons).to_csv(out/'matched_date_controls.csv',index=False)
    wdf=pd.DataFrame(wf,index=f.dates[f.keep]);wdf.index.name='date';wdf.to_csv(out/'chronological_daily.csv')
    wdf.corr().to_csv(out/'model_daily_correlation.csv')
    atomic_json(out/'data_quality.json',f.meta)
    np.savez_compressed(out/'all_daily.npz',ids=np.array(ids),dates=f.dates,daily=daily,known=known,events=events)
    text.extend(['','The chronological series changes settings at month starts using only preceding dates. It is a development selection diagnostic, not a combined continuously replayed prop account.',
        'Quarter/year stability, whole-contract skips, long/short attribution and trade concentration remain visible in the detailed files. Controls are hypotheses comparisons, not proof of causality.',
        'Download this artifact before retention expires. Original per-group checkpoints allow reproduction and recovery.'])
    (out/'ALL_10_BREAKDOWN.md').write_text('\n'.join(text),encoding='utf-8')
    (out/'summary.md').write_text('\n'.join(text),encoding='utf-8')
    print(json.dumps(completion),flush=True)

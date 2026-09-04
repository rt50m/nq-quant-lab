"""Shared raw/account evaluation and diagnostic statistics."""
import numpy as np
from registry import grid
from signals import build
from execution import replay,parameters,event_rows,posterior_path


def context(f,s):
    number=int(s['model'][-2:]);sig=build(f,s)
    events=event_rows(f,sig,s.get('opening',15))
    # The overnight/variable opening threshold is already encoded in signals.
    # H/L event columns are only needed for fixed-range model31 and resting limits.
    adverse=np.full((len(f.a),390,2),np.nan);bayes=adverse.copy()
    if number==25:adverse=f.adverse_threshold(s['observe'],s['magnitude_quantile'])
    if number==26:
        z=f.standardized(60)
        for d in np.unique(events[:,0].astype(int)):
            for j,side in enumerate([1,-1]):
                chosen=events[(events[:,0]==d)&(events[:,2]==side)]
                if not len(chosen):continue
                t=int(chosen[0,1]);result=posterior_path(z[d,t:],s['hazard'],s['recent_run'])
                bayes[d,t:,j]=result[:,j]
    return events,adverse,bayes


def evaluate(f,c,ctx,enforce=False,slip=None):
    g=grid();a=g['account'];cost=g['costs']
    accounts=np.array([a['start'],a['max_loss'],a['locked_floor'],min(a['daily_loss'],a['personal_daily_stop']),
                       cost['nq_commission_per_side'],cost['mnq_commission_per_side'],a['max_nq'],a['account_buffer'],a['max_mnq']],dtype=float)
    values,p=parameters(c)
    return replay(f.a,ctx[0],f.atr,f.vwap,ctx[1],ctx[2],int(c['model'][-2:]),values,p,accounts,enforce,
                  cost['slippage_per_side_points'] if slip is None else slip)


def describe(f,r):
    known=r[:,6]==0;daily=np.where(known,r[:,0],0.)
    eq=np.r_[0.,np.cumsum(daily)];dd=eq-np.maximum.accumulate(eq)
    trades=r[known,1].sum();loss=-r[known,3].sum();sd=daily[f.keep].std(ddof=1)
    result={'net_profit':float(daily.sum()),'trades':int(trades),
            'win_rate':float(r[known,4].sum()/trades) if trades else None,
            'profit_factor':float(r[known,2].sum()/loss) if loss>0 else None,
            'max_drawdown':float(dd.min()),'worst_day':float(daily.min()),
            'daily_sharpe':float(daily[f.keep].mean()/sd*np.sqrt(252)) if sd>0 else None,
            'unknown_days':int(r[:,6].sum()),'ambiguous_exits':int(r[:,5].sum()),
            'quantity_skips':int(r[:,7].sum()),'nq_entries':int(r[:,8].sum()),'mnq_entries':int(r[:,9].sum()),
            'max_quantity':int(r[:,10].max()),'max_planned_risk':float(r[:,11].max()),
            'protection_exits':int(r[:,12].sum()),'last_exit_minute':int(r[:,13].max()),
            'worst_liquidation_day':float(r[:,14].min()),'long_net':float(r[:,15].sum()),
            'short_net':float(r[:,16].sum()),'partial_exits':int(r[:,18].sum()),'additions':int(r[:,19].sum())}
    for year in ['2023','2024','2025']:
        mask=np.char.startswith(f.dates,year)
        result['net_'+year]=float(daily[mask].sum())
        result['trades_'+year]=int(r[mask&known,1].sum())
    return result


def row(f,c,ctx):
    raw,_,_,_=evaluate(f,c,ctx)
    account,balance,status,failed=evaluate(f,c,ctx,True)
    stats=describe(f,raw);acc=describe(f,account)
    good=(status==0 and stats['unknown_days']==0 and acc['trades']>=grid()['minimum_event_days'] and balance>grid()['account']['start']
          and stats['max_drawdown']>-grid()['account']['max_loss'])
    if c['model']=='R4-15' and stats['ambiguous_exits']>0:good=False
    return {**stats,'evaluation_status':'NEEDS_DATA' if stats['unknown_days'] else 'NO_TRADES' if stats['trades']==0 else 'EVALUATED',
            'account_balance':float(balance),'account_net_profit':acc['net_profit'],
            'account_trades':acc['trades'],'account_status':['SURVIVED','BREACHED','NEEDS_DATA'][status],
            'account_stop_date':str(f.dates[failed]) if failed>=0 else None,'prop_screen_pass':bool(good)}

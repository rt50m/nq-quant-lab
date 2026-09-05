from __future__ import annotations
import math
import numpy as np


def mdd_from_daily(daily: np.ndarray) -> float:
    if daily.size == 0:
        return 0.0
    eq=np.cumsum(daily,dtype=float)
    peak=np.maximum.accumulate(np.r_[0.0,eq])[:-1]
    return float(min(0.0,np.min(eq-peak)))


def exact_metrics(delta: np.ndarray, adverse: np.ndarray, exposure: np.ndarray, dates: np.ndarray):
    """Conservative portfolio path.

    delta[t] is realized P&L booked after minute t. adverse[t] is the sum of each
    open sleeve's adverse liquidation P&L inside minute t. This intentionally sums
    each sleeve's adverse extreme even when opposite positions coexist, which is
    conservative on one-minute OHLCV because exact intrabar joint ordering is unknown.
    """
    delta=np.asarray(delta,dtype=float);adverse=np.asarray(adverse,dtype=float)
    realized=np.cumsum(delta)
    before=realized-delta
    peak_before=np.maximum.accumulate(np.r_[0.0,realized[:-1]])
    candidate=before+adverse
    dd_intraday=candidate-peak_before
    peak_after=np.maximum.accumulate(np.r_[0.0,realized]) [1:]
    dd_closed=realized-peak_after
    mdd=float(min(np.min(dd_intraday),np.min(dd_closed))) if len(delta) else 0.0
    nday=len(dates);daily=delta.reshape(nday,390).sum(axis=1)
    worst_day=float(min(0.0,daily.min())) if len(daily) else 0.0
    years=np.array([int(str(d)[:4]) for d in dates],dtype=int)
    out={'net_profit':float(delta.sum()),'max_drawdown':mdd,'worst_day':worst_day,
         'max_exposure_equiv_mnq':int(np.max(exposure)) if len(exposure) else 0}
    out['profit_to_dd']=out['net_profit']/abs(mdd) if mdd<0 else 999.0
    for y in (2023,2024,2025):
        z=years==y
        out[f'net_{y}']=float(daily[z].sum())
        out[f'mdd_daily_{y}']=mdd_from_daily(daily[z])
    return out


def batch_daily_metrics(daily_batch: np.ndarray, years: np.ndarray):
    """Vectorized approximate metrics used only for search pruning."""
    x=np.asarray(daily_batch,dtype=float)
    eq=np.cumsum(x,axis=1)
    peak=np.maximum.accumulate(np.c_[np.zeros(len(x)),eq],axis=1)[:,:-1]
    mdd=np.minimum(0.0,np.min(eq-peak,axis=1))
    net=eq[:,-1]
    ret={'net':net,'mdd':mdd}
    for y in (2023,2024,2025):
        z=years==y
        yy=x[:,z]
        if yy.shape[1]:
            ee=np.cumsum(yy,axis=1);pp=np.maximum.accumulate(np.c_[np.zeros(len(x)),ee],axis=1)[:,:-1]
            ret[f'net_{y}']=ee[:,-1];ret[f'mdd_{y}']=np.minimum(0.0,np.min(ee-pp,axis=1))
        else:
            ret[f'net_{y}']=np.zeros(len(x));ret[f'mdd_{y}']=np.zeros(len(x))
    return ret


def evidence_score(stats: dict) -> float:
    if stats['net_2023']<=0 or stats['net_2024']<=0:
        return -1e99
    p23=stats['net_2023']/max(100.0,abs(stats.get('mdd_2023',stats.get('mdd_daily_2023',0.0))))
    p24=stats['net_2024']/max(100.0,abs(stats.get('mdd_2024',stats.get('mdd_daily_2024',0.0))))
    return float(min(p23,p24)+0.25*(p23+p24))


def credible(stats:dict, meta:dict, objective:dict) -> bool:
    if stats['net_profit'] < objective['min_net_profit'] or stats['max_drawdown'] <= -objective['max_drawdown']:
        return False
    if stats['max_exposure_equiv_mnq'] > objective['max_equivalent_mnq_exposure']:
        return False
    if meta.get('portfolio_trades',0) < objective['credible_min_portfolio_trades']:
        return False
    if meta.get('active_strategies',0) < objective['min_active_strategies']:
        return False
    ys=[]
    for y in (2023,2024,2025):
        if meta.get(f'trades_{y}',0) < objective['credible_min_trades_per_year'] or stats[f'net_{y}']<=0:
            return False
        ys.append(stats[f'net_{y}'])
    if max(ys)/stats['net_profit'] > objective['max_year_profit_share']:
        return False
    if meta.get('max_strategy_profit_share',1.0) > objective['max_single_strategy_profit_share']:
        return False
    return True

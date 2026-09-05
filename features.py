"""Fast causal feature matrix built from Research-4 prepared arrays."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd

DECISION_MINUTES = np.arange(29, 331, 5, dtype=int)  # 09:59 close known -> next bar 10:00 open, through 15:00 entry
HORIZONS = (15, 30, 60)


def _safe_div(a, b):
    return np.divide(a, b, out=np.full(np.broadcast_shapes(np.shape(a), np.shape(b)), np.nan, dtype=float), where=np.isfinite(b) & (np.abs(b) > 1e-12))


def _rolling_same_clock_z(x: np.ndarray, window: int = 20) -> np.ndarray:
    """Prior-day-only z score for each minute column."""
    df = pd.DataFrame(x)
    mu = df.shift(1).rolling(window, min_periods=max(10, window // 2)).mean()
    sd = df.shift(1).rolling(window, min_periods=max(10, window // 2)).std(ddof=0)
    return ((df - mu) / sd.replace(0, np.nan)).to_numpy()


def build(prepared: str | Path):
    p = Path(prepared)
    meta = json.loads((p / 'prepared.json').read_text())
    a = np.load(p / 'rth.npy').astype(np.float64, copy=False)
    night = np.load(p / 'overnight.npy').astype(np.float64, copy=False)
    dates = np.array(meta['dates'])
    normal = np.array(meta['normal_session_mask'], dtype=bool)
    if a.shape[1:] != (390, 5):
        raise ValueError(f'unexpected RTH shape {a.shape}')

    o, h, l, c, v = (a[:, :, i] for i in range(5))
    n = len(a)
    valid_day = normal & np.isfinite(a[:, :389, :]).all(axis=(1, 2))

    # Day-level quantities available from prior sessions only.
    day_hi = np.nanmax(h, axis=1); day_lo = np.nanmin(l, axis=1); day_cl = c[:, -1]
    day_op = o[:, 0]
    prev_close = np.r_[np.nan, day_cl[:-1]]
    prev_open = np.r_[np.nan, day_op[:-1]]
    prev_hi = np.r_[np.nan, day_hi[:-1]]; prev_lo = np.r_[np.nan, day_lo[:-1]]
    prev_ret = np.log(prev_close / prev_open)
    prev_range = prev_hi - prev_lo
    tr = np.maximum(day_hi - day_lo, np.maximum(np.abs(day_hi - np.r_[np.nan, day_cl[:-1]]), np.abs(day_lo - np.r_[np.nan, day_cl[:-1]])))
    atr = pd.Series(tr).shift(1).rolling(14, min_periods=10).mean().to_numpy()

    # Intraday shared arrays.
    logret = np.full_like(c, np.nan)
    logret[:, 1:] = np.log(c[:, 1:] / c[:, :-1])
    cum_abs = np.nancumsum(np.abs(logret), axis=1)
    cum_vol = np.nancumsum(v, axis=1)
    typical = (h + l + c) / 3.0
    cum_money = np.nancumsum(typical * v, axis=1)
    vwap = np.divide(cum_money, cum_vol, out=np.full_like(cum_money, np.nan), where=cum_vol > 0)
    vol_z = _rolling_same_clock_z(cum_vol, 20)

    session_hi = np.maximum.accumulate(h, axis=1)
    session_lo = np.minimum.accumulate(l, axis=1)

    rows = []
    labels = {hz: [] for hz in HORIZONS}
    mfe = {hz: [] for hz in HORIZONS}; mae = {hz: [] for hz in HORIZONS}

    for d in range(n):
        if not valid_day[d] or not np.isfinite(atr[d]) or atr[d] <= 0 or not np.isfinite(prev_close[d]):
            continue
        gap = (day_op[d] - prev_close[d]) / atr[d]
        ov_hi, ov_lo, ov_vwap = night[d]
        ov_range = (ov_hi - ov_lo) / atr[d] if np.isfinite(ov_hi + ov_lo) else np.nan
        ov_vwap_dist = (day_op[d] - ov_vwap) / atr[d] if np.isfinite(ov_vwap) else np.nan
        orb5_hi, orb5_lo = np.nanmax(h[d, :5]), np.nanmin(l[d, :5])
        orb15_hi, orb15_lo = np.nanmax(h[d, :15]), np.nanmin(l[d, :15])
        orb30_hi, orb30_lo = np.nanmax(h[d, :30]), np.nanmin(l[d, :30])
        for m in DECISION_MINUTES:
            if m + max(HORIZONS) >= 390 or not np.isfinite(c[d, m]):
                continue
            px = c[d, m]
            def rback(k):
                return np.log(px / c[d, m-k]) if m >= k and np.isfinite(c[d, m-k]) else np.nan
            def rv(k):
                if m < k: return np.nan
                z = logret[d, m-k+1:m+1]
                return np.sqrt(np.nansum(z*z))
            def rng(k):
                if m < k: return np.nan
                return (np.nanmax(h[d, m-k+1:m+1]) - np.nanmin(l[d, m-k+1:m+1])) / atr[d]
            def efficiency(k):
                if m < k: return np.nan
                net = abs(np.log(px / c[d, m-k]))
                den = np.nansum(np.abs(logret[d, m-k+1:m+1]))
                return net / den if den > 0 else np.nan
            def orpos(hi_, lo_):
                w = hi_ - lo_
                return (px - (hi_ + lo_) / 2) / w if w > 0 else np.nan

            feat = [
                d, m, int(dates[d][:4]),
                prev_ret[d], prev_range[d] / atr[d], gap, ov_range, ov_vwap_dist,
                np.log(px / day_op[d]), rback(5), rback(15), rback(30), rback(60),
                rv(5), rv(15), rv(30), rv(60),
                (px - vwap[d, m]) / atr[d],
                ((vwap[d, m] - vwap[d, m-5]) / atr[d]) if m >= 5 else np.nan,
                ((vwap[d, m] - vwap[d, m-15]) / atr[d]) if m >= 15 else np.nan,
                vol_z[d, m],
                (orb5_hi - orb5_lo) / atr[d], orpos(orb5_hi, orb5_lo),
                (orb15_hi - orb15_lo) / atr[d], orpos(orb15_hi, orb15_lo) if m >= 14 else np.nan,
                (orb30_hi - orb30_lo) / atr[d] if m >= 29 else np.nan,
                orpos(orb30_hi, orb30_lo) if m >= 29 else np.nan,
                (px - session_lo[d, m]) / atr[d], (session_hi[d, m] - px) / atr[d],
                rng(15), rng(30), efficiency(15), efficiency(30),
                (m - 29) / (330 - 29),
            ]
            rows.append(feat)
            for hz in HORIZONS:
                future_close = c[d, m + hz]
                labels[hz].append(np.log(future_close / px))
                hh = np.nanmax(h[d, m+1:m+hz+1]); ll = np.nanmin(l[d, m+1:m+hz+1])
                mfe[hz].append((hh - px) / atr[d]); mae[hz].append((ll - px) / atr[d])

    names = [
        'day_index','minute','year','prev_ret','prev_range_atr','gap_atr','overnight_range_atr','open_vs_overnight_vwap_atr',
        'session_ret','mom5','mom15','mom30','mom60','rv5','rv15','rv30','rv60','vwap_dist_atr','vwap_slope5_atr','vwap_slope15_atr',
        'cum_volume_z','orb5_width_atr','orb5_pos','orb15_width_atr','orb15_pos','orb30_width_atr','orb30_pos',
        'from_session_low_atr','to_session_high_atr','range15_atr','range30_atr','eff15','eff30','time_frac'
    ]
    x = np.asarray(rows, dtype=float)
    out = {'X': x, 'feature_names': names, 'dates': dates, 'rth': a, 'atr': atr}
    for hz in HORIZONS:
        out[f'y{hz}'] = np.asarray(labels[hz], dtype=float)
        out[f'mfe{hz}'] = np.asarray(mfe[hz], dtype=float)
        out[f'mae{hz}'] = np.asarray(mae[hz], dtype=float)
    return out

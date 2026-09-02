from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

HORIZONS = (5, 15, 30, 60)
COST_POINTS = 0.50
MIN_GAP = 5


def load_data(data_dir: Path) -> pd.DataFrame:
    dates = json.loads((data_dir / "dates.json").read_text())
    chunks = []
    for n, d in enumerate(dates, 1):
        p = data_dir / f"{d}.json"
        if not p.exists():
            continue
        rows = json.loads(p.read_text())
        if rows:
            chunks.append(pd.DataFrame(rows, columns=["time","open","high","low","close","volume"]))
        if n % 150 == 0:
            print(f"loaded {n}/{len(dates)} daily files")

    if not chunks:
        raise RuntimeError("No data loaded")

    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["ts_et"] = df["ts_utc"].dt.tz_convert("America/New_York")

    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open","high","low","close"]).reset_index(drop=True)

    # Fixed research window. Partial late-2022 tail is excluded.
    df = df[(df["ts_et"] >= "2023-01-01") & (df["ts_et"] < "2026-01-01")].reset_index(drop=True)

    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14, min_periods=14).mean()

    ret = np.log(df["close"] / prev_close)
    df["rv5"] = ret.rolling(5, min_periods=5).std() * np.sqrt(5)
    df["rv15"] = ret.rolling(15, min_periods=15).std() * np.sqrt(15)

    rng = df["high"] - df["low"]
    df["body_ratio"] = np.where(rng > 0, (df["close"] - df["open"]).abs() / rng, 0.0)
    df["close_loc"] = np.where(rng > 0, (df["close"] - df["low"]) / rng, 0.5)

    df["minute_et"] = (df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).astype(np.int16)
    df["year"] = df["ts_et"].dt.year.astype(np.int16)
    df["date_et"] = df["ts_et"].dt.date
    day_codes, uniques = pd.factorize(df["date_et"], sort=True)
    df["day_id"] = day_codes.astype(np.int16)
    day_year = pd.Series(pd.to_datetime(uniques).year.astype(np.int16))
    df.attrs["day_year"] = day_year.to_numpy()

    # Leak-free seasonal baselines: only prior observations at the same ET minute.
    # 20-occurrence rolling median is enough to capture the U-shaped intraday profile
    # without looking into future days.
    def past_minute_rolling_median(s: pd.Series, window=20):
        return s.shift(1).rolling(window, min_periods=10).median()

    df["seasonal_vol"] = (
        df.groupby("minute_et", group_keys=False)["volume"]
          .apply(past_minute_rolling_median)
          .reset_index(level=0, drop=True)
    )
    df["seasonal_range"] = (
        df.assign(_range=rng)
          .groupby("minute_et", group_keys=False)["_range"]
          .apply(past_minute_rolling_median)
          .reset_index(level=0, drop=True)
    )
    df["relvol"] = df["volume"] / df["seasonal_vol"].replace(0, np.nan)
    df["relrange"] = rng / df["seasonal_range"].replace(0, np.nan)

    return df


def _rolling_past_slot_median(values: pd.Series, slots: pd.Series, window=20) -> pd.Series:
    tmp = pd.DataFrame({"v": values, "slot": slots})
    return (
        tmp.groupby("slot", group_keys=False)["v"]
           .apply(lambda s: s.shift(1).rolling(window, min_periods=10).median())
           .reset_index(level=0, drop=True)
    )


def add_anchor(base: pd.DataFrame, kind: str) -> pd.DataFrame:
    x = pd.DataFrame(index=base.index)
    local = base["ts_et"].dt.tz_localize(None)
    minute = base["minute_et"]

    if kind == "ETH18":
        shifted = local - pd.Timedelta(hours=18)
        key = shifted.dt.date.astype(str)
        slot = ((minute - 18*60) % 1440).astype(np.int16)
        active = np.ones(len(base), dtype=bool)

    elif kind == "MIDNIGHT":
        key = local.dt.date.astype(str)
        slot = minute.astype(np.int16)
        active = np.ones(len(base), dtype=bool)

    elif kind == "RTH":
        # True regular-session VWAP: 09:30 <= t < 16:00 ET, no overnight carry.
        active = ((minute >= 570) & (minute < 960)).to_numpy()
        key = local.dt.date.astype(str)
        slot = (minute - 570).astype(np.int16)

    else:
        raise ValueError(kind)

    x["active"] = active
    x["key"] = key
    x["slot"] = slot

    hlc3 = (base["high"] + base["low"] + base["close"]) / 3.0
    vol = base["volume"].fillna(0).where(active, 0.0)
    pv = (hlc3 * vol).where(active, 0.0)

    cum_pv = pv.groupby(key).cumsum()
    cum_vol = vol.groupby(key).cumsum()
    vwap = cum_pv / cum_vol.replace(0, np.nan)
    if kind == "RTH":
        vwap = vwap.where(active)
    x["vwap"] = vwap

    # Session cumulative volume and leak-free expected cumulative volume at same slot.
    cumv = vol.groupby(key).cumsum()
    cumv = cumv.where(active)
    x["cumvol"] = cumv
    x["cumvol_expected"] = _rolling_past_slot_median(cumv, slot)
    x["cumvol_rel"] = x["cumvol"] / x["cumvol_expected"].replace(0, np.nan)

    close = base["close"]
    atr = base["atr14"].replace(0, np.nan)
    x["dev_atr"] = (close - x["vwap"]) / atr

    for lb in (5, 10, 20):
        prev_vwap = x["vwap"].groupby(key).shift(lb)
        x[f"slope{lb}"] = (x["vwap"] - prev_vwap) / atr

    # Curvature: change in 5-bar VWAP slope.
    x["curve5"] = x["slope5"] - x["slope5"].groupby(key).shift(5)

    above = (close > x["vwap"]).astype(np.int8)
    below = (close < x["vwap"]).astype(np.int8)
    x["above10"] = above.groupby(key).rolling(10, min_periods=10).sum().reset_index(level=0, drop=True)
    x["below10"] = below.groupby(key).rolling(10, min_periods=10).sum().reset_index(level=0, drop=True)

    x["prev_close"] = close.groupby(key).shift(1)
    x["prev_vwap"] = x["vwap"].groupby(key).shift(1)
    x["prev_dev"] = x["dev_atr"].groupby(key).shift(1)
    x["prev_high"] = base["high"].groupby(key).shift(1)
    x["prev_low"] = base["low"].groupby(key).shift(1)

    return x


def add_forward_outcomes(base: pd.DataFrame) -> dict[int, np.ndarray]:
    out = {}
    close = base["close"]
    atr = base["atr14"].replace(0, np.nan)
    for h in HORIZONS:
        out[h] = ((close.shift(-h) - close) / atr).to_numpy(np.float64)
    return out


def time_mask(base: pd.DataFrame, name: str) -> np.ndarray:
    m = base["minute_et"].to_numpy()
    if name == "ALL":
        return np.ones(len(base), dtype=bool)
    if name == "RTH":
        return (m >= 570) & (m < 960)
    if name == "OPEN":
        return (m >= 570) & (m < 660)        # 09:30-11:00
    if name == "MID":
        return (m >= 660) & (m < 840)        # 11:00-14:00
    if name == "PM":
        return (m >= 840) & (m < 960)        # 14:00-16:00
    raise ValueError(name)


def greedy_gap(idx: np.ndarray, min_gap: int) -> np.ndarray:
    if len(idx) == 0:
        return idx
    keep = np.empty(len(idx), dtype=bool)
    keep[:] = False
    last = -10**12
    for k, v in enumerate(idx):
        if v - last > min_gap:
            keep[k] = True
            last = v
    return idx[keep]


def daily_cluster_stats(
    idx: np.ndarray,
    directed_outcome: np.ndarray,
    years: np.ndarray,
    day_ids: np.ndarray,
    day_year: np.ndarray,
    cost_r: np.ndarray,
    target_year: int
) -> dict:
    if len(idx) == 0:
        return dict(events=0, mean_atr=np.nan, net_mean_atr=np.nan, hit_rate=np.nan,
                    daily_t=np.nan, p_one_sided=np.nan, active_days=0)

    sel = idx[years[idx] == target_year]
    if len(sel) == 0:
        return dict(events=0, mean_atr=np.nan, net_mean_atr=np.nan, hit_rate=np.nan,
                    daily_t=np.nan, p_one_sided=np.nan, active_days=0)

    y = directed_outcome[sel]
    c = cost_r[sel]
    valid = np.isfinite(y) & np.isfinite(c)
    sel = sel[valid]
    y = y[valid]
    c = c[valid]
    if len(y) == 0:
        return dict(events=0, mean_atr=np.nan, net_mean_atr=np.nan, hit_rate=np.nan,
                    daily_t=np.nan, p_one_sided=np.nan, active_days=0)

    d = day_ids[sel].astype(np.int64)
    n_days = len(day_year)
    sums = np.bincount(d, weights=y, minlength=n_days)
    counts = np.bincount(d, minlength=n_days)
    day_mask = (counts > 0) & (day_year == target_year)
    daily_means = sums[day_mask] / counts[day_mask]

    if len(daily_means) >= 2 and daily_means.std(ddof=1) > 0:
        t = daily_means.mean() / (daily_means.std(ddof=1) / math.sqrt(len(daily_means)))
    else:
        t = np.nan

    p_one_sided = float(student_t.sf(t, df=len(daily_means)-1)) if np.isfinite(t) and len(daily_means) >= 2 else np.nan
    return dict(
        events=int(len(y)),
        mean_atr=float(y.mean()),
        net_mean_atr=float((y - c).mean()),
        hit_rate=float((y > 0).mean() * 100),
        daily_t=float(t) if np.isfinite(t) else np.nan,
        p_one_sided=float(p_one_sided) if np.isfinite(p_one_sided) else np.nan,
        active_days=int(len(daily_means)),
    )


def build_configs() -> list[dict]:
    cfgs = []
    anchors = ("ETH18","RTH","MIDNIGHT")
    times4 = ("ALL","RTH","OPEN","PM")

    # A) Paper-style VWAP trend state / persistence.
    for a in anchors:
        for tf in times4:
            for persist in (6,7,8,9):
                for slope in (0.0,0.02,0.05,0.10):
                    for rv in (0.0,1.20,1.50):
                        cfgs.append(dict(
                            family="TREND_STATE", anchor=a, time=tf,
                            persist=persist, slope=slope, relvol=rv
                        ))

    # B) Deviation mean reversion under flat/slow VWAP.
    for a in anchors:
        for tf in times4:
            for dev in (0.50,0.75,1.00,1.25,1.50,2.00):
                for slope_max in (0.02,0.05,0.10,999.0):
                    for vr in ("ANY","LOW","HIGH"):
                        cfgs.append(dict(
                            family="DEVIATION_REVERT", anchor=a, time=tf,
                            dev=dev, slope_max=slope_max, vol_regime=vr
                        ))

    # C) Deviation breakout / continuation.
    for a in anchors:
        for tf in times4:
            for dev in (0.25,0.50,0.75,1.00):
                for slope in (0.0,0.03,0.06):
                    for rv in (0.0,1.20,1.50):
                        cfgs.append(dict(
                            family="DEVIATION_BREAKOUT", anchor=a, time=tf,
                            dev=dev, slope=slope, relvol=rv
                        ))

    # D) Abnormal cumulative volume + local volume shock + VWAP trend.
    for a in anchors:
        for tf in times4:
            for cv in (1.10,1.25,1.50):
                for rv in (1.00,1.20,1.50):
                    for slope in (0.0,0.03,0.06):
                        cfgs.append(dict(
                            family="VOLUME_SURPRISE_TREND", anchor=a, time=tf,
                            cumvol_rel=cv, relvol=rv, slope=slope
                        ))

    # E) Dual-anchor alignment.
    for pair in (("ETH18","RTH"),("ETH18","MIDNIGHT"),("RTH","MIDNIGHT")):
        for tf in times4:
            for slope in (0.0,0.03,0.06):
                for devcap in (0.50,1.00,1.50):
                    for rv in (0.0,1.20,1.50):
                        cfgs.append(dict(
                            family="DUAL_ANCHOR", anchor=f"{pair[0]}+{pair[1]}",
                            a1=pair[0], a2=pair[1], time=tf,
                            slope=slope, devcap=devcap, relvol=rv
                        ))

    # F) Pullback/reclaim: acceptance + VWAP touch + directional close.
    for a in anchors:
        for tf in times4:
            for accept in (7,8,9):
                for body in (0.40,0.60):
                    for slope in (0.0,0.03):
                        for rv in (0.0,1.20):
                            cfgs.append(dict(
                                family="PULLBACK_RECLAIM", anchor=a, time=tf,
                                accept=accept, body=body, slope=slope, relvol=rv
                            ))

    for i, c in enumerate(cfgs, 1):
        c["condition_id"] = f"PAPER002_{i:04d}"
    return cfgs


def _relvol_ok(base: pd.DataFrame, threshold: float) -> np.ndarray:
    if threshold <= 0:
        return np.ones(len(base), dtype=bool)
    return (base["relvol"].to_numpy() >= threshold)


def make_signal(base: pd.DataFrame, feat: dict[str,pd.DataFrame], c: dict) -> np.ndarray:
    n = len(base)
    sig = np.zeros(n, dtype=np.int8)
    tf = time_mask(base, c["time"])
    close = base["close"]
    open_ = base["open"]
    high = base["high"]
    low = base["low"]

    if c["family"] == "DUAL_ANCHOR":
        a = feat[c["a1"]]
        b = feat[c["a2"]]
        active = a["active"].to_numpy() & b["active"].to_numpy()
        top = pd.concat([a["vwap"], b["vwap"]], axis=1).max(axis=1)
        bot = pd.concat([a["vwap"], b["vwap"]], axis=1).min(axis=1)
        avg = (a["vwap"] + b["vwap"]) / 2.0
        dev = ((close - avg).abs() / base["atr14"].replace(0,np.nan))
        rvok = _relvol_ok(base, c["relvol"])

        long = (
            (close > top) &
            (a["slope10"] >= c["slope"]) &
            (b["slope10"] >= c["slope"]) &
            (dev <= c["devcap"])
        ).fillna(False).to_numpy() & active & tf & rvok

        short = (
            (close < bot) &
            (a["slope10"] <= -c["slope"]) &
            (b["slope10"] <= -c["slope"]) &
            (dev <= c["devcap"])
        ).fillna(False).to_numpy() & active & tf & rvok

    else:
        f = feat[c["anchor"]]
        active = f["active"].to_numpy()
        vwap = f["vwap"]
        rvok = _relvol_ok(base, c.get("relvol", 0.0))

        if c["family"] == "TREND_STATE":
            long = (
                (f["above10"] >= c["persist"]) &
                (close > vwap) &
                (f["slope10"] >= c["slope"])
            ).fillna(False).to_numpy() & active & tf & rvok
            short = (
                (f["below10"] >= c["persist"]) &
                (close < vwap) &
                (f["slope10"] <= -c["slope"])
            ).fillna(False).to_numpy() & active & tf & rvok

        elif c["family"] == "DEVIATION_REVERT":
            d = f["dev_atr"]
            pdv = f["prev_dev"]
            flat = f["slope10"].abs() <= c["slope_max"]
            if c["vol_regime"] == "ANY":
                vok = np.ones(n, dtype=bool)
            elif c["vol_regime"] == "LOW":
                vok = (base["relvol"].to_numpy() <= 0.80)
            else:
                vok = (base["relvol"].to_numpy() >= 1.20)

            # Enter the event when an extreme deviation begins to revert inward.
            long = (
                (pdv <= -c["dev"]) & (d > -c["dev"]) &
                flat & (close > open_)
            ).fillna(False).to_numpy() & active & tf & vok
            short = (
                (pdv >= c["dev"]) & (d < c["dev"]) &
                flat & (close < open_)
            ).fillna(False).to_numpy() & active & tf & vok

        elif c["family"] == "DEVIATION_BREAKOUT":
            d = f["dev_atr"]
            pdv = f["prev_dev"]
            long = (
                (pdv <= c["dev"]) & (d > c["dev"]) &
                (f["slope10"] >= c["slope"])
            ).fillna(False).to_numpy() & active & tf & rvok
            short = (
                (pdv >= -c["dev"]) & (d < -c["dev"]) &
                (f["slope10"] <= -c["slope"])
            ).fillna(False).to_numpy() & active & tf & rvok

        elif c["family"] == "VOLUME_SURPRISE_TREND":
            cvok = (f["cumvol_rel"] >= c["cumvol_rel"]).fillna(False).to_numpy()
            long = (
                (close > vwap) &
                (f["slope10"] >= c["slope"])
            ).fillna(False).to_numpy() & active & tf & rvok & cvok
            short = (
                (close < vwap) &
                (f["slope10"] <= -c["slope"])
            ).fillna(False).to_numpy() & active & tf & rvok & cvok

        elif c["family"] == "PULLBACK_RECLAIM":
            long = (
                (f["above10"] >= c["accept"]) &
                (low <= vwap) &
                (close > vwap) &
                (close > open_) &
                (base["body_ratio"] >= c["body"]) &
                (close > f["prev_high"]) &
                (f["slope10"] >= c["slope"])
            ).fillna(False).to_numpy() & active & tf & rvok

            short = (
                (f["below10"] >= c["accept"]) &
                (high >= vwap) &
                (close < vwap) &
                (close < open_) &
                (base["body_ratio"] >= c["body"]) &
                (close < f["prev_low"]) &
                (f["slope10"] <= -c["slope"])
            ).fillna(False).to_numpy() & active & tf & rvok

        else:
            raise ValueError(c["family"])

    sig[long] = 1
    sig[short] = -1
    return sig


def evaluate_condition(
    base: pd.DataFrame,
    signal: np.ndarray,
    outcomes: dict[int,np.ndarray],
    cfg: dict
) -> list[dict]:
    raw_idx = np.flatnonzero(signal != 0)
    idx = greedy_gap(raw_idx, MIN_GAP)

    years = base["year"].to_numpy()
    days = base["day_id"].to_numpy()
    day_year = base.attrs["day_year"]
    atr = base["atr14"].to_numpy(np.float64)
    cost_r = COST_POINTS / atr

    rows = []
    for h in HORIZONS:
        directed = outcomes[h] * signal.astype(np.float64)
        row = dict(cfg)
        row["horizon_min"] = h
        row["raw_events"] = int(len(raw_idx))
        row["events_after_gap"] = int(len(idx))

        stats = {}
        for y in (2023,2024,2025):
            s = daily_cluster_stats(idx, directed, years, days, day_year, cost_r, y)
            stats[y] = s
            for k,v in s.items():
                row[f"{k}_{y}"] = v

        # Score is strictly frozen before looking at 2025.
        n23, n24 = stats[2023]["events"], stats[2024]["events"]
        m23, m24 = stats[2023]["mean_atr"], stats[2024]["mean_atr"]
        t23, t24 = stats[2023]["daily_t"], stats[2024]["daily_t"]

        eligible = (
            n23 >= 60 and n24 >= 60 and
            np.isfinite(m23) and np.isfinite(m24) and
            np.isfinite(t23) and np.isfinite(t24)
        )
        if eligible:
            consistency = min(m23, m24)
            t_floor = min(t23, t24)
            sample_weight = min(2.0, math.sqrt(min(n23,n24)/150.0))
            # Positive only when both discovery and validation point the same way.
            row["robust_score"] = consistency * max(0.0, t_floor) * sample_weight
            row["positive_2023_2024"] = bool(m23 > 0 and m24 > 0)
            row["t_positive_2023_2024"] = bool(t23 > 0 and t24 > 0)
        else:
            row["robust_score"] = -999.0
            row["positive_2023_2024"] = False
            row["t_positive_2023_2024"] = False

        rows.append(row)
    return rows



def bh_fdr(pvals: pd.Series) -> pd.Series:
    """Benjamini-Hochberg FDR q-values, preserving original index."""
    p = pd.to_numeric(pvals, errors="coerce")
    out = pd.Series(np.nan, index=p.index, dtype=float)
    valid = p.dropna()
    m = len(valid)
    if m == 0:
        return out
    order = np.argsort(valid.to_numpy())
    ranked = valid.to_numpy()[order]
    q = ranked * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0, 1)
    valid_index = valid.index.to_numpy()[order]
    out.loc[valid_index] = q
    return out


def family_summary(res: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fam, g in res.groupby("family"):
        eligible = g["robust_score"] > -900
        pos = g["positive_2023_2024"] & eligible
        rows.append(dict(
            family=fam,
            condition_horizon_tests=len(g),
            eligible_tests=int(eligible.sum()),
            positive_2023_2024=int(pos.sum()),
            pct_positive_2023_2024=float(100*pos.sum()/max(1,eligible.sum())),
            median_mean_atr_2023=float(g.loc[eligible,"mean_atr_2023"].median()) if eligible.any() else np.nan,
            median_mean_atr_2024=float(g.loc[eligible,"mean_atr_2024"].median()) if eligible.any() else np.nan,
            median_mean_atr_2025_OOS=float(g.loc[eligible,"mean_atr_2025"].median()) if eligible.any() else np.nan,
            best_robust_score=float(g["robust_score"].max()),
        ))
    return pd.DataFrame(rows).sort_values("best_robust_score", ascending=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("vwap_paper_sweep_002_results"))
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    base = load_data(args.data_dir)
    print(f"bars={len(base):,} | {base.ts_et.iloc[0]} -> {base.ts_et.iloc[-1]}")

    feat = {}
    for a in ("ETH18","RTH","MIDNIGHT"):
        print("computing anchor", a)
        feat[a] = add_anchor(base, a)

    outcomes = add_forward_outcomes(base)
    cfgs = build_configs()
    print(f"conditions={len(cfgs):,}; condition-horizon tests={len(cfgs)*len(HORIZONS):,}")

    all_rows = []
    for n,c in enumerate(cfgs,1):
        sig = make_signal(base, feat, c)
        all_rows.extend(evaluate_condition(base, sig, outcomes, c))
        if n % 50 == 0 or n == len(cfgs):
            print(f"evaluated {n}/{len(cfgs)} conditions")

    res = pd.DataFrame(all_rows)

    # Multiple-testing control. We compute BH-FDR q-values separately for discovery
    # and validation, then require both to survive for the strict candidate set.
    res["q_2023"] = bh_fdr(res["p_one_sided_2023"])
    res["q_2024"] = bh_fdr(res["p_one_sided_2024"])
    res["fdr_5pct_both_2023_2024"] = (res["q_2023"] <= 0.05) & (res["q_2024"] <= 0.05)

    res = res.sort_values("robust_score", ascending=False).reset_index(drop=True)
    res.to_csv(args.out_dir / "all_condition_horizon_tests.csv", index=False)

    fam = family_summary(res)
    fam.to_csv(args.out_dir / "family_summary.csv", index=False)

    # Pre-OOS frozen leaderboard.
    eligible = res[
        (res["robust_score"] > -900) &
        (res["positive_2023_2024"]) &
        (res["t_positive_2023_2024"])
    ].copy()

    strict_fdr = eligible[eligible["fdr_5pct_both_2023_2024"]].copy()
    strict_fdr.to_csv(args.out_dir / "strict_fdr_5pct_2023_2024.csv", index=False)
    eligible.to_csv(args.out_dir / "validated_2023_2024.csv", index=False)
    top100 = eligible.head(100).copy()
    top100.to_csv(args.out_dir / "top100_frozen_before_2025.csv", index=False)

    # 2025 is reported only after ranking is frozen.
    oos_positive = int((top100["mean_atr_2025"] > 0).sum()) if len(top100) else 0
    oos_net_positive = int((top100["net_mean_atr_2025"] > 0).sum()) if len(top100) else 0
    oos_t_positive = int((top100["daily_t_2025"] > 0).sum()) if len(top100) else 0

    cols = [
        "condition_id","family","anchor","time","horizon_min","robust_score",
        "events_2023","mean_atr_2023","daily_t_2023","q_2023",
        "events_2024","mean_atr_2024","daily_t_2024","q_2024",
        "events_2025","mean_atr_2025","net_mean_atr_2025","daily_t_2025"
    ]
    cols = [c for c in cols if c in top100.columns]

    md = []
    md.append("# VWAP Paper-Inspired Research Sweep 002")
    md.append("")
    md.append(f"- Bars: **{len(base):,}**")
    md.append(f"- Conditions: **{len(cfgs):,}**")
    md.append(f"- Forward horizons per condition: **{len(HORIZONS)}** ({', '.join(map(str,HORIZONS))} min)")
    md.append(f"- Total condition-horizon tests: **{len(res):,}**")
    md.append("- Research design: **event study**, not forced SL/TP trading.")
    md.append("- Signal separation: at least **5 minutes** between retained events.")
    md.append("- Returns normalized by contemporaneous **ATR(14)**.")
    md.append("- Daily-clustered t-statistic: events are averaged within each day before the t-test.")
    md.append("- Multiple testing: **Benjamini-Hochberg FDR q-values** computed across all condition/horizon tests for 2023 and 2024.")
    md.append(f"- Cost stress: **{COST_POINTS:.2f} NQ points** round trip, reported as ATR-normalized net forward return.")
    md.append("- 2023 = discovery; 2024 = validation; **2025 never enters the ranking score**.")
    md.append("")
    md.append("## Families")
    md.append("")
    md.append("1. Paper-style VWAP trend state / persistence")
    md.append("2. VWAP deviation mean reversion")
    md.append("3. VWAP deviation breakout / continuation")
    md.append("4. Dynamic cumulative-volume surprise + VWAP trend")
    md.append("5. Dual-anchor VWAP alignment")
    md.append("6. Pullback/reclaim with acceptance, slope and relative-volume filters")
    md.append("")
    md.append("## Family-level results")
    md.append("")
    md.append(fam.to_markdown(index=False))
    md.append("")
    md.append(f"- Tests surviving 5% FDR in BOTH 2023 and 2024: **{len(strict_fdr)}**")
    md.append("")
    md.append("## Frozen top 100 (ranked using only 2023 + 2024)")
    md.append("")
    if len(top100):
        md.append(top100[cols].head(30).to_markdown(index=False))
    else:
        md.append("No tests passed the 2023/2024 eligibility and sign-consistency gates.")
    md.append("")
    md.append("## Untouched 2025 check on the frozen top 100")
    md.append("")
    md.append(f"- Positive gross forward expectancy in 2025: **{oos_positive}/{len(top100)}**")
    md.append(f"- Positive after 0.50-point cost stress in 2025: **{oos_net_positive}/{len(top100)}**")
    md.append(f"- Positive daily-clustered t-stat in 2025: **{oos_t_positive}/{len(top100)}**")
    md.append("")
    md.append("This is a factor-discovery screen. Any survivor still needs a dedicated execution backtest, "
              "parameter-neighborhood checks, multiple-testing controls, and longer data before being treated as tradable alpha.")

    (args.out_dir / "summary.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()

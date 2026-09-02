from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

COST_DEFAULT = 0.50
HORIZON_DEFAULT = 60


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
        raise RuntimeError("No bars loaded")

    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["ts_et"] = df["ts_utc"].dt.tz_convert("America/New_York")
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open","high","low","close"]).reset_index(drop=True)

    # We intentionally exclude the partial 2022 tail from model discovery.
    df = df[(df["ts_et"] >= "2023-01-01") & (df["ts_et"] < "2026-01-01")].reset_index(drop=True)

    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14, min_periods=14).mean()
    rng = df["high"] - df["low"]
    df["body_ratio"] = np.where(rng > 0, (df["close"] - df["open"]).abs() / rng, 0.0)
    df["close_loc"] = np.where(rng > 0, (df["close"] - df["low"]) / rng, 0.5)
    df["vol_med20"] = df["volume"].rolling(20, min_periods=20).median()
    df["vol_ratio"] = df["volume"] / df["vol_med20"].replace(0, np.nan)
    df["minute_et"] = df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute
    df["year"] = df["ts_et"].dt.year.astype(np.int16)
    return df


def add_anchor_features(base: pd.DataFrame, reset_minute: int) -> pd.DataFrame:
    x = pd.DataFrame(index=base.index)
    local = base["ts_et"].dt.tz_localize(None)
    shifted = local - pd.to_timedelta(reset_minute, unit="m")
    key = shifted.dt.date.astype(str)
    x["session_key"] = key

    hlc3 = (base["high"] + base["low"] + base["close"]) / 3.0
    pv = hlc3 * base["volume"].fillna(0)
    cum_pv = pv.groupby(key).cumsum()
    cum_vol = base["volume"].fillna(0).groupby(key).cumsum()
    x["vwap"] = cum_pv / cum_vol.replace(0, np.nan)
    x["vwap"] = x.groupby("session_key")["vwap"].ffill()

    above = (base["close"] > x["vwap"]).astype(np.int8)
    below = (base["close"] < x["vwap"]).astype(np.int8)
    x["above10"] = above.groupby(key).rolling(10, min_periods=10).sum().reset_index(level=0, drop=True)
    x["below10"] = below.groupby(key).rolling(10, min_periods=10).sum().reset_index(level=0, drop=True)
    x["above10_prev"] = x.groupby("session_key")["above10"].shift(1)
    x["below10_prev"] = x.groupby("session_key")["below10"].shift(1)

    for lb in (5, 10, 20):
        prev_vwap = x.groupby("session_key")["vwap"].shift(lb)
        x[f"slope{lb}"] = (x["vwap"] - prev_vwap) / base["atr14"].replace(0, np.nan)

    x["dev_atr"] = (base["close"] - x["vwap"]) / base["atr14"].replace(0, np.nan)
    x["prev_vwap"] = x.groupby("session_key")["vwap"].shift(1)
    x["prev_dev_atr"] = x.groupby("session_key")["dev_atr"].shift(1)
    x["prev_close"] = base["close"].groupby(key).shift(1)
    x["prev_high"] = base["high"].groupby(key).shift(1)
    x["prev_low"] = base["low"].groupby(key).shift(1)
    return x


def time_mask(base: pd.DataFrame, name: str) -> np.ndarray:
    m = base["minute_et"].to_numpy()
    if name == "ALL":
        return np.ones(len(base), dtype=np.bool_)
    if name == "RTH":
        return (m >= 570) & (m < 960)       # 09:30-16:00 ET
    if name == "OPEN":
        return (m >= 570) & (m < 660)       # 09:30-11:00 ET
    raise ValueError(name)


@njit(cache=True)
def evaluate_signals(signal, open_, high, low, close, atr, years, cost_points, horizon):
    entry_idx_l = []
    exit_idx_l = []
    dir_l = []
    gross_r_l = []
    net_r_l = []
    bars_l = []
    reason_l = []

    n = len(signal)
    last_exit = -1
    i = 0

    while i < n - 1:
        d = int(signal[i])
        if d == 0 or i <= last_exit or np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue

        e = i + 1
        entry = open_[e]
        risk = atr[i]
        if np.isnan(entry) or risk <= 0:
            i += 1
            continue

        if d == 1:
            stop = entry - risk
            target = entry + risk
        else:
            stop = entry + risk
            target = entry - risk

        end = min(n - 1, e + horizon - 1)
        exit_idx = end
        exit_px = close[end]
        reason = 0  # timeout

        j = e
        while j <= end:
            if d == 1:
                if open_[j] <= stop:
                    exit_px = open_[j]
                    exit_idx = j
                    reason = -2
                    break
                stop_hit = low[j] <= stop
                target_hit = high[j] >= target
                if stop_hit:  # conservative same-bar ambiguity
                    exit_px = stop
                    exit_idx = j
                    reason = -1
                    break
                if target_hit:
                    exit_px = target
                    exit_idx = j
                    reason = 1
                    break
            else:
                if open_[j] >= stop:
                    exit_px = open_[j]
                    exit_idx = j
                    reason = -2
                    break
                stop_hit = high[j] >= stop
                target_hit = low[j] <= target
                if stop_hit:
                    exit_px = stop
                    exit_idx = j
                    reason = -1
                    break
                if target_hit:
                    exit_px = target
                    exit_idx = j
                    reason = 1
                    break
            j += 1

        gross_pts = (exit_px - entry) * d
        gross_r = gross_pts / risk
        net_r = (gross_pts - cost_points) / risk

        entry_idx_l.append(e)
        exit_idx_l.append(exit_idx)
        dir_l.append(d)
        gross_r_l.append(gross_r)
        net_r_l.append(net_r)
        bars_l.append(exit_idx - e + 1)
        reason_l.append(reason)

        last_exit = exit_idx
        i = exit_idx + 1

    return (
        np.array(entry_idx_l, dtype=np.int64),
        np.array(exit_idx_l, dtype=np.int64),
        np.array(dir_l, dtype=np.int8),
        np.array(gross_r_l, dtype=np.float64),
        np.array(net_r_l, dtype=np.float64),
        np.array(bars_l, dtype=np.int32),
        np.array(reason_l, dtype=np.int8),
    )


def metrics(net_r: np.ndarray, gross_r: np.ndarray, reasons: np.ndarray) -> dict:
    if len(net_r) == 0:
        return {
            "trades": 0, "win_rate": np.nan, "expectancy": np.nan,
            "pf": np.nan, "net_r_total": 0.0, "max_dd": np.nan,
            "timeout_pct": np.nan
        }
    wins = net_r > 0
    pos = net_r[wins].sum()
    neg = -net_r[~wins].sum()
    eq = np.cumsum(net_r)
    peak = np.maximum.accumulate(np.concatenate(([0.0], eq)))[1:]
    dd = eq - peak
    return {
        "trades": int(len(net_r)),
        "win_rate": float(wins.mean() * 100),
        "expectancy": float(net_r.mean()),
        "gross_expectancy": float(gross_r.mean()),
        "pf": float(pos / neg) if neg > 0 else np.nan,
        "net_r_total": float(net_r.sum()),
        "max_dd": float(dd.min()) if len(dd) else 0.0,
        "timeout_pct": float((reasons == 0).mean() * 100),
    }


def build_variants():
    variants = []
    anchors = ["ETH18", "ANCHOR0930"]
    times2 = ["ALL", "RTH"]
    times3 = ["ALL", "RTH", "OPEN"]

    # 1) Price crosses/reclaims VWAP with optional slope + volume confirmation.
    for a in anchors:
        for slope in [0.0, 0.03, 0.06]:
            for vr in [0.0, 1.2]:
                for tf in times3:
                    variants.append(dict(family="CROSS_RECLAIM", anchor=a, time=tf, slope=slope, vol=vr))

    # 2) Trend acceptance then one-bar VWAP pullback/rejection.
    for a in anchors:
        for accept in [7, 8, 9]:
            for body in [0.50, 0.65]:
                for tol in [0.0, 0.10]:  # ATR units above/below VWAP allowed for touch
                    for slope in [0.0, 0.04]:
                        for tf in times2:
                            variants.append(dict(
                                family="PULLBACK_REJECTION", anchor=a, time=tf,
                                accept=accept, body=body, tol=tol, slope=slope
                            ))

    # 3) ATR-normalized deviation mean reversion: move outside band then re-enter.
    for a in anchors:
        for thr in [0.75, 1.0, 1.25, 1.50, 2.0]:
            for slope_max in [0.05, 0.10, 999.0]:
                for tf in times2:
                    variants.append(dict(
                        family="DEVIATION_MEAN_REVERT", anchor=a, time=tf,
                        threshold=thr, slope_max=slope_max
                    ))

    # 4) ATR-normalized deviation breakout with slope and volume confirmation.
    for a in anchors:
        for thr in [0.50, 0.75, 1.0, 1.25]:
            for slope in [0.0, 0.03, 0.06]:
                for vr in [0.0, 1.2]:
                    for tf in times2:
                        variants.append(dict(
                            family="DEVIATION_BREAKOUT", anchor=a, time=tf,
                            threshold=thr, slope=slope, vol=vr
                        ))

    # 5) VWAP slope momentum: slope crosses a threshold while price agrees.
    for a in anchors:
        for lb in [5, 10, 20]:
            for slope in [0.03, 0.06, 0.10]:
                for vr in [0.0, 1.2]:
                    for tf in times2:
                        variants.append(dict(
                            family="VWAP_SLOPE_MOMENTUM", anchor=a, time=tf,
                            lookback=lb, slope=slope, vol=vr
                        ))

    # 6) ETH + 09:30 VWAP alignment.
    for slope in [0.0, 0.03, 0.06]:
        for devcap in [0.5, 1.0, 1.5]:
            for vr in [0.0, 1.2]:
                for tf in times2:
                    variants.append(dict(
                        family="DUAL_ANCHOR_ALIGNMENT", anchor="DUAL", time=tf,
                        slope=slope, devcap=devcap, vol=vr
                    ))

    for i, v in enumerate(variants, 1):
        v["variant_id"] = f"VWAP_{i:04d}"
    return variants


def make_signal(base: pd.DataFrame, feats: dict[str, pd.DataFrame], cfg: dict) -> np.ndarray:
    tf = time_mask(base, cfg["time"])
    close = base["close"]
    open_ = base["open"]
    atr = base["atr14"]
    vr = base["vol_ratio"].fillna(0)
    body = base["body_ratio"]

    sig = np.zeros(len(base), dtype=np.int8)

    if cfg["family"] == "DUAL_ANCHOR_ALIGNMENT":
        e = feats["ETH18"]
        r = feats["ANCHOR0930"]
        top = pd.concat([e["vwap"], r["vwap"]], axis=1).max(axis=1)
        bot = pd.concat([e["vwap"], r["vwap"]], axis=1).min(axis=1)
        prev_top = top.shift(1)
        prev_bot = bot.shift(1)
        avg_v = (e["vwap"] + r["vwap"]) / 2.0
        dev = (close - avg_v).abs() / atr.replace(0, np.nan)
        vol_ok = np.ones(len(base), dtype=bool) if cfg["vol"] == 0 else (vr >= cfg["vol"]).to_numpy()
        long = (
            (close > top) & (close.shift(1) <= prev_top) &
            (e["slope10"] >= cfg["slope"]) & (r["slope10"] >= cfg["slope"]) &
            (dev <= cfg["devcap"])
        ).fillna(False).to_numpy() & vol_ok & tf
        short = (
            (close < bot) & (close.shift(1) >= prev_bot) &
            (e["slope10"] <= -cfg["slope"]) & (r["slope10"] <= -cfg["slope"]) &
            (dev <= cfg["devcap"])
        ).fillna(False).to_numpy() & vol_ok & tf
        sig[long] = 1
        sig[short] = -1
        return sig

    f = feats[cfg["anchor"]]
    vwap = f["vwap"]

    if cfg["family"] == "CROSS_RECLAIM":
        vol_ok = np.ones(len(base), dtype=bool) if cfg["vol"] == 0 else (vr >= cfg["vol"]).to_numpy()
        long = (
            (close > vwap) & (f["prev_close"] <= f["prev_vwap"]) &
            (f["slope10"] >= cfg["slope"])
        ).fillna(False).to_numpy() & vol_ok & tf
        short = (
            (close < vwap) & (f["prev_close"] >= f["prev_vwap"]) &
            (f["slope10"] <= -cfg["slope"])
        ).fillna(False).to_numpy() & vol_ok & tf

    elif cfg["family"] == "PULLBACK_REJECTION":
        tol_pts = atr * cfg["tol"]
        long = (
            (f["above10_prev"] >= cfg["accept"]) &
            (base["low"] <= vwap + tol_pts) &
            (close > vwap) &
            (close > open_) &
            (body >= cfg["body"]) &
            (close > f["prev_high"]) &
            (f["slope10"] >= cfg["slope"])
        ).fillna(False).to_numpy() & tf
        short = (
            (f["below10_prev"] >= cfg["accept"]) &
            (base["high"] >= vwap - tol_pts) &
            (close < vwap) &
            (close < open_) &
            (body >= cfg["body"]) &
            (close < f["prev_low"]) &
            (f["slope10"] <= -cfg["slope"])
        ).fillna(False).to_numpy() & tf

    elif cfg["family"] == "DEVIATION_MEAN_REVERT":
        d = f["dev_atr"]
        pdv = f["prev_dev_atr"]
        flat = f["slope10"].abs() <= cfg["slope_max"]
        long = (
            (pdv <= -cfg["threshold"]) & (d > -cfg["threshold"]) &
            flat & (close > open_)
        ).fillna(False).to_numpy() & tf
        short = (
            (pdv >= cfg["threshold"]) & (d < cfg["threshold"]) &
            flat & (close < open_)
        ).fillna(False).to_numpy() & tf

    elif cfg["family"] == "DEVIATION_BREAKOUT":
        d = f["dev_atr"]
        pdv = f["prev_dev_atr"]
        vol_ok = np.ones(len(base), dtype=bool) if cfg["vol"] == 0 else (vr >= cfg["vol"]).to_numpy()
        long = (
            (pdv <= cfg["threshold"]) & (d > cfg["threshold"]) &
            (f["slope10"] >= cfg["slope"])
        ).fillna(False).to_numpy() & vol_ok & tf
        short = (
            (pdv >= -cfg["threshold"]) & (d < -cfg["threshold"]) &
            (f["slope10"] <= -cfg["slope"])
        ).fillna(False).to_numpy() & vol_ok & tf

    elif cfg["family"] == "VWAP_SLOPE_MOMENTUM":
        s = f[f"slope{cfg['lookback']}"]
        ps = s.groupby(f["session_key"]).shift(1)
        vol_ok = np.ones(len(base), dtype=bool) if cfg["vol"] == 0 else (vr >= cfg["vol"]).to_numpy()
        long = (
            (ps <= cfg["slope"]) & (s > cfg["slope"]) & (close > vwap)
        ).fillna(False).to_numpy() & vol_ok & tf
        short = (
            (ps >= -cfg["slope"]) & (s < -cfg["slope"]) & (close < vwap)
        ).fillna(False).to_numpy() & vol_ok & tf

    else:
        raise ValueError(cfg["family"])

    sig[long] = 1
    sig[short] = -1
    return sig


def summarize_period(entry_idx, gross_r, net_r, reasons, base_years, year):
    mask = base_years[entry_idx] == year
    return metrics(net_r[mask], gross_r[mask], reasons[mask])


def row_from_result(cfg, entry_idx, gross_r, net_r, reasons, base_years):
    row = dict(cfg)
    per = {}
    for y in (2023, 2024, 2025):
        m = summarize_period(entry_idx, gross_r, net_r, reasons, base_years, y)
        per[y] = m
        for k, v in m.items():
            row[f"{k}_{y}"] = v

    n23, n24 = per[2023]["trades"], per[2024]["trades"]
    e23, e24 = per[2023]["expectancy"], per[2024]["expectancy"]

    eligible = (
        n23 >= 40 and n24 >= 40 and
        np.isfinite(e23) and np.isfinite(e24)
    )
    if eligible:
        sample_weight = min(2.0, math.sqrt(min(n23, n24) / 100.0))
        # Ranking uses ONLY 2023 + 2024. 2025 is never part of the score.
        row["robust_score"] = min(e23, e24) * sample_weight
        row["positive_2023_2024"] = bool(e23 > 0 and e24 > 0)
    else:
        row["robust_score"] = -999.0
        row["positive_2023_2024"] = False

    return row


def family_summary(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fam, g in results.groupby("family"):
        rows.append({
            "family": fam,
            "variants": len(g),
            "eligible_variants": int((g["robust_score"] > -900).sum()),
            "positive_both_2023_2024": int(g["positive_2023_2024"].sum()),
            "pct_positive_both_2023_2024": 100 * g["positive_2023_2024"].mean(),
            "median_expectancy_2023": g["expectancy_2023"].median(),
            "median_expectancy_2024": g["expectancy_2024"].median(),
            "median_expectancy_2025_OOS": g["expectancy_2025"].median(),
            "best_robust_score": g["robust_score"].max(),
        })
    return pd.DataFrame(rows).sort_values("best_robust_score", ascending=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("vwap_sweep_results"))
    ap.add_argument("--cost-points", type=float, default=COST_DEFAULT)
    ap.add_argument("--horizon", type=int, default=HORIZON_DEFAULT)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    base = load_data(args.data_dir)
    print(f"bars={len(base):,} {base.ts_et.iloc[0]} -> {base.ts_et.iloc[-1]}")

    feats = {
        "ETH18": add_anchor_features(base, 18 * 60),
        "ANCHOR0930": add_anchor_features(base, 9 * 60 + 30),
    }

    variants = build_variants()
    print(f"variants={len(variants)}")

    open_a = base["open"].to_numpy(np.float64)
    high_a = base["high"].to_numpy(np.float64)
    low_a = base["low"].to_numpy(np.float64)
    close_a = base["close"].to_numpy(np.float64)
    atr_a = base["atr14"].to_numpy(np.float64)
    years_a = base["year"].to_numpy(np.int16)

    # Warm numba once before sweep timing matters.
    dummy = np.zeros(len(base), dtype=np.int8)
    evaluate_signals(dummy[:100], open_a[:100], high_a[:100], low_a[:100],
                     close_a[:100], atr_a[:100], years_a[:100],
                     args.cost_points, args.horizon)

    rows = []
    for n, cfg in enumerate(variants, 1):
        sig = make_signal(base, feats, cfg)
        entry_idx, exit_idx, dirs, gross_r, net_r, bars, reasons = evaluate_signals(
            sig, open_a, high_a, low_a, close_a, atr_a, years_a,
            args.cost_points, args.horizon
        )
        rows.append(row_from_result(cfg, entry_idx, gross_r, net_r, reasons, years_a))
        if n % 25 == 0 or n == len(variants):
            print(f"tested {n}/{len(variants)}")

    res = pd.DataFrame(rows)
    res = res.sort_values("robust_score", ascending=False).reset_index(drop=True)
    res.to_csv(args.out_dir / "all_variants.csv", index=False)

    fam = family_summary(res)
    fam.to_csv(args.out_dir / "family_summary.csv", index=False)

    candidates = res[
        (res["positive_2023_2024"]) &
        (res["trades_2023"] >= 40) &
        (res["trades_2024"] >= 40)
    ].copy()
    candidates.to_csv(args.out_dir / "candidates_positive_2023_2024.csv", index=False)

    top = res.head(50).copy()
    top.to_csv(args.out_dir / "top50_ranked_without_2025.csv", index=False)

    # Once the ranking is frozen, report how those pre-selected candidates behaved in 2025.
    top20 = res.head(20)
    oos_positive = int((top20["expectancy_2025"] > 0).sum())
    oos_median = float(top20["expectancy_2025"].median()) if len(top20) else np.nan

    md = []
    md.append("# VWAP Research Sweep 001")
    md.append("")
    md.append(f"- Bars: **{len(base):,}**")
    md.append(f"- Variants tested: **{len(res)}**")
    md.append(f"- Entry: **next 1-minute open**")
    md.append(f"- Risk/target: **1 ATR(14) stop / 1R target**")
    md.append(f"- Timeout: **{args.horizon} minutes**")
    md.append(f"- Friction: **{args.cost_points:.2f} NQ points round trip**")
    md.append("- Discovery: **2023**")
    md.append("- Validation: **2024**")
    md.append("- Final OOS: **2025**")
    md.append("- **2025 is not used anywhere in the ranking score.**")
    md.append("")
    md.append("## Family-level stability")
    md.append("")
    md.append(fam.to_markdown(index=False))
    md.append("")
    md.append("## Top 20 ranked using only 2023 + 2024")
    md.append("")
    cols = [
        "variant_id","family","anchor","time","robust_score",
        "trades_2023","expectancy_2023","trades_2024","expectancy_2024",
        "trades_2025","expectancy_2025","pf_2025"
    ]
    md.append(top20[cols].to_markdown(index=False))
    md.append("")
    md.append("## Frozen-selection 2025 check")
    md.append("")
    md.append(f"- Top-20 candidates positive in 2025: **{oos_positive}/{len(top20)}**")
    md.append(f"- Median 2025 expectancy among the frozen top 20: **{oos_median:.4f}R/trade**")
    md.append("")
    md.append("Important: this is a broad factor screen, not a final tradable strategy. "
              "We should look for families/parameter neighborhoods that remain stable, then run a dedicated trade-level backtest on finalists.")

    (args.out_dir / "summary.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import math
import random
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

ET = "America/New_York"
SEED = 20260903
rng = np.random.default_rng(SEED)
random.seed(SEED)

HORIZONS = (5, 15, 30, 60)
COSTS = (0.5, 1.0, 2.0, 3.0)
MIN_EVENTS = 80
GAP = {5: 5, 15: 15, 30: 30, 60: 60}

# Large staged search. The first stage is deliberately approximate and cheap;
# every survivor is then re-run on the full sequential data.
RANDOM_RULES = 220_000
EVOLUTION_POP = 3000
EVOLUTION_GENS = 16
EVOLUTION_ELITE = 250
FULL_RECHECK = 3500
BOOTSTRAP_TOP = 120
EXECUTION_TOP = 60
DISCOVERY_SCREEN_ROWS = 20_000

# LucidPro-style reference wrapper used only AFTER alpha search.
START_BALANCE = 50_000.0
PROFIT_TARGET = 3_000.0
MAX_LOSS = 2_000.0
LOCKED_MLL = 50_100.0
MAX_NQ = 4
MAX_MNQ = 40
NQ_POINT = 20.0
MNQ_POINT = 2.0
NQ_RT_COMMISSION = 3.50
MNQ_RT_COMMISSION = 1.00
PROP_SLIPPAGE_RT_POINTS = 1.0
RISK_PROFILES = [
    ("VERY_CONSERVATIVE", 50, 200),
    ("CONSERVATIVE", 75, 300),
    ("BALANCED", 100, 400),
    ("BALANCED_PLUS", 125, 500),
    ("AGGRESSIVE", 150, 600),
    ("AGGRESSIVE_PLUS", 175, 700),
    ("HIGH_AGGRESSION", 200, 800),
    ("STRESS_TEST", 250, 1000),
]


def load_data(data_dir: Path) -> pd.DataFrame:
    dates = json.loads((data_dir / "dates.json").read_text())
    chunks = []
    for n, d in enumerate(dates, 1):
        p = data_dir / f"{d}.json"
        if p.exists():
            rows = json.loads(p.read_text())
            if rows:
                chunks.append(pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]))
        if n % 150 == 0:
            print(f"loaded {n}/{len(dates)} files")
    if not chunks:
        raise RuntimeError("No NQ bars found")
    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["ts_et"] = df["ts_utc"].dt.tz_convert(ET)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    df = df[(df["ts_et"] >= "2022-12-26") & (df["ts_et"] < "2026-01-01")].reset_index(drop=True)
    df["date_et"] = df["ts_et"].dt.date
    df["year"] = df["ts_et"].dt.year.astype(int)
    df["minute_et"] = (df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).astype(int)
    return df


def rolling_z(s: pd.Series, w: int) -> pd.Series:
    m = s.rolling(w, min_periods=max(8, w // 3)).mean()
    sd = s.rolling(w, min_periods=max(8, w // 3)).std(ddof=0)
    return (s - m) / sd.replace(0, np.nan)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    prev = x["close"].shift(1)
    tr = pd.concat([
        x["high"] - x["low"],
        (x["high"] - prev).abs(),
        (x["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    x["atr14"] = tr.rolling(14, min_periods=14).mean()
    x["atr50"] = tr.rolling(50, min_periods=20).mean()
    x["atr_ratio"] = x["atr14"] / x["atr50"].replace(0, np.nan)

    hlc3 = (x["high"] + x["low"] + x["close"]) / 3.0
    local = x["ts_et"].dt.tz_localize(None)
    rth = (x["minute_et"] >= 570) & (x["minute_et"] < 960)
    rth_key = local.dt.date.astype(str)
    rvol = x["volume"].where(rth, 0.0)
    rpv = (hlc3 * rvol).where(rth, 0.0)
    x["vwap_rth"] = (rpv.groupby(rth_key).cumsum() / rvol.groupby(rth_key).cumsum().replace(0, np.nan)).where(rth)

    eth_key = (local - pd.Timedelta(hours=18)).dt.date.astype(str)
    x["vwap_eth"] = (hlc3 * x["volume"]).groupby(eth_key).cumsum() / x["volume"].groupby(eth_key).cumsum().replace(0, np.nan)
    mid_key = local.dt.date.astype(str)
    x["vwap_mid"] = (hlc3 * x["volume"]).groupby(mid_key).cumsum() / x["volume"].groupby(mid_key).cumsum().replace(0, np.nan)

    for h in [1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240]:
        x[f"ret_{h}"] = x["close"] / x["close"].shift(h) - 1.0
        x[f"chg_atr_{h}"] = (x["close"] - x["close"].shift(h)) / x["atr14"].replace(0, np.nan)

    lr = np.log(x["close"] / x["close"].shift(1))
    for h in [5, 10, 15, 30, 60, 120]:
        x[f"rv_{h}"] = lr.rolling(h, min_periods=max(3, h // 3)).std(ddof=0) * np.sqrt(h)
        x[f"range_{h}_atr"] = (x["high"].rolling(h).max() - x["low"].rolling(h).min()) / x["atr14"].replace(0, np.nan)

    br = (x["high"] - x["low"]).replace(0, np.nan)
    x["body_frac"] = (x["close"] - x["open"]) / br
    x["close_loc"] = (x["close"] - x["low"]) / br
    x["bar_range_atr"] = (x["high"] - x["low"]) / x["atr14"].replace(0, np.nan)
    x["upper_wick"] = (x["high"] - x[["open", "close"]].max(axis=1)) / br
    x["lower_wick"] = (x[["open", "close"]].min(axis=1) - x["low"]) / br

    for name in ["rth", "eth", "mid"]:
        v = x[f"vwap_{name}"]
        x[f"dev_{name}_atr"] = (x["close"] - v) / x["atr14"].replace(0, np.nan)
        x[f"above_{name}"] = (x["close"] > v).astype(float)
        for h in [3, 5, 10, 20, 30, 60]:
            x[f"slope_{name}_{h}"] = (v - v.shift(h)) / x["atr14"].replace(0, np.nan)
        for h in [5, 10, 20, 30, 60]:
            x[f"persist_{name}_{h}"] = x[f"above_{name}"].rolling(h, min_periods=h).mean()

    x["dual_rth_eth"] = x["above_rth"] + x["above_eth"] - 1.0
    x["dual_rth_mid"] = x["above_rth"] + x["above_mid"] - 1.0

    for h in [10, 20, 50, 100, 200]:
        x[f"vol_z_{h}"] = rolling_z(x["volume"], h)
        x[f"vol_rel_{h}"] = x["volume"] / x["volume"].rolling(h, min_periods=max(5, h // 3)).median().replace(0, np.nan)

    # Leak-free intraday seasonal volume: same minute of day, prior observations only.
    seasonal = np.full(len(x), np.nan)
    for _, idx in x.groupby("minute_et").groups.items():
        ii = np.asarray(list(idx), dtype=int)
        vals = x.loc[ii, "volume"].astype(float)
        med = vals.shift(1).rolling(20, min_periods=8).median()
        seasonal[ii] = med.to_numpy()
    x["vol_seasonal_rel"] = x["volume"] / pd.Series(seasonal, index=x.index).replace(0, np.nan)
    x["vol_seasonal_z"] = rolling_z(x["vol_seasonal_rel"], 100)

    daily = x.groupby("date_et").agg(day_open=("open", "first"), day_high=("high", "max"), day_low=("low", "min"), day_close=("close", "last"))
    daily["prev_high"] = daily["day_high"].shift(1)
    daily["prev_low"] = daily["day_low"].shift(1)
    daily["prev_close"] = daily["day_close"].shift(1)
    x["prev_high"] = x["date_et"].map(daily["prev_high"])
    x["prev_low"] = x["date_et"].map(daily["prev_low"])
    x["prev_close"] = x["date_et"].map(daily["prev_close"])
    x["dist_prev_high_atr"] = (x["close"] - x["prev_high"]) / x["atr14"].replace(0, np.nan)
    x["dist_prev_low_atr"] = (x["close"] - x["prev_low"]) / x["atr14"].replace(0, np.nan)

    rth_df = x[rth]
    op = rth_df.groupby("date_et")["open"].first()
    x["rth_open"] = x["date_et"].map(op)
    x["from_rth_open_atr"] = (x["close"] - x["rth_open"]) / x["atr14"].replace(0, np.nan)
    orb = rth_df[(rth_df["minute_et"] >= 570) & (rth_df["minute_et"] < 585)].groupby("date_et").agg(hi=("high", "max"), lo=("low", "min"))
    x["orb_hi"] = x["date_et"].map(orb["hi"])
    x["orb_lo"] = x["date_et"].map(orb["lo"])
    x["dist_orb_hi_atr"] = (x["close"] - x["orb_hi"]) / x["atr14"].replace(0, np.nan)
    x["dist_orb_lo_atr"] = (x["close"] - x["orb_lo"]) / x["atr14"].replace(0, np.nan)

    minute = x["minute_et"].astype(float)
    x["time_sin"] = np.sin(2 * np.pi * minute / 1440.0)
    x["time_cos"] = np.cos(2 * np.pi * minute / 1440.0)
    x["rth_frac"] = np.clip((minute - 570) / 390.0, 0, 1)
    x["is_london"] = ((minute >= 180) & (minute < 510)).astype(float)
    x["is_open"] = ((minute >= 570) & (minute < 660)).astype(float)
    x["is_midday"] = ((minute >= 660) & (minute < 840)).astype(float)
    x["is_pm"] = ((minute >= 840) & (minute < 955)).astype(float)
    x["is_power"] = ((minute >= 900) & (minute < 955)).astype(float)

    dow = x["ts_et"].dt.dayofweek
    for d in range(5):
        x[f"dow_{d}"] = (dow == d).astype(float)

    for h in [5, 10, 20, 50, 100, 200]:
        ema = x["close"].ewm(span=h, adjust=False, min_periods=h).mean()
        x[f"ema_dev_{h}_atr"] = (x["close"] - ema) / x["atr14"].replace(0, np.nan)
        x[f"ema_slope_{h}"] = (ema - ema.shift(5)) / x["atr14"].replace(0, np.nan)

    for h in HORIZONS:
        x[f"fwd_{h}"] = x["close"].shift(-h) - x["close"]
    return x


def feature_columns(df: pd.DataFrame) -> list[str]:
    excluded = {
        "time", "open", "high", "low", "close", "volume", "ts_utc", "ts_et", "date_et", "year", "minute_et",
        "prev_high", "prev_low", "prev_close", "rth_open", "orb_hi", "orb_lo",
    }
    out = []
    for c in df.columns:
        if c in excluded or c.startswith("fwd_"):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            out.append(c)
    return out


def base_eligible(df: pd.DataFrame) -> np.ndarray:
    return (((df["minute_et"] >= 180) & (df["minute_et"] < 955) & (df["year"] >= 2023) & df["atr14"].notna()).to_numpy())


def split_mask(df: pd.DataFrame, year: int) -> np.ndarray:
    return base_eligible(df) & (df["year"].to_numpy() == year)


def session_mask(df: pd.DataFrame, name: str) -> np.ndarray:
    m = df["minute_et"].to_numpy()
    if name == "ALL": return (m >= 180) & (m < 955)
    if name == "LONDON": return (m >= 180) & (m < 510)
    if name == "RTH": return (m >= 570) & (m < 955)
    if name == "OPEN": return (m >= 570) & (m < 660)
    if name == "MID": return (m >= 660) & (m < 840)
    if name == "PM": return (m >= 840) & (m < 955)
    if name == "POWER": return (m >= 900) & (m < 955)
    raise ValueError(name)


def thin_indices(idx: np.ndarray, gap: int) -> np.ndarray:
    if len(idx) == 0:
        return idx
    keep = [int(idx[0])]
    last = int(idx[0])
    for j in idx[1:]:
        j = int(j)
        if j - last >= gap:
            keep.append(j)
            last = j
    return np.asarray(keep, dtype=np.int64)


def daily_t(values: np.ndarray, dates: np.ndarray) -> tuple[float, int]:
    z = pd.DataFrame({"v": values, "d": dates}).dropna()
    if z.empty:
        return np.nan, 0
    d = z.groupby("d")["v"].mean()
    if len(d) < 2 or d.std(ddof=1) == 0:
        return np.nan, len(d)
    return float(d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))), len(d)


def normal_p_one_sided(t: float) -> float:
    return 0.5 * math.erfc(t / math.sqrt(2)) if np.isfinite(t) else np.nan


def bh_qvalues(pvals: np.ndarray) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    pv = p[ok]
    if len(pv) == 0:
        return q
    order = np.argsort(pv)
    ranked = pv[order]
    qq = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    qq = np.minimum.accumulate(qq[::-1])[::-1]
    qq = np.clip(qq, 0, 1)
    tmp = np.empty_like(qq)
    tmp[order] = qq
    q[np.flatnonzero(ok)] = tmp
    return q


@dataclass(frozen=True)
class Condition:
    feature: str
    op: str
    threshold: float


def cond_mask_full(df: pd.DataFrame, c: Condition) -> np.ndarray:
    a = df[c.feature].to_numpy()
    return a > c.threshold if c.op == ">" else a < c.threshold


def quantile_pool(df: pd.DataFrame, features: list[str]) -> list[Condition]:
    disc = split_mask(df, 2023)
    pool = []
    quantiles = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
    for f in features:
        s = df.loc[disc, f].replace([np.inf, -np.inf], np.nan).dropna()
        if len(s) < 500:
            continue
        for v in sorted(set(float(x) for x in s.quantile(quantiles).to_numpy() if np.isfinite(x))):
            pool.append(Condition(f, ">", v))
            pool.append(Condition(f, "<", v))
    return pool


def rule_key(conds, side, horizon, session):
    return (tuple(sorted((c.feature, c.op, round(float(c.threshold), 10)) for c in conds)), side, horizon, session)


def eval_rule_full(df, conds, side, horizon, session, year, cost=0.5):
    m = split_mask(df, year) & session_mask(df, session)
    for c in conds:
        m &= cond_mask_full(df, c)
    idx = thin_indices(np.flatnonzero(m), GAP[horizon])
    if len(idx) < MIN_EVENTS:
        return None
    y = df[f"fwd_{horizon}"].to_numpy()[idx] * side - cost
    good = np.isfinite(y)
    idx = idx[good]
    y = y[good]
    if len(y) < MIN_EVENTS:
        return None
    t, nd = daily_t(y, df["date_et"].to_numpy()[idx])
    return {"n": len(y), "mean": float(y.mean()), "t": t, "wr": float((y > 0).mean()), "days": nd, "idx": idx}


def screen_setup(df, pool):
    disc_idx = np.flatnonzero(split_mask(df, 2023))
    if len(disc_idx) > DISCOVERY_SCREEN_ROWS:
        sample = np.sort(rng.choice(disc_idx, DISCOVERY_SCREEN_ROWS, replace=False))
    else:
        sample = disc_idx
    screen = df.loc[sample]
    y = {h: screen[f"fwd_{h}"].to_numpy() for h in HORIZONS}
    dates = screen["date_et"].to_numpy()
    sessions = {s: session_mask(screen, s) for s in ["ALL", "LONDON", "RTH", "OPEN", "MID", "PM", "POWER"]}
    masks = []
    for c in pool:
        a = screen[c.feature].to_numpy()
        masks.append(a > c.threshold if c.op == ">" else a < c.threshold)
    return sample, y, dates, sessions, masks


def screen_rule(conds_idx, side, horizon, session, y, dates, sessions, masks):
    m = sessions[session].copy()
    for ci in conds_idx:
        m &= masks[ci]
    idx = np.flatnonzero(m)
    if len(idx) < MIN_EVENTS:
        return None
    # Screening is intentionally approximate: sample rows are not consecutive.
    ret = y[horizon][idx] * side - 0.5
    good = np.isfinite(ret)
    ret = ret[good]
    idx = idx[good]
    if len(ret) < MIN_EVENTS:
        return None
    mean = float(ret.mean())
    sd = float(ret.std(ddof=1)) if len(ret) > 1 else np.nan
    t = mean / (sd / math.sqrt(len(ret))) if np.isfinite(sd) and sd > 0 else np.nan
    return len(ret), mean, t


def screen_score(r):
    if r is None:
        return -1e9
    n, mean, t = r
    if not np.isfinite(t):
        return -1e9
    return float(t + 0.10 * math.log1p(n) + 0.05 * np.clip(mean, -10, 10))


def random_rule_indices(pool_size: int):
    k = random.choices([1, 2, 3, 4], weights=[0.10, 0.38, 0.36, 0.16])[0]
    conds = tuple(random.sample(range(pool_size), k))
    return conds, random.choice([-1, 1]), random.choice(HORIZONS), random.choice(["ALL", "LONDON", "RTH", "OPEN", "MID", "PM", "POWER"])


def discovery_search(df, pool):
    _, y, dates, sessions, masks = screen_setup(df, pool)
    hall = {}
    for i in range(1, RANDOM_RULES + 1):
        cond_idx, side, h, ses = random_rule_indices(len(pool))
        r = screen_rule(cond_idx, side, h, ses, y, dates, sessions, masks)
        if r:
            key = (tuple(sorted(cond_idx)), side, h, ses)
            sc = screen_score(r)
            old = hall.get(key)
            if old is None or sc > old[0]:
                hall[key] = (sc, cond_idx, side, h, ses, r)
        if i % 25_000 == 0:
            print(f"screened {i:,} random rules; valid unique={len(hall):,}")
    seeds = sorted(hall.values(), key=lambda z: z[0], reverse=True)[:FULL_RECHECK]
    return seeds, y, dates, sessions, masks


def mutate(rule, pool_size):
    cond_idx, side, h, ses = rule
    conds = list(cond_idx)
    action = random.choice(["replace", "replace", "add", "drop", "side", "h", "session"])
    if action == "replace" and conds:
        conds[random.randrange(len(conds))] = random.randrange(pool_size)
    elif action == "add" and len(conds) < 5:
        conds.append(random.randrange(pool_size))
    elif action == "drop" and len(conds) > 1:
        conds.pop(random.randrange(len(conds)))
    elif action == "side":
        side *= -1
    elif action == "h":
        h = random.choice(HORIZONS)
    elif action == "session":
        ses = random.choice(["ALL", "LONDON", "RTH", "OPEN", "MID", "PM", "POWER"])
    return tuple(conds), side, h, ses


def evolutionary_search(pool, seeds, y, dates, sessions, masks):
    population = [(z[1], z[2], z[3], z[4]) for z in seeds[:EVOLUTION_POP]]
    hall = {}
    for gen in range(EVOLUTION_GENS):
        scored = []
        for rule in population:
            r = screen_rule(*rule, y, dates, sessions, masks)
            if not r:
                continue
            sc = screen_score(r)
            scored.append((sc, rule, r))
            key = (tuple(sorted(rule[0])), rule[1], rule[2], rule[3])
            if key not in hall or sc > hall[key][0]:
                hall[key] = (sc, rule, r)
        scored.sort(key=lambda z: z[0], reverse=True)
        elite = [z[1] for z in scored[:EVOLUTION_ELITE]]
        print(f"evolution gen {gen+1}/{EVOLUTION_GENS}; valid={len(scored):,}; best={scored[0][0]:.3f}" if scored else "evolution empty")
        if not elite:
            break
        population = list(elite)
        while len(population) < EVOLUTION_POP:
            population.append(mutate(random.choice(elite), len(pool)))
    return sorted(hall.values(), key=lambda z: z[0], reverse=True)[:FULL_RECHECK]


def full_recheck(df, pool, seeds, evo):
    rules = []
    seen = set()
    for z in seeds:
        cond_idx, side, h, ses = z[1], z[2], z[3], z[4]
        key = (tuple(sorted(cond_idx)), side, h, ses)
        if key not in seen:
            seen.add(key); rules.append((cond_idx, side, h, ses))
    for z in evo:
        cond_idx, side, h, ses = z[1]
        key = (tuple(sorted(cond_idx)), side, h, ses)
        if key not in seen:
            seen.add(key); rules.append((cond_idx, side, h, ses))
    rules = rules[:FULL_RECHECK]

    rows = []
    for rid, (cond_idx, side, h, ses) in enumerate(rules):
        conds = tuple(pool[i] for i in cond_idx)
        d = eval_rule_full(df, conds, side, h, ses, 2023, 0.5)
        v = eval_rule_full(df, conds, side, h, ses, 2024, 0.5)
        s = eval_rule_full(df, conds, side, h, ses, 2025, 0.5)
        if not d or not v:
            continue
        rule_text = " AND ".join(f"{c.feature} {c.op} {c.threshold:.10g}" for c in conds)
        row = {
            "candidate_id": f"RULE_{rid:06d}", "family": "RULE", "side": side, "horizon": h, "session": ses, "rule": rule_text,
            "disc_n": d["n"], "disc_mean": d["mean"], "disc_t": d["t"],
            "val_n": v["n"], "val_mean": v["mean"], "val_t": v["t"],
            "seen25_n": s["n"] if s else 0, "seen25_mean": s["mean"] if s else np.nan, "seen25_t": s["t"] if s else np.nan,
        }
        for cost in COSTS:
            vr = eval_rule_full(df, conds, side, h, ses, 2024, cost)
            row[f"val_mean_cost_{str(cost).replace('.', 'p')}"] = vr["mean"] if vr else np.nan
        row["p_disc"] = normal_p_one_sided(d["t"])
        row["p_val"] = normal_p_one_sided(v["t"])
        row["robust_score"] = min(d["t"], v["t"]) + 0.12 * min(d["mean"], v["mean"])
        rows.append(row)
        if rid % 500 == 0:
            print("full recheck", rid, "kept", len(rows))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["q_disc"] = bh_qvalues(out["p_disc"].to_numpy())
        out["q_val"] = bh_qvalues(out["p_val"].to_numpy())
        out = out.sort_values("robust_score", ascending=False).reset_index(drop=True)
    return out


def parse_rule(text: str) -> tuple[Condition, ...]:
    out = []
    for part in text.split(" AND "):
        f, op, th = part.split(" ")
        out.append(Condition(f, op, float(th)))
    return tuple(out)


def bootstrap_top(df, rules):
    rows = []
    for _, r in rules.head(BOOTSTRAP_TOP).iterrows():
        conds = parse_rule(r["rule"])
        v = eval_rule_full(df, conds, int(r["side"]), int(r["horizon"]), r["session"], 2024, 0.5)
        if not v:
            continue
        vals = df[f"fwd_{int(r['horizon'])}"].to_numpy()[v["idx"]] * int(r["side"]) - 0.5
        z = pd.DataFrame({"v": vals, "d": df["date_et"].to_numpy()[v["idx"]]}).groupby("d")["v"].mean().to_numpy()
        if len(z) < 20:
            continue
        means = np.array([rng.choice(z, len(z), replace=True).mean() for _ in range(1000)])
        rows.append({
            "candidate_id": r["candidate_id"], "boot_lo95": float(np.quantile(means, 0.025)),
            "boot_median": float(np.quantile(means, 0.5)), "boot_hi95": float(np.quantile(means, 0.975)),
        })
    return pd.DataFrame(rows)


def neighborhood_test(df, rules, n=80):
    rows = []
    for _, r in rules.head(n).iterrows():
        conds = list(parse_rule(r["rule"]))
        for ci, c in enumerate(conds):
            scale = max(abs(c.threshold) * 0.10, 1e-6)
            for delta in [-0.2, -0.1, 0.1, 0.2]:
                cc = list(conds)
                cc[ci] = Condition(c.feature, c.op, c.threshold + delta * scale)
                v = eval_rule_full(df, tuple(cc), int(r["side"]), int(r["horizon"]), r["session"], 2024, 0.5)
                rows.append({
                    "candidate_id": r["candidate_id"], "condition_index": ci, "delta": delta,
                    "val_n": v["n"] if v else 0, "val_mean": v["mean"] if v else np.nan, "val_t": v["t"] if v else np.nan,
                })
    return pd.DataFrame(rows)


def ml_search(df, features):
    disc = split_mask(df, 2023)
    val = split_mask(df, 2024)
    seen = split_mask(df, 2025)
    yref = df.loc[disc, "fwd_15"]
    corrs = {}
    for f in features:
        a = df.loc[disc, f].replace([np.inf, -np.inf], np.nan)
        m = a.notna() & yref.notna()
        if m.sum() > 1000:
            c = np.corrcoef(a[m].to_numpy(), yref[m].to_numpy())[0, 1]
            corrs[f] = abs(c) if np.isfinite(c) else 0.0
    ml_feats = sorted(corrs, key=corrs.get, reverse=True)[:100]
    rows = []
    models = [
        ("RIDGE", lambda: make_pipeline(StandardScaler(), Ridge(alpha=10.0))),
        ("HGBR", lambda: HistGradientBoostingRegressor(max_iter=200, learning_rate=0.04, max_leaf_nodes=15, l2_regularization=2.0, random_state=SEED)),
        ("EXTRATREES", lambda: ExtraTreesRegressor(n_estimators=220, min_samples_leaf=45, max_features=0.7, n_jobs=-1, random_state=SEED)),
    ]
    for h in HORIZONS:
        def frame(mask):
            z = df.loc[mask, ml_feats + [f"fwd_{h}", "date_et"]].replace([np.inf, -np.inf], np.nan)
            return z.dropna(subset=[f"fwd_{h}"])
        tr, va, se = frame(disc), frame(val), frame(seen)
        if len(tr) < 5000 or len(va) < 2000:
            continue
        med = tr[ml_feats].median()
        Xtr = tr[ml_feats].fillna(med).to_numpy(np.float32); ytr = tr[f"fwd_{h}"].to_numpy(np.float32)
        Xva = va[ml_feats].fillna(med).to_numpy(np.float32); yva = va[f"fwd_{h}"].to_numpy(np.float32)
        Xse = se[ml_feats].fillna(med).to_numpy(np.float32); yse = se[f"fwd_{h}"].to_numpy(np.float32)
        fit_idx = rng.choice(len(Xtr), min(150_000, len(Xtr)), replace=False)
        for name, maker in models:
            print("fit ML", name, h)
            model = maker(); model.fit(Xtr[fit_idx], ytr[fit_idx])
            ptr, pva, pse = model.predict(Xtr), model.predict(Xva), model.predict(Xse)
            for q in [0.80, 0.90, 0.95, 0.975]:
                th = float(np.quantile(np.abs(ptr), q))
                for mode in ["SIGNED", "LONG_ONLY", "SHORT_ONLY"]:
                    def metrics(pred, y, dates):
                        if mode == "SIGNED": mask = np.abs(pred) >= th; sides = np.sign(pred)
                        elif mode == "LONG_ONLY": mask = pred >= th; sides = np.ones(len(pred))
                        else: mask = pred <= -th; sides = -np.ones(len(pred))
                        idx = thin_indices(np.flatnonzero(mask), GAP[h])
                        if len(idx) < MIN_EVENTS: return None
                        ret = y[idx] * sides[idx] - 0.5
                        t, nd = daily_t(ret, dates[idx])
                        return len(idx), float(ret.mean()), t
                    d = metrics(ptr, ytr, tr["date_et"].to_numpy())
                    v = metrics(pva, yva, va["date_et"].to_numpy())
                    s = metrics(pse, yse, se["date_et"].to_numpy())
                    if not d or not v: continue
                    rows.append({
                        "candidate_id": f"ML_{name}_H{h}_Q{q}_{mode}", "family": "ML", "model": name, "horizon": h,
                        "quantile": q, "side_mode": mode, "disc_n": d[0], "disc_mean": d[1], "disc_t": d[2],
                        "val_n": v[0], "val_mean": v[1], "val_t": v[2], "seen25_n": s[0] if s else 0,
                        "seen25_mean": s[1] if s else np.nan, "seen25_t": s[2] if s else np.nan,
                        "robust_score": min(d[2], v[2]) + 0.12 * min(d[1], v[1]),
                    })
    return pd.DataFrame(rows).sort_values("robust_score", ascending=False).reset_index(drop=True) if rows else pd.DataFrame(), ml_feats


def _prop_stop_points_outcome(df, ent, ex, side, entry, stop_points):
    stop = entry - side * stop_points
    for j in range(ent, ex + 1):
        o = float(df.at[j, "open"]); h = float(df.at[j, "high"]); l = float(df.at[j, "low"])
        if side == 1:
            if o <= stop: return o - entry, j, "STOP_GAP"
            if l <= stop: return -stop_points, j, "STOP"
        else:
            if o >= stop: return entry - o, j, "STOP_GAP"
            if h >= stop: return -stop_points, j, "STOP"
    exitp = float(df.at[ex, "close"])
    return (exitp - entry) * side, ex, "TIME"


def execution_trades(df, rules):
    out = []
    good = rules[(rules["disc_mean"] > 0) & (rules["val_mean"] > 0) & (rules["val_mean_cost_2p0"] > 0)].head(EXECUTION_TOP)
    for _, r in good.iterrows():
        conds = parse_rule(r["rule"]); side = int(r["side"]); h = int(r["horizon"])
        for year, label in [(2024, "VAL_2024"), (2025, "SEEN_2025")]:
            m = split_mask(df, year) & session_mask(df, r["session"])
            for c in conds: m &= cond_mask_full(df, c)
            idx = thin_indices(np.flatnonzero(m), GAP[h])
            for i in idx:
                ent = i + 1; ex = ent + h
                if ex >= len(df) or df.at[ent, "date_et"] != df.at[ex, "date_et"]: continue
                # Prop-compatible conversion must be flat before 16:45 ET.
                if int(df.at[ex, "minute_et"]) >= 1005: continue
                entry = float(df.at[ent, "open"]); exitp = float(df.at[ex, "close"])
                atr = float(df.at[i, "atr14"]) if np.isfinite(df.at[i, "atr14"]) else 20.0
                stop_points = max(8.0, 1.5 * atr)
                prop_pts, prop_exit_idx, prop_reason = _prop_stop_points_outcome(df, ent, ex, side, entry, stop_points)
                out.append({
                    "candidate_id": r["candidate_id"], "split": label, "date_et": df.at[ent, "date_et"],
                    "entry_time_et": df.at[ent, "ts_et"], "exit_time_et": df.at[ex, "ts_et"], "side": side,
                    "entry": entry, "exit": exitp, "gross_points": (exitp - entry) * side,
                    "atr14": atr, "prop_stop_points": stop_points, "prop_gross_points": prop_pts,
                    "prop_exit_time_et": df.at[prop_exit_idx, "ts_et"], "prop_exit_reason": prop_reason,
                })
    return pd.DataFrame(out)

def choose_contract(stop_points, budget):
    nq = stop_points * NQ_POINT + NQ_RT_COMMISSION
    q = min(MAX_NQ, int(budget // nq))
    if q >= 1: return "NQ", q, NQ_POINT, NQ_RT_COMMISSION
    mnq = stop_points * MNQ_POINT + MNQ_RT_COMMISSION
    q = min(MAX_MNQ, int(budget // mnq))
    if q >= 1: return "MNQ", q, MNQ_POINT, MNQ_RT_COMMISSION
    return None


def prop_replay(exec_df):
    rows = []
    if exec_df.empty: return pd.DataFrame()
    for cid, g in exec_df.groupby("candidate_id"):
        g = g.sort_values("entry_time_et")
        for profile, budget, daily_stop in RISK_PROFILES:
            sized = []
            for _, t in g.iterrows():
                stop_ref = float(t["prop_stop_points"])
                c = choose_contract(stop_ref, budget)
                if c is None: continue
                inst, qty, pv, comm = c
                pnl = float(t["prop_gross_points"]) * pv * qty - PROP_SLIPPAGE_RT_POINTS * pv * qty - comm * qty
                sized.append({"date": t["date_et"], "time": t["entry_time_et"], "pnl": pnl, "inst": inst, "qty": qty})
            if not sized: continue
            sdf = pd.DataFrame(sized).sort_values("time")
            daily_pairs = []
            for d, day in sdf.groupby("date", sort=True):
                cum = 0.0
                for _, tr in day.sort_values("time").iterrows():
                    if cum <= -daily_stop: break
                    cum += float(tr["pnl"])
                    if cum <= -daily_stop: break
                daily_pairs.append((d, cum))
            reps = []
            for st in range(0, len(daily_pairs), 5):
                bal = START_BALANCE; high = bal; mll = bal - MAX_LOSS; result = "OPEN"; days = 0
                for days, (_, pnl) in enumerate(daily_pairs[st:], 1):
                    bal += pnl
                    if bal <= mll: result = "FAIL"; break
                    if bal >= START_BALANCE + PROFIT_TARGET: result = "PASS"; break
                    high = max(high, bal)
                    mll = max(START_BALANCE - MAX_LOSS, min(LOCKED_MLL, high - MAX_LOSS))
                reps.append((result, days))
            passdays = [d for r, d in reps if r == "PASS"]
            rows.append({
                "candidate_id": cid, "profile": profile, "risk_budget": budget, "personal_daily_stop": daily_stop,
                "historical_starts": len(reps), "pass_rate_pct": 100 * sum(r == "PASS" for r, _ in reps) / len(reps),
                "fail_rate_pct": 100 * sum(r == "FAIL" for r, _ in reps) / len(reps),
                "open_rate_pct": 100 * sum(r == "OPEN" for r, _ in reps) / len(reps),
                "median_days_to_pass": float(np.median(passdays)) if passdays else np.nan,
            })
    return pd.DataFrame(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("alpha_factory_001_results"))
    args = ap.parse_args(); args.out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()

    df = add_features(load_data(args.data_dir))
    feats = feature_columns(df)
    pd.DataFrame({"feature": feats}).to_csv(args.out_dir / "feature_catalog.csv", index=False)
    print(f"bars={len(df):,}; features={len(feats)}")

    pool = quantile_pool(df, feats)
    pd.DataFrame([{"feature": c.feature, "op": c.op, "threshold": c.threshold} for c in pool]).to_csv(args.out_dir / "condition_pool.csv", index=False)
    print(f"condition pool={len(pool):,}")

    seeds, y, dates, sessions, masks = discovery_search(df, pool)
    evo = evolutionary_search(pool, seeds, y, dates, sessions, masks)
    rules = full_recheck(df, pool, seeds, evo)
    rules.to_csv(args.out_dir / "rule_candidates_full_recheck.csv", index=False)

    boot = bootstrap_top(df, rules)
    boot.to_csv(args.out_dir / "top_rule_bootstrap.csv", index=False)
    neigh = neighborhood_test(df, rules)
    neigh.to_csv(args.out_dir / "top_rule_neighborhoods.csv", index=False)

    ml, ml_feats = ml_search(df, feats)
    ml.to_csv(args.out_dir / "ml_candidates.csv", index=False)
    pd.DataFrame({"feature": ml_feats}).to_csv(args.out_dir / "ml_feature_subset.csv", index=False)

    exec_df = execution_trades(df, rules)
    exec_df.to_csv(args.out_dir / "execution_trades_top_rules.csv", index=False)
    prop = prop_replay(exec_df)
    prop.to_csv(args.out_dir / "prop_profiles_top_rules.csv", index=False)

    strict = rules[
        (rules["disc_mean"] > 0) & (rules["val_mean"] > 0) &
        (rules["disc_t"] > 1.5) & (rules["val_t"] > 1.5) &
        (rules["val_mean_cost_2p0"] > 0)
    ].copy() if not rules.empty else pd.DataFrame()
    strict.to_csv(args.out_dir / "strict_rule_survivors.csv", index=False)

    rr = rules[["candidate_id", "family", "horizon", "disc_n", "disc_mean", "disc_t", "val_n", "val_mean", "val_t", "seen25_n", "seen25_mean", "seen25_t", "robust_score"]].copy() if not rules.empty else pd.DataFrame()
    mm = ml[["candidate_id", "family", "horizon", "disc_n", "disc_mean", "disc_t", "val_n", "val_mean", "val_t", "seen25_n", "seen25_mean", "seen25_t", "robust_score"]].copy() if not ml.empty else pd.DataFrame()
    board = pd.concat([z for z in [rr, mm] if not z.empty], ignore_index=True).sort_values("robust_score", ascending=False) if (not rr.empty or not mm.empty) else pd.DataFrame()
    board.to_csv(args.out_dir / "combined_leaderboard.csv", index=False)

    summary = [
        "# NQ Alpha Factory 001", "",
        f"Bars: **{len(df):,}**", f"Causal features: **{len(feats)}**", f"Threshold conditions: **{len(pool):,}**",
        f"Random rules screened: **{RANDOM_RULES:,}**", f"Evolution: **{EVOLUTION_POP:,} population × {EVOLUTION_GENS} generations**",
        f"Full-sequence candidates rechecked: **{len(rules):,}**", f"Strict rule survivors: **{len(strict):,}**", f"ML candidates: **{len(ml):,}**", "",
        "## Validation design", "",
        "- 2023: discovery/search.", "- 2024: validation/model selection.",
        "- 2025: already-seen secondary evidence only; NOT untouched OOS.",
        "- Full recheck uses horizon-spaced events and day-clustered t-statistics.",
        "- Validation cost stress: 0.5, 1, 2 and 3 NQ points.",
        "- Top rules receive day bootstrap and threshold-neighborhood perturbation tests.", "",
        "## Top combined candidates", "",
        board.head(30).to_markdown(index=False) if not board.empty else "No candidates.", "",
        "## Research warning", "",
        "This factory intentionally searches a huge hypothesis space. That increases false-discovery risk. A candidate is not deployable merely because it ranks highly. Final confirmation requires genuinely unseen later data or an independent historical source.", "",
        f"Elapsed minutes: **{(time.time()-started)/60:.1f}**",
    ]
    (args.out_dir / "summary.md").write_text("\n".join(summary))
    print("\n".join(summary))


if __name__ == "__main__":
    main()

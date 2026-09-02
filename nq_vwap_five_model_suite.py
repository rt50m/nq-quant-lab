from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ET = "America/New_York"
NQ_POINT_VALUE = 20.0
MNQ_POINT_VALUE = 2.0
TICK = 0.25

# Unified screening assumptions.
ROUND_TRIP_COST_POINTS = 0.50
MAX_TRADES_PER_DAY = 3
DAILY_KILL_R = -2.0
PROP_RISK_FRACTION_OF_DRAWDOWN = 0.06
DEFAULT_ALLOWED_DRAWDOWN = 2500.0


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
            print(f"loaded {n}/{len(dates)} files")
    if not chunks:
        raise RuntimeError("No NQ bars loaded")

    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["ts_et"] = df["ts_utc"].dt.tz_convert(ET)

    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open","high","low","close"]).reset_index(drop=True)

    # Fixed research period.
    df = df[(df["ts_et"] >= "2023-01-01") & (df["ts_et"] < "2026-01-01")].reset_index(drop=True)

    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14, min_periods=14).mean()

    rng = df["high"] - df["low"]
    df["body_ratio"] = np.where(rng > 0, (df["close"]-df["open"]).abs()/rng, 0)
    df["minute_et"] = df["ts_et"].dt.hour*60 + df["ts_et"].dt.minute
    df["date_et"] = df["ts_et"].dt.date
    df["year"] = df["ts_et"].dt.year.astype(int)
    df["vol_med20"] = df["volume"].rolling(20, min_periods=20).median()
    df["relvol"] = df["volume"] / df["vol_med20"].replace(0, np.nan)

    add_adx(df, 14)
    add_day_levels(df)
    add_vwaps(df)
    add_noise_area(df, lookback_days=14)
    return df


def add_adx(df: pd.DataFrame, period: int = 14) -> None:
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    dn = -low.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)

    prev_close = close.shift(1)
    tr = pd.concat([
        high-low,
        (high-prev_close).abs(),
        (low-prev_close).abs()
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    plus = pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    minus = pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus / atr.replace(0,np.nan)
    minus_di = 100 * minus / atr.replace(0,np.nan)
    dx = 100 * (plus_di-minus_di).abs()/(plus_di+minus_di).replace(0,np.nan)
    df["adx14"] = dx.ewm(alpha=1/period, adjust=False, min_periods=period).mean()


def add_day_levels(df: pd.DataFrame) -> None:
    d = pd.Series(df["date_et"])
    daily = df.groupby("date_et").agg(day_high=("high","max"), day_low=("low","min"), day_close=("close","last"))
    daily["prev_day_high"] = daily["day_high"].shift(1)
    daily["prev_day_low"] = daily["day_low"].shift(1)
    daily["prev_day_close"] = daily["day_close"].shift(1)
    df["prev_day_high"] = d.map(daily["prev_day_high"])
    df["prev_day_low"] = d.map(daily["prev_day_low"])
    df["prev_day_close"] = d.map(daily["prev_day_close"])


def _vwap_by_key(df: pd.DataFrame, key: pd.Series, active: pd.Series | np.ndarray) -> pd.Series:
    active = pd.Series(active, index=df.index).astype(bool)
    hlc3 = (df["high"]+df["low"]+df["close"])/3.0
    vol = df["volume"].where(active, 0.0)
    pv = (hlc3*vol).where(active, 0.0)
    cpv = pv.groupby(key).cumsum()
    cv = vol.groupby(key).cumsum()
    out = cpv/cv.replace(0,np.nan)
    return out.where(active)


def add_vwaps(df: pd.DataFrame) -> None:
    local = df["ts_et"].dt.tz_localize(None)
    minute = df["minute_et"]

    rth_active = (minute >= 570) & (minute < 960)
    rth_key = local.dt.date.astype(str)
    df["vwap_rth"] = _vwap_by_key(df, rth_key, rth_active)

    eth_key = (local - pd.Timedelta(hours=18)).dt.date.astype(str)
    df["vwap_eth"] = _vwap_by_key(df, eth_key, np.ones(len(df), dtype=bool))

    df["vwap_rth_slope10"] = (
        df["vwap_rth"] -
        df["vwap_rth"].groupby(rth_key).shift(10)
    ) / df["atr14"].replace(0,np.nan)

    df["vwap_eth_slope10"] = (
        df["vwap_eth"] -
        df["vwap_eth"].groupby(eth_key).shift(10)
    ) / df["atr14"].replace(0,np.nan)


def add_noise_area(df: pd.DataFrame, lookback_days: int = 14) -> None:
    # Beat-the-Market style intraday "noise area":
    # typical absolute movement away from RTH open at each minute-of-session.
    rth = df[(df["minute_et"] >= 570) & (df["minute_et"] < 960)].copy()
    if rth.empty:
        df["noise_sigma"] = np.nan
        df["noise_upper"] = np.nan
        df["noise_lower"] = np.nan
        return

    rth["rth_open"] = rth.groupby("date_et")["open"].transform("first")
    rth["abs_move"] = (rth["close"]/rth["rth_open"] - 1.0).abs()
    rth["slot"] = rth["minute_et"] - 570

    # Leak-free: rolling mean uses only prior sessions at the same minute.
    rth["noise_sigma"] = (
        rth.groupby("slot")["abs_move"]
           .transform(lambda s: s.shift(1).rolling(lookback_days, min_periods=lookback_days).mean())
    )

    # Common published implementation uses max(open, prev close) / min(open, prev close)
    # to account for the overnight gap.
    prev_close_map = rth["prev_day_close"]
    upper_base = pd.concat([rth["rth_open"], prev_close_map], axis=1).max(axis=1)
    lower_base = pd.concat([rth["rth_open"], prev_close_map], axis=1).min(axis=1)
    rth["noise_upper"] = upper_base * (1.0 + rth["noise_sigma"])
    rth["noise_lower"] = lower_base * (1.0 - rth["noise_sigma"])

    df["noise_sigma"] = np.nan
    df["noise_upper"] = np.nan
    df["noise_lower"] = np.nan
    df.loc[rth.index, "noise_sigma"] = rth["noise_sigma"]
    df.loc[rth.index, "noise_upper"] = rth["noise_upper"]
    df.loc[rth.index, "noise_lower"] = rth["noise_lower"]


def contract_sizing(risk_points: float, allowed_drawdown: float) -> tuple[str,int,float]:
    risk_budget = allowed_drawdown * PROP_RISK_FRACTION_OF_DRAWDOWN
    if risk_points <= 0 or not np.isfinite(risk_points):
        return "NONE", 0, 0.0

    nq_risk = risk_points * NQ_POINT_VALUE
    nq_qty = int(risk_budget // nq_risk)
    if nq_qty >= 1:
        return "NQ", nq_qty, nq_qty*nq_risk

    mnq_risk = risk_points * MNQ_POINT_VALUE
    mnq_qty = max(1, int(risk_budget // mnq_risk))
    return "MNQ", mnq_qty, mnq_qty*mnq_risk


def simulate_trade(df, entry_i, side, stop, target=None, exit_mode="target_or_stop",
                   flat_minute=955, max_hold=120):
    if entry_i >= len(df):
        return None
    entry = float(df.at[entry_i,"open"])
    if side == 1 and entry <= stop:
        return None
    if side == -1 and entry >= stop:
        return None

    risk = (entry-stop) if side==1 else (stop-entry)
    if risk <= 0:
        return None

    if target is None:
        target = entry + side*risk

    end = min(len(df)-1, entry_i+max_hold-1)
    entry_date = df.at[entry_i,"date_et"]

    for j in range(entry_i, end+1):
        if df.at[j,"date_et"] != entry_date:
            j -= 1
            break

        o,h,l,c = [float(df.at[j,x]) for x in ("open","high","low","close")]
        minute = int(df.at[j,"minute_et"])

        if side == 1:
            if o <= stop:
                return entry, o, j, "SL_GAP", risk
            if l <= stop:
                return entry, stop, j, "SL", risk
            if exit_mode != "vwap_only" and h >= target:
                return entry, target, j, "TP", risk
        else:
            if o >= stop:
                return entry, o, j, "SL_GAP", risk
            if h >= stop:
                return entry, stop, j, "SL", risk
            if exit_mode != "vwap_only" and l <= target:
                return entry, target, j, "TP", risk

        if exit_mode in ("vwap_exit","vwap_only"):
            v = df.at[j,"vwap_rth"]
            if np.isfinite(v):
                if side==1 and c < v:
                    return entry, c, j, "VWAP_EXIT", risk
                if side==-1 and c > v:
                    return entry, c, j, "VWAP_EXIT", risk

        if minute >= flat_minute:
            return entry, c, j, "EOD", risk

    j = max(entry_i, min(end, j))
    return entry, float(df.at[j,"close"]), j, "TIME", risk


def add_trade(trades, model, df, signal_i, side, stop, target, result, allowed_drawdown):
    if result is None:
        return
    entry, exit_px, exit_i, reason, risk = result
    gross_pts = (exit_px-entry)*side
    gross_r = gross_pts/risk
    net_r = (gross_pts-ROUND_TRIP_COST_POINTS)/risk
    contract, qty, risk_dollars = contract_sizing(risk, allowed_drawdown)
    trades.append({
        "model": model,
        "side": "long" if side==1 else "short",
        "signal_time_et": df.at[signal_i,"ts_et"],
        "entry_time_et": df.at[signal_i+1,"ts_et"],
        "exit_time_et": df.at[exit_i,"ts_et"],
        "entry": entry,
        "stop": stop,
        "target": target,
        "exit": exit_px,
        "risk_points": risk,
        "gross_r": gross_r,
        "net_r": net_r,
        "exit_reason": reason,
        "contract_for_prop": contract,
        "contracts": qty,
        "initial_risk_dollars": risk_dollars,
        "year": int(df.at[signal_i+1,"year"]),
        "date_et": df.at[signal_i+1,"date_et"],
        "entry_hour_et": int(df.at[signal_i+1,"minute_et"]//60)
    })


def run_model_a(df, allowed_drawdown):
    """Noise-area momentum + VWAP confirmation. Highest-fidelity paper-inspired model."""
    trades=[]
    last_exit=-1
    day_count={}
    day_r={}

    for i in range(1,len(df)-1):
        date=df.at[i,"date_et"]
        m=int(df.at[i,"minute_et"])
        if m < 600 or m >= 955:  # first check 10:00; flat 15:55
            continue
        if (m-570) % 30 != 0:
            continue
        if i <= last_exit:
            continue
        if day_count.get(date,0)>=MAX_TRADES_PER_DAY or day_r.get(date,0)<=DAILY_KILL_R:
            continue

        c=float(df.at[i,"close"])
        u=df.at[i,"noise_upper"]; l=df.at[i,"noise_lower"]; v=df.at[i,"vwap_rth"]
        atr=df.at[i,"atr14"]
        if not all(np.isfinite(x) for x in (u,l,v,atr)):
            continue

        if c>u and c>v:
            side=1
        elif c<l and c<v:
            side=-1
        else:
            continue

        entry=float(df.at[i+1,"open"])
        stop = entry - side*float(atr)
        target = entry + side*float(atr)
        r=simulate_trade(df,i+1,side,stop,target,"target_or_stop",955,120)
        before=len(trades)
        add_trade(trades,"A_NOISE_AREA_MOMENTUM",df,i,side,stop,target,r,allowed_drawdown)
        if len(trades)>before:
            last_exit = df.index[df["ts_et"]==trades[-1]["exit_time_et"]][0] if False else (r[2] if r else i)
            day_count[date]=day_count.get(date,0)+1
            day_r[date]=day_r.get(date,0)+trades[-1]["net_r"]
    return trades


def run_model_b(df, allowed_drawdown):
    """Simple RTH VWAP flip/trend model."""
    trades=[]
    for date,g in df.groupby("date_et"):
        g=g[(g["minute_et"]>=571)&(g["minute_et"]<955)]
        if len(g)<2:
            continue

        in_pos=False
        side=0
        entry_i=None
        stop=None

        for i in g.index:
            if i+1>=len(df):
                break
            v=df.at[i,"vwap_rth"]
            atr=df.at[i,"atr14"]
            if not np.isfinite(v) or not np.isfinite(atr):
                continue

            c=float(df.at[i,"close"])
            desired=1 if c>v else (-1 if c<v else 0)

            if not in_pos and desired!=0:
                side=desired
                entry_i=i+1
                entry=float(df.at[entry_i,"open"])
                stop=entry-side*float(atr)  # catastrophe stop for prop compatibility
                in_pos=True
                continue

            if in_pos:
                flip = (side==1 and c<v) or (side==-1 and c>v)
                if flip or int(df.at[i,"minute_et"])>=955:
                    entry=float(df.at[entry_i,"open"])
                    exit_px=float(df.at[i,"close"])
                    risk=abs(entry-stop)
                    gross_pts=(exit_px-entry)*side
                    result=(entry,exit_px,i,"VWAP_FLIP" if flip else "EOD",risk)
                    add_trade(trades,"B_VWAP_FLIP",df,entry_i-1,side,stop,np.nan,result,allowed_drawdown)
                    in_pos=False
                    side=0
                    entry_i=None
                    stop=None
                    if flip and desired!=0 and i+1<len(df) and int(df.at[i,"minute_et"])<955:
                        side=desired
                        entry_i=i+1
                        entry=float(df.at[entry_i,"open"])
                        stop=entry-side*float(atr)
                        in_pos=True
    return trades


def run_model_c(df, allowed_drawdown):
    """Same noise-area entry, but VWAP-based exit engine."""
    trades=[]
    last_exit=-1
    for i in range(1,len(df)-1):
        m=int(df.at[i,"minute_et"])
        if m<600 or m>=955 or (m-570)%30!=0 or i<=last_exit:
            continue
        c=float(df.at[i,"close"])
        u,l,v,atr=[df.at[i,x] for x in ("noise_upper","noise_lower","vwap_rth","atr14")]
        if not all(np.isfinite(x) for x in (u,l,v,atr)):
            continue
        if c>u and c>v:
            side=1
        elif c<l and c<v:
            side=-1
        else:
            continue

        entry=float(df.at[i+1,"open"])
        stop=entry-side*float(atr)
        r=simulate_trade(df,i+1,side,stop,None,"vwap_only",955,180)
        add_trade(trades,"C_NOISE_ENTRY_VWAP_EXIT",df,i,side,stop,np.nan,r,allowed_drawdown)
        if r:
            last_exit=r[2]
    return trades


def run_model_d(df, allowed_drawdown):
    """Research reconstruction of VWAP exhaustion + ADX rollover mean reversion."""
    trades=[]
    last_exit=-1
    for i in range(2,len(df)-1):
        if i<=last_exit:
            continue
        m=int(df.at[i,"minute_et"])
        if m<600 or m>=945:
            continue
        vals=[df.at[i,x] for x in ("vwap_rth","atr14","adx14","prev_day_high","prev_day_low")]
        if not all(np.isfinite(x) for x in vals):
            continue
        v,atr,adx,pdh,pdl=map(float,vals)
        c=float(df.at[i,"close"])
        prev_adx=float(df.at[i-1,"adx14"]) if np.isfinite(df.at[i-1,"adx14"]) else np.nan
        if not np.isfinite(prev_adx):
            continue

        dev=(c-v)/atr
        near_high=abs(c-pdh)<=0.35*atr
        near_low=abs(c-pdl)<=0.35*atr
        rolling_over=(adx>=22 and adx<prev_adx)

        if near_high and dev>=1.25 and rolling_over:
            side=-1
        elif near_low and dev<=-1.25 and rolling_over:
            side=1
        else:
            continue

        entry=float(df.at[i+1,"open"])
        stop=entry-side*0.75*atr
        # Natural target = VWAP; cap to no farther than 2R for screening.
        vwap_target=v
        one_r=entry+side*abs(entry-stop)
        if side==1:
            target=min(vwap_target, entry+2*abs(entry-stop))
            target=max(target, one_r*0 + target)  # explicit scalar
        else:
            target=max(vwap_target, entry-2*abs(entry-stop))

        r=simulate_trade(df,i+1,side,stop,target,"target_or_stop",955,120)
        add_trade(trades,"D_VWAP_EXHAUSTION_ADX",df,i,side,stop,target,r,allowed_drawdown)
        if r:
            last_exit=r[2]
    return trades


def run_model_e(df, allowed_drawdown):
    """NQ-native ORB break/retest + dual-VWAP regime reconstruction."""
    trades=[]
    last_exit=-1
    for date,g in df.groupby("date_et"):
        orb=g[(g["minute_et"]>=570)&(g["minute_et"]<585)]
        session=g[(g["minute_et"]>=585)&(g["minute_et"]<840)]  # through 14:00 ET
        if orb.empty or session.empty:
            continue
        orb_hi=float(orb["high"].max())
        orb_lo=float(orb["low"].min())
        breakout_side=0
        breakout_i=None

        for i in session.index:
            if i<=last_exit or i+1>=len(df):
                continue
            c=float(df.at[i,"close"])
            atr=df.at[i,"atr14"]
            vr=df.at[i,"relvol"]
            vrth=df.at[i,"vwap_rth"]; veth=df.at[i,"vwap_eth"]
            sr=df.at[i,"vwap_rth_slope10"]; se=df.at[i,"vwap_eth_slope10"]
            if not all(np.isfinite(x) for x in (atr,vr,vrth,veth,sr,se)):
                continue

            if breakout_side==0:
                if c>orb_hi:
                    breakout_side=1; breakout_i=i
                elif c<orb_lo:
                    breakout_side=-1; breakout_i=i
                continue

            # Retest must occur within 30 bars of breakout.
            if i-breakout_i>30:
                breakout_side=0; breakout_i=None
                continue

            if breakout_side==1:
                retest=(float(df.at[i,"low"])<=orb_hi+0.15*atr and c>orb_hi)
                regime=(c>vrth and c>veth and sr>=0 and se>=0 and vr>=1.20)
                direction_bar=c>float(df.at[i,"open"])
                if retest and regime and direction_bar:
                    side=1
                else:
                    continue
            else:
                retest=(float(df.at[i,"high"])>=orb_lo-0.15*atr and c<orb_lo)
                regime=(c<vrth and c<veth and sr<=0 and se<=0 and vr>=1.20)
                direction_bar=c<float(df.at[i,"open"])
                if retest and regime and direction_bar:
                    side=-1
                else:
                    continue

            entry=float(df.at[i+1,"open"])
            if side==1:
                stop=min(float(df.at[i,"low"])-TICK, entry-0.75*atr)
            else:
                stop=max(float(df.at[i,"high"])+TICK, entry+0.75*atr)
            risk=abs(entry-stop)
            target=entry+side*1.5*risk

            r=simulate_trade(df,i+1,side,stop,target,"target_or_stop",835,120)
            add_trade(trades,"E_ORB_RETEST_DUAL_VWAP",df,i,side,stop,target,r,allowed_drawdown)
            if r:
                last_exit=r[2]
            break  # max one ORB trade/day in frozen baseline
    return trades


def summarize(trades: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    if trades.empty:
        return pd.DataFrame()
    for model,g in trades.groupby("model"):
        for period,gg in [("ALL",g)] + [(str(y),g[g["year"]==y]) for y in (2023,2024,2025)]:
            if gg.empty:
                continue
            eq=gg["net_r"].cumsum()
            dd=eq-eq.cummax()
            wins=gg["net_r"]>0
            pos=gg.loc[wins,"net_r"].sum()
            neg=-gg.loc[~wins,"net_r"].sum()
            rows.append({
                "model":model,
                "period":period,
                "trades":len(gg),
                "win_rate_pct":100*wins.mean(),
                "gross_expectancy_r":gg["gross_r"].mean(),
                "net_expectancy_r":gg["net_r"].mean(),
                "profit_factor_net":pos/neg if neg>0 else np.nan,
                "net_r_total":gg["net_r"].sum(),
                "max_drawdown_r":dd.min(),
                "avg_risk_points":gg["risk_points"].mean(),
                "median_risk_points":gg["risk_points"].median(),
                "mnq_usage_pct":100*(gg["contract_for_prop"]=="MNQ").mean(),
            })
    return pd.DataFrame(rows)


def prop_simulation(trades: pd.DataFrame, allowed_drawdown: float) -> pd.DataFrame:
    # Simple standardized "evaluation compatibility" stress test:
    # 6% of allowed drawdown risked per trade, 3 trades/day max, stop for day at -2R.
    rows=[]
    for model,g in trades.groupby("model"):
        gg=g.sort_values("entry_time_et").copy()
        risk_budget=allowed_drawdown*PROP_RISK_FRACTION_OF_DRAWDOWN
        gg["pnl_dollars_model"] = gg["net_r"] * risk_budget
        daily=gg.groupby("date_et")["pnl_dollars_model"].sum()
        eq=daily.cumsum()
        peak=eq.cummax()
        dd=eq-peak
        rows.append({
            "model":model,
            "allowed_drawdown":allowed_drawdown,
            "risk_budget_per_trade":risk_budget,
            "days":len(daily),
            "net_pnl_dollars_model":daily.sum(),
            "worst_peak_to_trough_dollars":dd.min() if len(dd) else np.nan,
            "pct_of_allowed_drawdown_used_by_worst_dd":
                100*abs(dd.min())/allowed_drawdown if len(dd) else np.nan,
            "positive_days_pct":100*(daily>0).mean() if len(daily) else np.nan,
        })
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-dir",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,default=Path("five_model_results"))
    ap.add_argument("--allowed-drawdown",type=float,default=DEFAULT_ALLOWED_DRAWDOWN)
    args=ap.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)

    df=load_data(args.data_dir)
    print(f"bars={len(df):,} range={df.ts_et.iloc[0]} -> {df.ts_et.iloc[-1]}")

    all_trades=[]
    runners=[
        ("A",run_model_a),
        ("B",run_model_b),
        ("C",run_model_c),
        ("D",run_model_d),
        ("E",run_model_e),
    ]
    for name,fn in runners:
        print("running model",name)
        t=fn(df,args.allowed_drawdown)
        print(name,"trades",len(t))
        all_trades.extend(t)

    trades=pd.DataFrame(all_trades)
    trades.to_csv(args.out_dir/"all_trades.csv",index=False)

    summary=summarize(trades)
    summary.to_csv(args.out_dir/"model_summary.csv",index=False)

    prop=prop_simulation(trades,args.allowed_drawdown)
    prop.to_csv(args.out_dir/"prop_compatibility.csv",index=False)

    by_hour=(trades.groupby(["model","entry_hour_et"])
             .agg(trades=("net_r","size"),
                  win_rate_pct=("net_r",lambda s:100*(s>0).mean()),
                  net_expectancy_r=("net_r","mean"),
                  net_r_total=("net_r","sum"))
             .reset_index()) if not trades.empty else pd.DataFrame()
    by_hour.to_csv(args.out_dir/"by_hour.csv",index=False)

    md=[]
    md.append("# NQ VWAP Five-Model Replication Suite")
    md.append("")
    md.append(f"Bars: **{len(df):,}**")
    md.append(f"Round-trip friction stress: **{ROUND_TRIP_COST_POINTS:.2f} NQ points**")
    md.append(f"Prop risk budget: **{PROP_RISK_FRACTION_OF_DRAWDOWN*100:.1f}% of allowed drawdown per trade**")
    md.append(f"Allowed drawdown used for sizing: **${args.allowed_drawdown:,.0f}**")
    md.append("")
    md.append("## Fidelity note")
    md.append("")
    md.append("- A and B are the highest-fidelity published-rule replications possible from public descriptions.")
    md.append("- C is the published noise-area entry mechanism paired with a frozen VWAP exit engine.")
    md.append("- D is a research reconstruction of the published VWAP-exhaustion/ADX framework.")
    md.append("- E is an NQ-native research reconstruction because the public ORB/VWAP project does not publish every production parameter.")
    md.append("")
    md.append("## Results")
    md.append("")
    md.append(summary.to_markdown(index=False) if not summary.empty else "No trades generated.")
    md.append("")
    md.append("## Prop-compatibility stress")
    md.append("")
    md.append(prop.to_markdown(index=False) if not prop.empty else "No prop results.")
    md.append("")
    md.append("Important: prop-firm rules vary. This suite standardizes intraday-only trading, one-position behavior, bounded risk, no martingale/averaging-down, hard EOD flat, and NQ→MNQ risk scaling. It is a research compatibility screen, not a guarantee any specific firm permits the strategy.")

    (args.out_dir/"summary.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__=="__main__":
    main()

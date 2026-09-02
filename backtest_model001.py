from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
TICK = 0.25


def load_data(data_dir: Path) -> pd.DataFrame:
    dates_path = data_dir / "dates.json"
    if not dates_path.exists():
        raise FileNotFoundError(f"Missing {dates_path}")
    dates = json.loads(dates_path.read_text())
    chunks = []
    for n, d in enumerate(dates, 1):
        p = data_dir / f"{d}.json"
        if not p.exists():
            continue
        rows = json.loads(p.read_text())
        if not rows:
            continue
        chunks.append(pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]))
        if n % 100 == 0:
            print(f"loaded {n}/{len(dates)} daily files")
    if not chunks:
        raise RuntimeError("No NQ JSON bars found")
    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates(subset="time", keep="last").sort_values("time").reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["ts_et"] = df["ts_utc"].dt.tz_convert("America/New_York")
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    return df


def add_session_vwap(df: pd.DataFrame, reset_minutes: int) -> pd.DataFrame:
    out = df.copy()
    local_naive = out["ts_et"].dt.tz_localize(None)
    shifted = local_naive - pd.to_timedelta(reset_minutes, unit="m")
    out["session_key"] = shifted.dt.date.astype(str)
    out["hlc3"] = (out["high"] + out["low"] + out["close"]) / 3.0
    pv = out["hlc3"] * out["volume"].fillna(0)
    out["cum_pv"] = pv.groupby(out["session_key"]).cumsum()
    out["cum_vol"] = out["volume"].fillna(0).groupby(out["session_key"]).cumsum()
    out["vwap"] = out["cum_pv"] / out["cum_vol"].replace(0, np.nan)
    out["vwap"] = out.groupby("session_key")["vwap"].ffill()

    above = (out["close"] > out["vwap"]).astype(int)
    below = (out["close"] < out["vwap"]).astype(int)
    out["above_10"] = above.groupby(out["session_key"]).rolling(10, min_periods=10).sum().reset_index(level=0, drop=True)
    out["below_10"] = below.groupby(out["session_key"]).rolling(10, min_periods=10).sum().reset_index(level=0, drop=True)
    out["long_accept"] = (out["above_10"] >= 8) & (out["close"] > out["vwap"])
    out["short_accept"] = (out["below_10"] >= 8) & (out["close"] < out["vwap"])

    rng = out["high"] - out["low"]
    body = (out["close"] - out["open"]).abs()
    out["body_ratio"] = np.where(rng > 0, body / rng, 0.0)
    out["close_loc"] = np.where(rng > 0, (out["close"] - out["low"]) / rng, 0.5)
    out["bull_disp"] = (
        (out["close"] > out["open"]) &
        (out["body_ratio"] >= 0.60) &
        (out["close_loc"] >= 0.75) &
        (out["close"] > out["high"].shift(1)) &
        (out["close"] > out["vwap"])
    )
    out["bear_disp"] = (
        (out["close"] < out["open"]) &
        (out["body_ratio"] >= 0.60) &
        (out["close_loc"] <= 0.25) &
        (out["close"] < out["low"].shift(1)) &
        (out["close"] < out["vwap"])
    )
    return out


def two_wrong_closes(df: pd.DataFrame, i: int, side: str) -> bool:
    if i < 1:
        return False
    if side == "long":
        return bool(df.at[i, "close"] < df.at[i, "vwap"] and df.at[i-1, "close"] < df.at[i-1, "vwap"])
    return bool(df.at[i, "close"] > df.at[i, "vwap"] and df.at[i-1, "close"] > df.at[i-1, "vwap"])


def simulate(df: pd.DataFrame, label: str, round_trip_cost_points: float = 0.50) -> pd.DataFrame:
    trades = []
    setup_side = None
    setup_state = "none"  # none, wait_touch, wait_disp
    pullback_extreme = None
    touch_idx = None
    pending = None
    pos = None

    i = 10
    n = len(df)
    while i < n:
        row = df.iloc[i]

        # Enter on the next bar open after a confirmed displacement.
        if pending is not None and pending["entry_idx"] == i and pos is None:
            entry = float(row.open)
            if pending["side"] == "long":
                stop = float(pending["extreme"] - TICK)
                risk = entry - stop
                target = entry + risk
            else:
                stop = float(pending["extreme"] + TICK)
                risk = stop - entry
                target = entry - risk
            if risk > 0 and math.isfinite(risk):
                pos = {
                    "side": pending["side"], "entry_idx": i, "entry_time": row.ts_et,
                    "entry": entry, "stop": stop, "target": target, "risk_points": risk,
                    "touch_time": pending["touch_time"], "disp_time": pending["disp_time"],
                    "max_high": float(row.high), "min_low": float(row.low),
                }
            pending = None
            setup_side = None
            setup_state = "none"
            pullback_extreme = None
            touch_idx = None

        # Manage open position. Conservative same-bar ambiguity: stop first.
        if pos is not None:
            pos["max_high"] = max(pos["max_high"], float(row.high))
            pos["min_low"] = min(pos["min_low"], float(row.low))
            exit_price = None
            reason = None
            side = pos["side"]
            if side == "long":
                if float(row.open) <= pos["stop"]:
                    exit_price, reason = float(row.open), "SL_gap"
                else:
                    stop_hit = float(row.low) <= pos["stop"]
                    target_hit = float(row.high) >= pos["target"]
                    if stop_hit:
                        exit_price, reason = pos["stop"], "SL"
                    elif target_hit:
                        exit_price, reason = pos["target"], "TP"
            else:
                if float(row.open) >= pos["stop"]:
                    exit_price, reason = float(row.open), "SL_gap"
                else:
                    stop_hit = float(row.high) >= pos["stop"]
                    target_hit = float(row.low) <= pos["target"]
                    if stop_hit:
                        exit_price, reason = pos["stop"], "SL"
                    elif target_hit:
                        exit_price, reason = pos["target"], "TP"

            if exit_price is not None:
                gross_points = (exit_price - pos["entry"]) if side == "long" else (pos["entry"] - exit_price)
                net_points = gross_points - round_trip_cost_points
                gross_r = gross_points / pos["risk_points"]
                net_r = net_points / pos["risk_points"]
                if side == "long":
                    mfe = (pos["max_high"] - pos["entry"]) / pos["risk_points"]
                    mae = (pos["entry"] - pos["min_low"]) / pos["risk_points"]
                else:
                    mfe = (pos["entry"] - pos["min_low"]) / pos["risk_points"]
                    mae = (pos["max_high"] - pos["entry"]) / pos["risk_points"]
                trades.append({
                    "vwap_variant": label,
                    "side": side,
                    "entry_time_et": pos["entry_time"],
                    "exit_time_et": row.ts_et,
                    "touch_time_et": pos["touch_time"],
                    "displacement_time_et": pos["disp_time"],
                    "entry": pos["entry"], "stop": pos["stop"], "target": pos["target"],
                    "risk_points": pos["risk_points"], "exit": exit_price, "exit_reason": reason,
                    "gross_points": gross_points, "net_points": net_points,
                    "gross_r": gross_r, "net_r": net_r,
                    "mfe_r": mfe, "mae_r": mae,
                    "bars_held": i - pos["entry_idx"] + 1,
                })
                pos = None
                # Do not form a new setup on the same bar that exits.
                i += 1
                continue

        if pos is None and pending is None and pd.notna(row.vwap):
            if setup_state == "none":
                if bool(row.long_accept):
                    setup_side, setup_state = "long", "wait_touch"
                elif bool(row.short_accept):
                    setup_side, setup_state = "short", "wait_touch"

            elif setup_state == "wait_touch":
                if two_wrong_closes(df, i, setup_side):
                    setup_side, setup_state = None, "none"
                elif setup_side == "long" and float(row.low) <= float(row.vwap):
                    setup_state, touch_idx = "wait_disp", i
                    pullback_extreme = float(row.low)
                elif setup_side == "short" and float(row.high) >= float(row.vwap):
                    setup_state, touch_idx = "wait_disp", i
                    pullback_extreme = float(row.high)

            elif setup_state == "wait_disp":
                if setup_side == "long":
                    pullback_extreme = min(float(pullback_extreme), float(row.low))
                else:
                    pullback_extreme = max(float(pullback_extreme), float(row.high))

                if two_wrong_closes(df, i, setup_side):
                    setup_side, setup_state = None, "none"
                    pullback_extreme, touch_idx = None, None
                else:
                    # Confirmation must occur after the touch bar, not on it.
                    confirmed = (i > touch_idx) and (
                        (setup_side == "long" and bool(row.bull_disp)) or
                        (setup_side == "short" and bool(row.bear_disp))
                    )
                    if confirmed and i + 1 < n:
                        pending = {
                            "side": setup_side,
                            "entry_idx": i + 1,
                            "extreme": pullback_extreme,
                            "touch_time": df.at[touch_idx, "ts_et"],
                            "disp_time": row.ts_et,
                        }
                        setup_side, setup_state = None, "none"
                        pullback_extreme, touch_idx = None, None

        i += 1

    # Mark any unresolved position at dataset end to keep accounting explicit.
    if pos is not None:
        row = df.iloc[-1]
        side = pos["side"]
        exit_price = float(row.close)
        gross_points = (exit_price - pos["entry"]) if side == "long" else (pos["entry"] - exit_price)
        net_points = gross_points - round_trip_cost_points
        trades.append({
            "vwap_variant": label, "side": side,
            "entry_time_et": pos["entry_time"], "exit_time_et": row.ts_et,
            "touch_time_et": pos["touch_time"], "displacement_time_et": pos["disp_time"],
            "entry": pos["entry"], "stop": pos["stop"], "target": pos["target"],
            "risk_points": pos["risk_points"], "exit": exit_price, "exit_reason": "DATA_END",
            "gross_points": gross_points, "net_points": net_points,
            "gross_r": gross_points / pos["risk_points"], "net_r": net_points / pos["risk_points"],
            "mfe_r": np.nan, "mae_r": np.nan, "bars_held": n - pos["entry_idx"],
        })

    return pd.DataFrame(trades)


def max_losing_streak(series: pd.Series) -> int:
    best = cur = 0
    for x in series:
        if x <= 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def summarize(t: pd.DataFrame) -> dict:
    if t.empty:
        return {"trades": 0}
    eq = t["net_r"].cumsum()
    dd = eq - eq.cummax()
    wins = t["net_r"] > 0
    losses = t["net_r"] <= 0
    pos_sum = t.loc[wins, "net_r"].sum()
    neg_sum = -t.loc[losses, "net_r"].sum()
    return {
        "trades": int(len(t)),
        "win_rate_net_pct": round(float(wins.mean() * 100), 3),
        "win_rate_gross_pct": round(float((t["gross_r"] > 0).mean() * 100), 3),
        "expectancy_net_r": round(float(t["net_r"].mean()), 5),
        "expectancy_gross_r": round(float(t["gross_r"].mean()), 5),
        "profit_factor_net": round(float(pos_sum / neg_sum), 4) if neg_sum > 0 else None,
        "max_drawdown_net_r": round(float(dd.min()), 3),
        "longest_losing_streak": int(max_losing_streak(t["net_r"])),
        "avg_risk_points": round(float(t["risk_points"].mean()), 3),
        "median_risk_points": round(float(t["risk_points"].median()), 3),
        "avg_bars_held": round(float(t["bars_held"].mean()), 2),
        "median_mfe_r": round(float(t["mfe_r"].median()), 3),
        "median_mae_r": round(float(t["mae_r"].median()), 3),
        "net_r_total": round(float(t["net_r"].sum()), 3),
        "gross_r_total": round(float(t["gross_r"].sum()), 3),
    }


def breakdowns(t: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    x = t.copy()
    x["year"] = pd.to_datetime(x["entry_time_et"]).dt.year
    x["entry_hour_et"] = pd.to_datetime(x["entry_time_et"]).dt.hour
    x["entry_date_et"] = pd.to_datetime(x["entry_time_et"]).dt.date

    def agg(g):
        return pd.Series({
            "trades": len(g),
            "win_rate_net_pct": 100 * (g.net_r > 0).mean(),
            "expectancy_net_r": g.net_r.mean(),
            "net_r_total": g.net_r.sum(),
            "avg_risk_points": g.risk_points.mean(),
        })

    by_year = x.groupby(["vwap_variant", "year"], dropna=False).apply(agg).reset_index()
    by_side = x.groupby(["vwap_variant", "side"], dropna=False).apply(agg).reset_index()
    by_hour = x.groupby(["vwap_variant", "entry_hour_et"], dropna=False).apply(agg).reset_index()
    return by_year, by_side, by_hour


def build_markdown(all_trades: pd.DataFrame, summaries: dict, cost: float) -> str:
    lines = [
        "# Model 001 — VWAP Pullback Continuation",
        "",
        f"Round-trip friction assumption: **{cost:.2f} NQ points** (default = one tick on entry + one tick on exit; commission not included).",
        "",
        "Baseline rules: 8/10 closes on VWAP side → literal VWAP touch → no 2-close opposite acceptance → displacement body ≥60%, close in outer 25%, breaks prior bar → next-bar-open entry → pullback extreme ±1 tick stop → 1R target. Same-bar TP/SL ambiguity is scored as stop first.",
        "",
    ]
    for variant, s in summaries.items():
        lines += [f"## {variant}", "", "```json", json.dumps(s, indent=2), "```", ""]
    if not all_trades.empty:
        lines += ["## Notes", "", "- Gross results ignore friction; net results subtract the configured round-trip point cost.", "- 2025 is shown but should be treated as final out-of-sample only after model rules are frozen.", "- This first baseline intentionally does not optimize parameters.", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results"))
    ap.add_argument("--round-trip-cost-points", type=float, default=0.50)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    raw = load_data(args.data_dir)
    print(f"bars={len(raw):,} range={raw.ts_et.iloc[0]} -> {raw.ts_et.iloc[-1]}")

    outputs = []
    summaries = {}
    # Primary baseline = CME Globex session reset at 18:00 ET.
    # RTH variant is included as a diagnostic because TradingView's chart-session choice can change Session VWAP behavior.
    for label, reset_minutes in [("ETH_18ET", 18 * 60), ("RTH_0930ET_DIAGNOSTIC", 9 * 60 + 30)]:
        print(f"calculating {label}")
        d = add_session_vwap(raw, reset_minutes=reset_minutes)
        tr = simulate(d, label, round_trip_cost_points=args.round_trip_cost_points)
        summaries[label] = summarize(tr)
        outputs.append(tr)
        print(label, summaries[label])

    trades = pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()
    trades.to_csv(args.out_dir / "model001_trades.csv", index=False)
    (args.out_dir / "model001_summary.json").write_text(json.dumps(summaries, indent=2, default=str))

    if not trades.empty:
        by_year, by_side, by_hour = breakdowns(trades)
        by_year.to_csv(args.out_dir / "model001_by_year.csv", index=False)
        by_side.to_csv(args.out_dir / "model001_by_side.csv", index=False)
        by_hour.to_csv(args.out_dir / "model001_by_hour.csv", index=False)

    md = build_markdown(trades, summaries, args.round_trip_cost_points)
    (args.out_dir / "summary.md").write_text(md)
    print("\n" + md)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import nq_orb_research_suite_010 as base

EXPECTED_TOTAL = 55260
MODEL_SPECS = {
    "ORB01_MODERN_5M_FORMED": {"short": "orb01", "expected": 1080, "shards": 2},
    "ORB02_VALUE_AREA_FLOW": {"short": "orb02", "expected": 2160, "shards": 3},
    "ORB03_DELAYED_25M": {"short": "orb03", "expected": 2700, "shards": 3},
    "ORB04_TSAI_TORB": {"short": "orb04", "expected": 2700, "shards": 3},
    "ORB05_VOL_STATE": {"short": "orb05", "expected": 6480, "shards": 7},
    "ORB06_STAT_THRESHOLD": {"short": "orb06", "expected": 9720, "shards": 10},
    "ORB07_GAORB_FULL_GRID": {"short": "orb07", "expected": 4500, "shards": 5},
    "ORB08_NN_THRESHOLD": {"short": "orb08", "expected": 16200, "shards": 18},
    "ORB09_PREDICTED_TR": {"short": "orb09", "expected": 3240, "shards": 4},
    "ORB10_NQ_GAP_STATE": {"short": "orb10", "expected": 6480, "shards": 7},
}

def atomic_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)

def atomic_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str))
    os.replace(tmp, path)

def add_opening_close_columns(dayfeat, days):
    for L in [1,2,3,4,5,15,25,30,35]:
        vals = {}
        for d, g in days.items():
            s = base.opening_stats(g, L)
            if s:
                vals[d] = s["close"]
        dayfeat[f"orb{L}_close"] = pd.Series(vals)

def enhanced_causality_audit(df, daily, days, dayfeat):
    checks = []

    base_audit = base.causality_audit(dayfeat)
    checks.append({
        "name": "base_orb010_audit",
        "pass": base_audit.get("status") == "PASS",
        "detail": base_audit,
    })

    # Exact config count is part of research reproducibility.
    configs = base.generate_configs()
    checks.append({
        "name": "exact_manifest_count_55260",
        "pass": len(configs) == EXPECTED_TOTAL,
        "observed": len(configs),
    })

    # Verify model-family counts independently from the workflow shard layout.
    vc = pd.Series([c.model for c in configs]).value_counts().to_dict()
    for model, spec in MODEL_SPECS.items():
        checks.append({
            "name": f"{spec['short']}_config_count",
            "pass": int(vc.get(model, 0)) == spec["expected"],
            "observed": int(vc.get(model, 0)),
            "expected": spec["expected"],
        })

    # Verify previous-session fields exactly equal lagged completed RTH values.
    idx = daily.index
    prev_close_expected = daily["rth_close"].shift(1)
    prev_ret_expected = daily["rth_close"].shift(1) / daily["rth_open"].shift(1) - 1
    m1 = np.isclose(
        daily["prev_close"].to_numpy(float),
        prev_close_expected.to_numpy(float),
        equal_nan=True
    ).all()
    m2 = np.isclose(
        daily["prev_ret"].to_numpy(float),
        prev_ret_expected.to_numpy(float),
        equal_nan=True
    ).all()
    checks.append({"name": "prev_close_is_lagged_completed_RTH", "pass": bool(m1)})
    checks.append({"name": "prev_ret_is_lagged_completed_RTH", "pass": bool(m2)})

    # Future-mutation audit:
    # changing bars AFTER an ORB is complete must not change that ORB's levels/statistics.
    tested = 0
    mutation_ok = True
    sample_days = sorted(days.keys())[100:180:7]
    for d in sample_days:
        g = days[d]
        for L in [1,5,15,25,30,35]:
            s0 = base.opening_stats(g, L)
            if not s0:
                continue
            gm = g.copy()
            future = gm["minute_et"] >= (570 + L)
            if future.any():
                # absurd future mutation: if any future information leaks into the ORB,
                # this will almost certainly change it.
                gm.loc[future, "high"] = gm.loc[future, "high"] + 5000.0
                gm.loc[future, "low"] = gm.loc[future, "low"] - 5000.0
                gm.loc[future, "close"] = gm.loc[future, "close"] + 2500.0
                gm.loc[future, "volume"] = gm.loc[future, "volume"] * 100.0 + 999999.0
                s1 = base.opening_stats(gm, L)
                tested += 1
                keys = ["hi","lo","open","close","width","vol","dir","end_min"]
                if s1 is None or any(
                    not np.isclose(float(s0[k]), float(s1[k]), equal_nan=True)
                    for k in keys
                ):
                    mutation_ok = False
                    break
        if not mutation_ok:
            break
    checks.append({
        "name": "future_bars_cannot_change_completed_ORB",
        "pass": bool(mutation_ok and tested >= 20),
        "cases_tested": tested,
    })

    # Current-day AFTER-OPEN mutations must not change state variables that are
    # supposed to be known at/near the open: prev close/return, lagged vol, EMA.
    # Recompute on several mutated days to catch accidental current-day leakage.
    state_cols = ["prev_close","prev_ret","daily_atr14","vol_10","vol_20","vol_50","vol_100","ema50","ema200"]
    state_ok = True
    state_cases = 0
    for d in sample_days[:5]:
        raw = df.copy()
        mask = (raw["date_et"] == d) & (raw["minute_et"] >= 571) & (raw["minute_et"] < 960)
        if not mask.any() or d not in daily.index:
            continue
        raw.loc[mask, "high"] += 4000.0
        raw.loc[mask, "low"] -= 4000.0
        raw.loc[mask, "close"] += 2000.0
        raw.loc[mask, "volume"] *= 50.0
        dm = base.prepare_daily(raw)
        if d not in dm.index:
            state_ok = False
            break
        for c in state_cols:
            a = daily.loc[d, c]
            b = dm.loc[d, c]
            state_cases += 1
            if not np.isclose(float(a), float(b), equal_nan=True):
                state_ok = False
                break
        if not state_ok:
            break
    checks.append({
        "name": "post_open_future_mutation_cannot_change_lagged_state",
        "pass": bool(state_ok and state_cases >= 20),
        "comparisons": state_cases,
    })

    status = "PASS" if all(bool(c["pass"]) for c in checks) else "FAIL"
    return {"status": status, "checks": checks}

def prepare_mode(data_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    print("PREPARE: loading data", flush=True)
    df = base.load_data(data_dir)
    daily = base.prepare_daily(df)
    days = base.day_map(df)
    dayfeat = base.build_day_features(df, daily, days)
    add_opening_close_columns(dayfeat, days)

    audit = enhanced_causality_audit(df, daily, days, dayfeat)
    atomic_json(audit, out_dir / "causality_audit_011.json")
    print("CAUSALITY_011", audit["status"], flush=True)
    if audit["status"] != "PASS":
        raise RuntimeError("Enhanced causality audit failed")

    print("PREPARE: training shared ML/TR gates once", flush=True)
    ml_gates, tr_gates = base.train_ml_gates(dayfeat)

    all_configs = base.generate_configs()
    if len(all_configs) != EXPECTED_TOTAL:
        raise RuntimeError(f"Manifest drift: expected {EXPECTED_TOTAL}, got {len(all_configs)}")

    manifest = pd.DataFrame([
        {"config_id": f"C{i:06d}", **asdict(c)}
        for i, c in enumerate(all_configs)
    ])
    manifest.to_csv(out_dir / "grid_manifest_011.csv", index=False)

    model_counts = manifest["model"].value_counts().sort_index().to_dict()
    atomic_json({
        "total_configs": len(manifest),
        "model_counts": {k:int(v) for k,v in model_counts.items()},
        "model_specs": MODEL_SPECS,
    }, out_dir / "manifest_counts_011.json")

    # One reusable prepared artifact. This prevents 62 shard jobs from each
    # cloning/parsing the million-bar source and retraining the ML gates.
    prepared = {
        "days": days,
        "dayfeat": dayfeat,
        "ml_gates": ml_gates,
        "tr_gates": tr_gates,
        "manifest": manifest,
    }
    joblib.dump(prepared, out_dir / "orb011_prepared.joblib", compress=3)
    print("PREPARE COMPLETE", len(manifest), "configs", flush=True)

def model_records(all_configs, model):
    return [(i,c) for i,c in enumerate(all_configs) if c.model == model]

def split_records(records, shard_index, shard_count):
    if shard_count < 1 or shard_index < 0 or shard_index >= shard_count:
        raise ValueError("Invalid shard index/count")
    chunks = np.array_split(np.arange(len(records)), shard_count)
    ids = chunks[shard_index].tolist()
    return [records[i] for i in ids]

def shard_mode(prepared_path: Path, model: str, shard_index: int, shard_count: int, out_dir: Path):
    if model not in MODEL_SPECS:
        raise ValueError(model)
    spec = MODEL_SPECS[model]
    if shard_count != spec["shards"]:
        raise RuntimeError(f"Shard-count mismatch for {model}: workflow={shard_count}, spec={spec['shards']}")

    out_dir.mkdir(parents=True, exist_ok=True)
    prep = joblib.load(prepared_path)
    days = prep["days"]
    dayfeat = prep["dayfeat"]
    ml_gates = prep["ml_gates"]
    tr_gates = prep["tr_gates"]

    all_configs = base.generate_configs()
    records = model_records(all_configs, model)
    if len(records) != spec["expected"]:
        raise RuntimeError(f"{model} expected {spec['expected']} configs, got {len(records)}")

    shard = split_records(records, shard_index, shard_count)
    short = spec["short"]
    stem = f"{short}_s{shard_index:02d}"
    result_path = out_dir / f"{stem}_results.csv"
    progress_path = out_dir / f"{stem}_progress.json"
    shard_manifest = pd.DataFrame([
        {"config_id": f"C{i:06d}", **asdict(c)}
        for i,c in shard
    ])
    shard_manifest.to_csv(out_dir / f"{stem}_manifest.csv", index=False)

    rows = []
    total = len(shard)
    print(f"START {model} shard {shard_index+1}/{shard_count}: {total} configs", flush=True)

    for n, (global_i, cfg) in enumerate(shard, 1):
        st, _ = base.run_config(
            cfg, days, dayfeat, ml_gates, tr_gates,
            base.PRIMARY_RISK, False
        )
        row = {
            "config_id": f"C{global_i:06d}",
            **asdict(cfg),
            "valid_result": st is not None,
        }
        if st:
            row.update(st)
        rows.append(row)

        # Frequent disk checkpoint. Even if Python is killed, the last checkpoint
        # is still on the runner for the workflow's `if: always()` upload step.
        if n % 25 == 0 or n == total:
            rdf = pd.DataFrame(rows)
            atomic_csv(rdf, result_path)
            atomic_json({
                "status": "RUNNING" if n < total else "PASS",
                "model": model,
                "short": short,
                "shard_index": shard_index,
                "shard_count": shard_count,
                "attempted": n,
                "expected_in_shard": total,
                "pct": round(100*n/total, 3) if total else 100.0,
                "last_config_id": f"C{global_i:06d}",
            }, progress_path)
            print(f"{model} shard {shard_index}: {n}/{total}", flush=True)

    print(f"COMPLETE {model} shard {shard_index}: {total}/{total}", flush=True)

def rank_results(res: pd.DataFrame):
    if res.empty:
        return res
    valid = res[res["valid_result"] == True].copy()
    if valid.empty:
        return valid
    for c in ["trades","trades_2024","profit_factor","avg_R","net_profit"]:
        if c not in valid.columns:
            valid[c] = np.nan
    cand = valid[(valid["trades"] >= 80) & (valid["trades_2024"] >= 20)].copy()
    if cand.empty:
        return cand
    cand["rank_score"] = (
        np.log(cand["profit_factor"].clip(lower=.01)) * np.sqrt(cand["trades"])
        + 0.25 * cand["avg_R"] * np.sqrt(cand["trades"])
    )
    return cand.sort_values(["rank_score","net_profit"], ascending=False)

def detailed_top3(cand, prepared, out_dir: Path, model: str):
    if cand.empty:
        return
    days = prepared["days"]
    dayfeat = prepared["dayfeat"]
    ml_gates = prepared["ml_gates"]
    tr_gates = prepared["tr_gates"]
    all_configs = base.generate_configs()

    logs, props, yearrows, monthrows, equityrows = [], [], [], [], []
    for _, row in cand.head(3).iterrows():
        cid = row["config_id"]
        cfg = all_configs[int(cid[1:])]
        st, tr = base.run_config(cfg, days, dayfeat, ml_gates, tr_gates, base.PRIMARY_RISK, True)
        for q in tr:
            logs.append({"config_id":cid, **q})

        tt = pd.DataFrame(tr)
        if not tt.empty:
            tt = tt.sort_values("date_et").reset_index(drop=True)
            tt["equity"] = base.START_EQUITY + tt["net_pnl"].cumsum()
            tt["cum_R"] = tt["R_actual"].cumsum()
            for _, q in tt.iterrows():
                equityrows.append({
                    "config_id":cid, "date_et":q["date_et"],
                    "equity":q["equity"], "cum_R":q["cum_R"],
                })
            for y, gg in tt.groupby("year"):
                sy = base.stats(gg.to_dict("records"))
                yearrows.append({"config_id":cid,"year":y,**(sy or {})})
            tt["month"] = pd.to_datetime(tt["date_et"]).dt.to_period("M").astype(str)
            for m, gg in tt.groupby("month"):
                sm = base.stats(gg.to_dict("records"))
                monthrows.append({"config_id":cid,"month":m,**(sm or {})})

        for risk in base.RISK_GRID:
            _, trr = base.run_config(cfg, days, dayfeat, ml_gates, tr_gates, risk, True)
            sr = base.stats(trr)
            for dll_on in [True, False]:
                pp = base.prop_replay(trr, risk, base.DAILY_STOPS[risk], dll_on)
                props.append({
                    "config_id":cid,
                    "risk_budget":risk,
                    "personal_daily_stop":base.DAILY_STOPS[risk],
                    "dll_on":dll_on,
                    **(sr or {}),
                    **pp,
                })

    pd.DataFrame(logs).to_csv(out_dir / "trade_logs_top3.csv", index=False)
    pd.DataFrame(props).to_csv(out_dir / "prop_risk_grid_top3.csv", index=False)
    pd.DataFrame(yearrows).to_csv(out_dir / "yearly_stats_top3.csv", index=False)
    pd.DataFrame(monthrows).to_csv(out_dir / "monthly_stats_top3.csv", index=False)
    pd.DataFrame(equityrows).to_csv(out_dir / "equity_curves_top3.csv", index=False)

def aggregate_model_mode(parts_dir: Path, prepared_path: Path, model: str, out_dir: Path):
    if model not in MODEL_SPECS:
        raise ValueError(model)
    spec = MODEL_SPECS[model]
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(parts_dir.rglob(f"{spec['short']}_s*_results.csv"))
    frames = []
    for p in files:
        try:
            q = pd.read_csv(p)
            if not q.empty:
                frames.append(q)
        except Exception as e:
            print("WARN could not read", p, e, flush=True)

    if frames:
        res = pd.concat(frames, ignore_index=True)
        res = res.drop_duplicates("config_id", keep="last")
    else:
        res = pd.DataFrame()

    attempted = int(len(res))
    valid = int(res["valid_result"].fillna(False).sum()) if "valid_result" in res.columns else 0
    status = "PASS" if attempted == spec["expected"] else "PARTIAL"

    res.to_csv(out_dir / "model_all_results.csv", index=False)
    cand = rank_results(res)
    cand.head(100).to_csv(out_dir / "model_top_100.csv", index=False)
    cand.head(10).to_csv(out_dir / "model_top_10.csv", index=False)

    completion = {
        "status": status,
        "model": model,
        "expected_configs": spec["expected"],
        "attempted_configs_recovered": attempted,
        "valid_result_configs": valid,
        "shard_artifact_files_found": len(files),
        "expected_shards": spec["shards"],
    }
    atomic_json(completion, out_dir / "model_completion.json")

    # Generate expensive TradingView-style detail only after the model's exhaustive
    # search has been recovered/merged.
    prep = joblib.load(prepared_path)
    detailed_top3(cand, prep, out_dir, model)

    fid = base.MODEL_FIDELITY[model]
    cols = [
        "config_id","trades","net_profit","net_R_actual","profit_factor","win_rate",
        "avg_R","avg_win","avg_loss","max_drawdown","max_drawdown_R",
        "max_win_streak","avg_win_streak","max_loss_streak","avg_loss_streak",
        "sharpe_daily","sortino_daily","PF_2023","PF_2024","PF_2025",
    ]
    showcols = [c for c in cols if c in cand.columns]
    summary = [
        f"# {model} — ORB Suite 011",
        "",
        f"Completion: **{status}** — recovered **{attempted:,}/{spec['expected']:,}** exhaustive configs.",
        f"Research fidelity: **{fid[1]}** — {fid[0]}",
        "",
        "## Top configurations ($300 risk/trade)",
        "",
        cand[showcols].head(10).to_markdown(index=False) if not cand.empty else "No ranked configurations.",
        "",
        "Top-3 artifacts include full trade logs, equity curves, monthly/yearly stats, "
        "and the $50–$300 prop-risk grid.",
    ]
    (out_dir / "model_summary.md").write_text("\n".join(summary))
    print("\n".join(summary), flush=True)

def aggregate_all_mode(models_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    completions = []
    summaries = []
    for model, spec in MODEL_SPECS.items():
        # download-artifact merge puts model files into model-specific dirs when
        # merge-multiple is false; rglob keeps this robust either way.
        candidates = list(models_dir.rglob("model_all_results.csv"))
        # Select only rows belonging to this model after reading.
        model_frames = []
        for p in candidates:
            try:
                q = pd.read_csv(p)
                if "model" in q.columns:
                    q = q[q["model"] == model]
                    if not q.empty:
                        model_frames.append(q)
            except Exception:
                pass
        if model_frames:
            m = pd.concat(model_frames, ignore_index=True).drop_duplicates("config_id")
            frames.append(m)

    allres = pd.concat(frames, ignore_index=True).drop_duplicates("config_id") if frames else pd.DataFrame()
    allres.to_csv(out_dir / "all_configuration_results_011.csv", index=False)
    cand = rank_results(allres)
    cand.head(500).to_csv(out_dir / "top_500_011.csv", index=False)
    if not cand.empty:
        cand.groupby("model", group_keys=False).head(10).to_csv(out_dir / "top_10_per_model_011.csv", index=False)
        best = cand.groupby("model", group_keys=False).head(1)
    else:
        best = pd.DataFrame()

    model_counts = allres["model"].value_counts().to_dict() if "model" in allres.columns else {}
    completion_rows = []
    all_pass = True
    for model, spec in MODEL_SPECS.items():
        got = int(model_counts.get(model, 0))
        s = "PASS" if got == spec["expected"] else "PARTIAL"
        all_pass &= s == "PASS"
        completion_rows.append({
            "model":model,
            "expected":spec["expected"],
            "recovered":got,
            "status":s,
        })
    pd.DataFrame(completion_rows).to_csv(out_dir / "model_completion_overview.csv", index=False)
    atomic_json({
        "status":"PASS" if all_pass and len(allres)==EXPECTED_TOTAL else "PARTIAL",
        "expected_total":EXPECTED_TOTAL,
        "recovered_total":int(len(allres)),
        "models":completion_rows,
    }, out_dir / "grid_completion_011.json")

    cols = [
        "config_id","model","trades","net_profit","net_R_actual","profit_factor",
        "win_rate","avg_R","max_drawdown","max_drawdown_R",
        "max_win_streak","max_loss_streak","PF_2023","PF_2024","PF_2025"
    ]
    showcols = [c for c in cols if c in best.columns]
    summary = [
        "# NQ ORB Parallel Research Suite 011",
        "",
        f"Recovered exhaustive configs: **{len(allres):,}/{EXPECTED_TOTAL:,}**",
        "",
        "## Completion by model",
        "",
        pd.DataFrame(completion_rows).to_markdown(index=False),
        "",
        "## Best ranked configuration per model",
        "",
        best[showcols].to_markdown(index=False) if not best.empty else "No ranked configurations.",
        "",
        "Primary Strategy-Tester risk: **$300/trade**. Results preserve the same 55,260-grid "
        "and execution logic as Suite 010; Suite 011 changes compute architecture, checkpointing, "
        "parallelism and progressive result publication.",
    ]
    (out_dir / "summary_011.md").write_text("\n".join(summary))
    print("\n".join(summary), flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["prepare","shard","aggregate-model","aggregate-all"])
    ap.add_argument("--data-dir", type=Path)
    ap.add_argument("--prepared-path", type=Path)
    ap.add_argument("--parts-dir", type=Path)
    ap.add_argument("--models-dir", type=Path)
    ap.add_argument("--model")
    ap.add_argument("--shard-index", type=int)
    ap.add_argument("--shard-count", type=int)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    if args.mode == "prepare":
        if args.data_dir is None:
            ap.error("--data-dir required for prepare")
        prepare_mode(args.data_dir, args.out_dir)
    elif args.mode == "shard":
        if args.prepared_path is None or args.model is None or args.shard_index is None or args.shard_count is None:
            ap.error("--prepared-path --model --shard-index --shard-count required for shard")
        shard_mode(args.prepared_path, args.model, args.shard_index, args.shard_count, args.out_dir)
    elif args.mode == "aggregate-model":
        if args.prepared_path is None or args.parts_dir is None or args.model is None:
            ap.error("--prepared-path --parts-dir --model required for aggregate-model")
        aggregate_model_mode(args.parts_dir, args.prepared_path, args.model, args.out_dir)
    else:
        if args.models_dir is None:
            ap.error("--models-dir required for aggregate-all")
        aggregate_all_mode(args.models_dir, args.out_dir)

if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

ET = "America/New_York"

LUCID_START_BALANCE = 50_000.0
LUCID_PROFIT_TARGET = 3_000.0
LUCID_MAX_LOSS = 2_000.0
LUCID_DLL = 1_200.0
LUCID_MAX_NQ = 4
LUCID_MAX_MNQ = 40
LUCID_LOCKED_MLL_BALANCE = 50_100.0

NQ_POINT_VALUE = 20.0
MNQ_POINT_VALUE = 2.0
NQ_RT_COMMISSION = 3.50
MNQ_RT_COMMISSION = 1.00
PROP_SLIPPAGE_POINTS_RT = 1.0
COST_STRESS_POINTS = (0.5, 2.0)

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

SOURCE_FIDELITY = {
    "A_BALTUSSEN_CLOSE_MOMENTUM": ("Baltussen et al. (2021), JFE", "HIGH-MECHANISM-FIDELITY",
        "NQ-specific published predictor; trading translation uses sign of predictor."),
    "B_ROSA_THRESHOLD_CLOSE_MOMENTUM": ("Rosa (2022), Journal of Futures Markets", "MECHANISM-FIDELITY_WITH_PREDECLARED_THRESHOLDS",
        "Threshold gating is public; one canonical threshold is not exposed in accessible text, so four are frozen ex ante."),
    "C_YU_OVERNIGHT_REVERSAL_REGRESSION": ("Yu, Rentzler & Wolf (2005), JOIM", "RECONSTRUCTION",
        "Public source exposes regressors and four opening-period finding, not exact period map/coefficients."),
    "D_MESFIN_RTH_CONFLUENCE": ("Mesfin (2026) MNQ positive control", "RECONSTRUCTION",
        "Public thresholds are known; GMM feature set and exact ATR scaling are omitted."),
    "E_MESFIN_LONDON_R0_R2": ("Mesfin (2026) MNQ London positive control", "RECONSTRUCTION",
        "Transition/hold are public; GMM feature specification is omitted."),
}


def load_minute_data(data_dir: Path) -> pd.DataFrame:
    dates = json.loads((data_dir / "dates.json").read_text())
    chunks = []
    for n, d in enumerate(dates, 1):
        p = data_dir / f"{d}.json"
        if p.exists():
            rows = json.loads(p.read_text())
            if rows:
                chunks.append(pd.DataFrame(rows, columns=["time","open","high","low","close","volume"]))
        if n % 150 == 0:
            print(f"loaded {n}/{len(dates)} daily files")
    if not chunks:
        raise RuntimeError("No NQ minute bars loaded")
    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["ts_et"] = df["ts_utc"].dt.tz_convert(ET)
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open","high","low","close"]).reset_index(drop=True)
    df = df[(df["ts_et"] >= "2022-12-26") & (df["ts_et"] < "2026-01-01")].reset_index(drop=True)
    df["minute_et"] = (df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).astype(int)
    df["date_et"] = df["ts_et"].dt.date
    df["year"] = df["ts_et"].dt.year.astype(int)
    prev = df["close"].shift(1)
    tr = pd.concat([
        df["high"]-df["low"], (df["high"]-prev).abs(), (df["low"]-prev).abs()
    ], axis=1).max(axis=1)
    df["atr14_1m"] = tr.rolling(14, min_periods=14).mean()
    return df


def make_bars(df1m, freq, session_start, session_end):
    x = df1m.set_index("ts_et")
    out = x.resample(freq, label="left", closed="left").agg(
        open=("open","first"), high=("high","max"), low=("low","min"),
        close=("close","last"), volume=("volume","sum"), n=("close","size")
    ).dropna(subset=["open","high","low","close"])
    out["minute_et"] = out.index.hour*60 + out.index.minute
    out["date_et"] = out.index.date
    out["year"] = out.index.year
    out = out[(out["minute_et"]>=session_start)&(out["minute_et"]<session_end)].copy()
    prev = out["close"].shift(1)
    tr = pd.concat([
        out["high"]-out["low"], (out["high"]-prev).abs(), (out["low"]-prev).abs()
    ], axis=1).max(axis=1)
    out["atr14"] = tr.rolling(14,min_periods=14).mean()
    out["ret1"] = out["close"].pct_change()
    out["absret_atr"] = (out["close"]-out["open"]).abs()/out["atr14"].replace(0,np.nan)
    out["range_atr"] = (out["high"]-out["low"])/out["atr14"].replace(0,np.nan)
    rng = out["high"]-out["low"]
    out["body_frac"] = np.where(rng>0,(out["close"]-out["open"])/rng,0.0)
    vm = out["volume"].rolling(50,min_periods=30).mean()
    vs = out["volume"].rolling(50,min_periods=30).std(ddof=0)
    out["volume_z50"] = (out["volume"]-vm)/vs.replace(0,np.nan)
    return out


def rth_daily_table(df):
    rth = df[(df["minute_et"]>=570)&(df["minute_et"]<960)].copy()
    rows=[]
    for d,g in rth.groupby("date_et"):
        g=g.sort_values("ts_et")
        if g.empty: continue
        g1530=g[g["minute_et"]==930]
        row={
            "date_et":d, "year":int(g.iloc[0]["year"]),
            "rth_open":float(g.iloc[0]["open"]), "rth_close":float(g.iloc[-1]["close"]),
            "open_ts":g.iloc[0]["ts_et"], "close_ts":g.iloc[-1]["ts_et"],
            "p1530":np.nan, "ts1530":pd.NaT, "atr1530":np.nan
        }
        if not g1530.empty:
            q=g1530.iloc[0]
            row["p1530"]=float(q["open"]); row["ts1530"]=q["ts_et"]
            row["atr1530"]=float(q["atr14_1m"]) if np.isfinite(q["atr14_1m"]) else np.nan
        rows.append(row)
    d=pd.DataFrame(rows).sort_values("date_et").reset_index(drop=True)
    d["prev_rth_close"]=d["rth_close"].shift(1)
    d["prev_rth_return"]=d["rth_close"].shift(1)/d["rth_open"].shift(1)-1
    d["overnight_return"]=d["rth_open"]/d["prev_rth_close"]-1
    d["rod_return_at_1530"]=d["p1530"]/d["prev_rth_close"]-1
    d["monday"]=(pd.to_datetime(d["date_et"]).dt.dayofweek==0).astype(int)
    d["bull60"]=((d["prev_rth_close"]/d["prev_rth_close"].shift(60)-1)>0).astype(int)
    return d


def trade_record(model, variant, side, entry_ts, exit_ts, entry, exit_px, year, date_et,
                 note, stop_ref_points, signal_strength=np.nan):
    gp=(exit_px-entry)*side
    r={"model":model,"variant":variant,"side":int(side),"entry_time_et":entry_ts,
       "exit_time_et":exit_ts,"entry_price":float(entry),"paper_exit_price":float(exit_px),
       "gross_points":float(gp),"year":int(year),"date_et":date_et,
       "stop_ref_points":float(stop_ref_points),"signal_strength":signal_strength,"paper_note":note}
    for cost in COST_STRESS_POINTS:
        r[f"net_points_cost_{str(cost).replace('.','p')}"]=gp-cost
    return r


def model_a(df,daily):
    out=[]
    for _,r in daily.iterrows():
        if r["year"]<2023 or not np.isfinite(r["rod_return_at_1530"]) or pd.isna(r["ts1530"]): continue
        if r["rod_return_at_1530"]==0: continue
        side=1 if r["rod_return_at_1530"]>0 else -1
        stop=max(10.0,1.5*r["atr1530"]) if np.isfinite(r["atr1530"]) else 25.0
        out.append(trade_record("A_BALTUSSEN_CLOSE_MOMENTUM","A_SIGN_ROD",side,
            r["ts1530"],r["close_ts"],r["p1530"],r["rth_close"],r["year"],r["date_et"],
            "Sign(rest-of-day return) traded through final RTH half-hour.",stop,abs(r["rod_return_at_1530"])))
    return out


def model_b(df,daily):
    out=[]
    for _,r in daily.iterrows():
        if r["year"]<2023 or not np.isfinite(r["overnight_return"]) or pd.isna(r["ts1530"]): continue
        if r["overnight_return"]==0: continue
        side=1 if r["overnight_return"]>0 else -1
        stop=max(10.0,1.5*r["atr1530"]) if np.isfinite(r["atr1530"]) else 25.0
        for th in [0.0025,0.005,0.0075,0.01]:
            if abs(r["overnight_return"])<th: continue
            out.append(trade_record("B_ROSA_THRESHOLD_CLOSE_MOMENTUM",f"B_ON_{int(th*10000)}bp",side,
                r["ts1530"],r["close_ts"],r["p1530"],r["rth_close"],r["year"],r["date_et"],
                "Threshold family frozen ex ante.",stop,abs(r["overnight_return"])))
    return out


def block_tuple(df,date_et,start,end):
    g=df[(df["date_et"]==date_et)&(df["minute_et"]>=start)&(df["minute_et"]<end)]
    if g.empty: return (np.nan,pd.NaT,pd.NaT,np.nan,np.nan)
    entry=float(g.iloc[0]["open"]); exitp=float(g.iloc[-1]["close"])
    return (exitp/entry-1,g.iloc[0]["ts_et"],g.iloc[-1]["ts_et"],entry,exitp)


def yu_x(row):
    y=row["prev_rth_return"]; o=row["overnight_return"]
    if not np.isfinite(y) or not np.isfinite(o): return None
    sy=float(y>0); so=float(o>0); mon=float(row["monday"]); bull=float(row["bull60"])
    return np.array([y,o,sy,so,mon,bull,y*o,y*mon,o*mon,y*bull,o*bull],float)


def model_c(df,daily):
    blocks=[(570,600),(600,630),(630,660),(660,690)]
    d=daily.copy().reset_index(drop=True)
    for b,(s,e) in enumerate(blocks,1):
        vals=[block_tuple(df,x,s,e) for x in d["date_et"]]
        for k,name in enumerate(["ret","entry_ts","exit_ts","entry_px","exit_px"]):
            d[f"{name}_b{b}"]=[v[k] for v in vals]
    X=[yu_x(r) for _,r in d.iterrows()]
    out=[]
    for i in range(len(d)):
        row=d.iloc[i]
        if row["year"]<2023 or X[i] is None: continue
        train=[j for j in range(max(0,i-504),i) if X[j] is not None]
        if len(train)<120: continue
        Xt=np.vstack([X[j] for j in train]); x=X[i].reshape(1,-1)
        for b in range(1,5):
            y=np.array([d.iloc[j][f"ret_b{b}"] for j in train],float)
            m=np.isfinite(y)
            if m.sum()<120: continue
            pred=float(LinearRegression().fit(Xt[m],y[m]).predict(x)[0])
            if not np.isfinite(pred) or pred==0: continue
            entry_ts=row[f"entry_ts_b{b}"]; exit_ts=row[f"exit_ts_b{b}"]
            ep=row[f"entry_px_b{b}"]; xp=row[f"exit_px_b{b}"]
            if pd.isna(entry_ts) or not np.isfinite(ep) or not np.isfinite(xp): continue
            side=1 if pred>0 else -1
            mg=df[df["ts_et"]==entry_ts]
            atr=float(mg["atr14_1m"].iloc[0]) if not mg.empty and np.isfinite(mg["atr14_1m"].iloc[0]) else 20
            out.append(trade_record("C_YU_OVERNIGHT_REVERSAL_REGRESSION",f"C_BLOCK_{b}",side,
                entry_ts,exit_ts,ep,xp,row["year"],row["date_et"],
                "Reconstruction: first four 30m RTH blocks frozen; coefficients estimated walk-forward.",max(10,1.5*atr),abs(pred)))
    return out


def causal_gmm_labels(bars,feature_cols,mapping,train_days=126,refit_days=20):
    labels=pd.Series(np.nan,index=bars.index,dtype=float)
    dates=list(pd.unique(bars["date_et"]))
    scaler=gmm=mp=None; last_fit=-9999
    for di,d in enumerate(dates):
        if di<train_days: continue
        if gmm is None or di-last_fit>=refit_days:
            tr_dates=set(dates[max(0,di-train_days):di])
            tr=bars[bars["date_et"].isin(tr_dates)].dropna(subset=feature_cols).copy()
            if len(tr)<500: continue
            scaler=StandardScaler(); X=scaler.fit_transform(tr[feature_cols])
            gmm=GaussianMixture(n_components=3,covariance_type="full",n_init=5,random_state=42)
            raw=gmm.fit_predict(X); tr["_raw"]=raw
            if mapping=="D":
                st=tr.groupby("_raw").agg(ret=("ret1","mean"),absret=("absret_atr","mean"),
                    rng=("range_atr","mean"),vol=("volume_z50","mean"))
                st["score"]=st["absret"].fillna(0)+.5*st["rng"].fillna(0)+.5*st["vol"].fillna(0)
                active=int(st["score"].idxmax()); rem=[x for x in st.index if x!=active]
                bull=int(st.loc[rem,"ret"].idxmax()); other=[x for x in rem if x!=bull][0]
                mp={int(other):0,active:1,bull:2}
            else:
                st=tr.groupby("_raw")["ret1"].mean().sort_values()
                mp={int(st.index[0]):0,int(st.index[1]):1,int(st.index[2]):2}
            last_fit=di
        test=bars[bars["date_et"]==d].dropna(subset=feature_cols)
        if gmm is None or test.empty: continue
        raw=gmm.predict(scaler.transform(test[feature_cols]))
        labels.loc[test.index]=[mp[int(z)] for z in raw]
    return labels


def transition_prob(labels,fr=1,to=2,window=200):
    prev=labels.shift(1)
    den=(prev==fr).astype(float).rolling(window,min_periods=50).sum()
    num=((prev==fr)&(labels==to)).astype(float).rolling(window,min_periods=50).sum()
    return num/den.replace(0,np.nan)


def model_d(df):
    b=make_bars(df,"5min",570,960)
    feats=["ret1","absret_atr","range_atr","body_frac","volume_z50"]
    b["regime"]=causal_gmm_labels(b,feats,"D")
    b["p12"]=transition_prob(b["regime"])
    idx=list(b.index); out=[]
    for pos,ts in enumerate(idx):
        r=b.loc[ts]
        if r["year"]<2023 or r["regime"]!=1 or not np.isfinite(r["p12"]) or r["p12"]<=.15: continue
        if not np.isfinite(r["volume_z50"]) or r["volume_z50"]<=.5 or not np.isfinite(r["atr14"]): continue
        exitpos=pos+13
        if exitpos>=len(idx) or b.loc[idx[exitpos],"date_et"]!=r["date_et"]: continue
        limit=float(r["close"]-2.5*r["atr14"]); fillts=None; fill=None
        for j in range(pos+1,exitpos+1):
            rr=b.loc[idx[j]]
            if rr["date_et"]!=r["date_et"]: break
            if rr["open"]<=limit: fillts=idx[j]; fill=float(rr["open"]); break
            if rr["low"]<=limit: fillts=idx[j]; fill=limit; break
        if fillts is None: continue
        xp=float(b.loc[idx[exitpos],"close"])
        out.append(trade_record("D_MESFIN_RTH_CONFLUENCE","D_GMM_R1_P12_VOL",1,
            fillts,idx[exitpos],fill,xp,r["year"],r["date_et"],
            "Reconstruction: exact thresholds; causal GMM + 2.5xATR pullback approximation.",50.0,float(r["p12"])))
    return out


def model_e(df):
    b=make_bars(df,"15min",180,510)
    feats=["ret1","absret_atr","range_atr","body_frac","volume_z50"]
    b["regime"]=causal_gmm_labels(b,feats,"E")
    idx=list(b.index); out=[]
    for pos in range(2,len(idx)-1):
        r=b.iloc[pos]
        if r["year"]<2023 or r["regime"]!=2 or b.iloc[pos-1]["regime"]!=0 or b.iloc[pos-2]["regime"]==1: continue
        ep=pos+1
        if b.iloc[ep]["date_et"]!=r["date_et"]: continue
        xp=min(ep+3,len(b)-1)
        while xp>ep and (b.iloc[xp]["date_et"]!=r["date_et"] or b.iloc[xp]["minute_et"]>=510):
            xp-=1
        atr=float(r["atr14"]) if np.isfinite(r["atr14"]) else 20
        out.append(trade_record("E_MESFIN_LONDON_R0_R2","E_CLEAN_0_TO_2",1,
            idx[ep],idx[xp],float(b.iloc[ep]["open"]),float(b.iloc[xp]["close"]),r["year"],r["date_et"],
            "Reconstruction: public R0->R2 timing exact; causal GMM feature map is reconstructed.",max(15,1.5*atr),1.0))
    return out


def summarize_paper(t):
    rows=[]
    for (m,v),g in t.groupby(["model","variant"]):
        for p,gg in [("ALL",g)]+[(str(y),g[g["year"]==y]) for y in (2023,2024,2025)]:
            if gg.empty: continue
            x=gg["gross_points"]
            rows.append({"model":m,"variant":v,"period":p,"trades":len(gg),
                "win_rate_pct":100*(x>0).mean(),"gross_mean_points":x.mean(),
                "gross_tstat":x.mean()/(x.std(ddof=1)/math.sqrt(len(x))) if len(x)>1 and x.std(ddof=1)>0 else np.nan,
                "net_mean_0p5":gg["net_points_cost_0p5"].mean(),
                "net_mean_2p0":gg["net_points_cost_2p0"].mean(),"gross_total_points":x.sum()})
    return pd.DataFrame(rows)


def stop_outcome(df,t,stoppts):
    side=int(t["side"]); entry=float(t["entry_price"])
    g=df[(df["ts_et"]>=pd.Timestamp(t["entry_time_et"]))&(df["ts_et"]<=pd.Timestamp(t["exit_time_et"]))]
    if g.empty: return float(t["gross_points"]),0.0
    stop=entry-side*stoppts; mae=0.0
    for _,r in g.iterrows():
        if side==1:
            mae=max(mae,entry-float(r["low"]))
            if float(r["open"])<=stop: return float(r["open"]-entry),mae
            if float(r["low"])<=stop: return -stoppts,max(mae,stoppts)
        else:
            mae=max(mae,float(r["high"])-entry)
            if float(r["open"])>=stop: return float(entry-r["open"]),mae
            if float(r["high"])>=stop: return -stoppts,max(mae,stoppts)
    return float(t["gross_points"]),mae


def choose_contract(stoppts,budget):
    nq=stoppts*NQ_POINT_VALUE+NQ_RT_COMMISSION
    q=min(LUCID_MAX_NQ,int(budget//nq))
    if q>=1: return "NQ",q,NQ_POINT_VALUE,NQ_RT_COMMISSION
    mnq=stoppts*MNQ_POINT_VALUE+MNQ_RT_COMMISSION
    q=min(LUCID_MAX_MNQ,int(budget//mnq))
    if q>=1: return "MNQ",q,MNQ_POINT_VALUE,MNQ_RT_COMMISSION
    return None


def prop_trade_rows(df,paper):
    rows=[]
    for _,t in paper.iterrows():
        stop=float(t["stop_ref_points"]); gp,mae=stop_outcome(df,t,stop)
        for profile,budget,dstop in RISK_PROFILES:
            c=choose_contract(stop,budget)
            if c is None: continue
            inst,q,pv,comm=c
            pnl=gp*pv*q-PROP_SLIPPAGE_POINTS_RT*pv*q-comm*q
            rows.append({"model":t["model"],"variant":t["variant"],"profile":profile,
                "risk_budget":budget,"personal_daily_stop":dstop,"date_et":t["date_et"],"year":t["year"],
                "entry_time_et":t["entry_time_et"],"exit_time_et":t["exit_time_et"],
                "instrument":inst,"qty":q,"stop_points":stop,"pnl_dollars":pnl,
                "mae_dollars":mae*pv*q+PROP_SLIPPAGE_POINTS_RT*pv*q+comm*q})
    return pd.DataFrame(rows)


def daily_pairs(g,dstop,dll_on):
    out=[]
    for d,day in g.groupby("date_et"):
        pnl=0.0
        for _,tr in day.sort_values("entry_time_et").iterrows():
            if pnl<=-dstop or (dll_on and pnl<=-LUCID_DLL): break
            pnl+=float(tr["pnl_dollars"])
            if pnl<=-dstop or (dll_on and pnl<=-LUCID_DLL): break
        out.append((d,pnl))
    return out


def replay(pairs,start):
    bal=LUCID_START_BALANCE; high=bal; mll=bal-LUCID_MAX_LOSS; peak=bal; maxdd=0.0
    for days,(d,pnl) in enumerate(pairs[start:],1):
        bal+=pnl; peak=max(peak,bal); maxdd=min(maxdd,bal-peak)
        if bal<=mll: return "FAIL",days,bal-LUCID_START_BALANCE,maxdd
        if bal>=LUCID_START_BALANCE+LUCID_PROFIT_TARGET: return "PASS",days,bal-LUCID_START_BALANCE,maxdd
        high=max(high,bal)
        mll=max(LUCID_START_BALANCE-LUCID_MAX_LOSS,min(LUCID_LOCKED_MLL_BALANCE,high-LUCID_MAX_LOSS))
    return "OPEN",len(pairs)-start,bal-LUCID_START_BALANCE,maxdd


def prop_summary(pt):
    sums=[]; starts=[]
    for (m,v,p),g in pt.groupby(["model","variant","profile"]):
        budget=float(g["risk_budget"].iloc[0]); dstop=float(g["personal_daily_stop"].iloc[0])
        for dll in (True,False):
            pairs=daily_pairs(g,dstop,dll)
            reps=[]
            for st in range(0,len(pairs),5):
                z=replay(pairs,st); reps.append(z)
                starts.append({"model":m,"variant":v,"profile":p,"dll_mode":"ON" if dll else "OFF",
                    "start_date":pairs[st][0],"result":z[0],"days":z[1],"ending_pnl":z[2],"max_dd":z[3]})
            if not reps: continue
            pdays=[z[1] for z in reps if z[0]=="PASS"]; fdays=[z[1] for z in reps if z[0]=="FAIL"]
            sums.append({"model":m,"variant":v,"profile":p,"risk_budget":budget,"personal_daily_stop":dstop,
                "dll_mode":"ON" if dll else "OFF","historical_starts":len(reps),
                "pass_rate_pct":100*sum(z[0]=="PASS" for z in reps)/len(reps),
                "fail_rate_pct":100*sum(z[0]=="FAIL" for z in reps)/len(reps),
                "open_rate_pct":100*sum(z[0]=="OPEN" for z in reps)/len(reps),
                "median_days_to_pass":np.median(pdays) if pdays else np.nan,
                "median_days_to_fail":np.median(fdays) if fdays else np.nan,
                "trades":len(g),"avg_trade_pnl":g["pnl_dollars"].mean(),
                "nq_usage_pct":100*(g["instrument"]=="NQ").mean(),"mnq_usage_pct":100*(g["instrument"]=="MNQ").mean()})
    return pd.DataFrame(sums),pd.DataFrame(starts)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-dir",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,default=Path("institutional_suite_003_results"))
    args=ap.parse_args(); args.out_dir.mkdir(parents=True,exist_ok=True)

    df=load_minute_data(args.data_dir); daily=rth_daily_table(df)
    print(f"bars={len(df):,} | {df.ts_et.iloc[0]} -> {df.ts_et.iloc[-1]}")

    trades=[]
    for name,fn in [
        ("A",lambda:model_a(df,daily)),("B",lambda:model_b(df,daily)),
        ("C",lambda:model_c(df,daily)),("D",lambda:model_d(df)),("E",lambda:model_e(df))
    ]:
        print("running",name); q=fn(); print(name,"trades",len(q)); trades.extend(q)

    paper=pd.DataFrame(trades)
    if paper.empty: raise RuntimeError("No trades generated")
    paper.to_csv(args.out_dir/"paper_pure_trades.csv",index=False)
    ps=summarize_paper(paper); ps.to_csv(args.out_dir/"paper_pure_summary.csv",index=False)

    pt=prop_trade_rows(df,paper); pt.to_csv(args.out_dir/"prop_wrapped_trades_all_profiles.csv",index=False)
    sm,st=prop_summary(pt)
    sm.to_csv(args.out_dir/"prop_profile_summary.csv",index=False)
    st.to_csv(args.out_dir/"prop_historical_start_replays.csv",index=False)

    fid=pd.DataFrame([{"model":k,"source":v[0],"status":v[1],"note":v[2]} for k,v in SOURCE_FIDELITY.items()])
    fid.to_csv(args.out_dir/"model_fidelity.csv",index=False)
    best=(sm.sort_values(["pass_rate_pct","fail_rate_pct"],ascending=[False,True])
          .groupby(["model","variant"],as_index=False).head(3))
    best.to_csv(args.out_dir/"best_prop_profiles_per_variant.csv",index=False)

    riskdf=pd.DataFrame(RISK_PROFILES,columns=["profile","risk_budget","personal_daily_stop"])
    md=["# NQ Institutional Paper Suite 003","",
        "Paper-mechanism results are separate from the prop wrapper. 2025 is not called untouched OOS because this project has already inspected it.","",
        "## Risk profiles","",riskdf.to_markdown(index=False),"",
        "## Paper-mechanism results","",ps.to_markdown(index=False),"",
        "## Best prop profiles per variant","",best.to_markdown(index=False) if not best.empty else "No prop results.","",
        "## Model fidelity","",fid.to_markdown(index=False)]
    (args.out_dir/"summary.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__=="__main__":
    main()

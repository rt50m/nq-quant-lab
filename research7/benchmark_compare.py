from __future__ import annotations
import argparse, json, math
from pathlib import Path

def close(a,b,tol):
    return math.isfinite(float(a)) and abs(float(a)-float(b)) <= tol

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--benchmark",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()

    report=json.loads(a.report.read_text())
    bench=json.loads(a.benchmark.read_text())
    exp=bench["expected"]; tol=float(bench.get("tolerance_dollars",0.01))
    checks=[]

    def add(name,actual,expected,ok):
        checks.append({"name":name,"actual":actual,"expected":expected,"match":bool(ok)})

    add("unique_exact_portfolios",report.get("unique_exact_portfolios"),exp["unique_exact_portfolios"],
        report.get("unique_exact_portfolios")==exp["unique_exact_portfolios"])
    add("scale_passes",report.get("scale_passes"),exp["scale_passes"],
        report.get("scale_passes")==exp["scale_passes"])
    add("credible_passes",report.get("credible_passes"),exp["credible_passes"],
        report.get("credible_passes")==exp["credible_passes"])

    oracle=report["best_oracle"][0]
    oe=exp["oracle_best"]
    for k in ["net_profit","max_drawdown","net_2023","net_2024","net_2025"]:
        add("oracle."+k,oracle["stats"][k],oe[k],close(oracle["stats"][k],oe[k],tol))
    add("oracle.trades",oracle["meta"]["portfolio_trades"],oe["trades"],
        oracle["meta"]["portfolio_trades"]==oe["trades"])
    add("oracle.choice",oracle["choice"],oe["choice"],oracle["choice"]==oe["choice"])

    cap=2000.0
    valid=[r for r in report["best_disciplined"]
           if r["stats"]["max_drawdown"]>-cap and r["stats"]["max_exposure_equiv_mnq"]<=40]
    if not valid:
        raise SystemExit("No cap-valid portfolio in best_disciplined")
    disc=valid[0]; de=exp["disciplined_cap_valid_best"]
    for k in ["net_profit","max_drawdown"]:
        add("disciplined."+k,disc["stats"][k],de[k],close(disc["stats"][k],de[k],tol))
    for k in ["selection_net","selection_daily_mdd"]:
        add("disciplined."+k,disc[k],de[k],close(disc[k],de[k],tol))
    add("disciplined.choice",disc["choice"],de["choice"],disc["choice"]==de["choice"])

    ok=all(x["match"] for x in checks)
    result={"status":"PASS" if ok else "FAIL","checks":checks}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    if not ok:
        raise SystemExit(2)

if __name__=="__main__":
    main()

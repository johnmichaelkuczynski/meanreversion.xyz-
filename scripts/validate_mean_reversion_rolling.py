"""Reproducible anonymous-schematic and real-market scoring report."""
from concurrent.futures import ThreadPoolExecutor
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/"tests")]

from mean_reversion_schematics import schematic_series, qualified_flat_deep_dip
from mean_reversion_winner import CONFIG, analyze_winner
from stock_chart_api import load_stock_history

OUT = ROOT/"generated-artifacts"


def compact(a):
    return {
        "symbol": a["symbol"], "latest_growth_pct": a.get("slope_pct"),
        "median_growth_pct": a.get("median_growth_pct"),
        "positive_year_fraction": a.get("positive_year_fraction"),
        "gap_pct": a.get("position_pct"), "gap_percentile": a.get("percentile"),
        "closeness": a["closeness_score"], "recovery": a["recovery_score"],
        "reversion": a["mean_reversion_score"], "mature_events": a["mature_count"],
        "newer_events": a["newer_count"],
        "recovered_5y": a.get("recovery_fractions", {}).get("5"),
        "recovered_3y": a.get("recovery_fractions", {}).get("3"),
        "recovered_1y": a.get("recovery_fractions", {}).get("1"),
        "depth_bonus_B": a.get("depth_bonus"), "drawdown90": a.get("drawdown90"),
        "drawdown_D": a.get("drawdown_factor"), "base": a.get("base_score"),
        "steel": a["scores"]["steel"], "paper": a["scores"]["paper"],
        "verdict": a["verdict"], "deep_dip": a["deep_dip"],
        "dip_matched_events": a.get("matched_dip_count"),
        "dip_recovery_fraction": a.get("matched_dip_recovery_fraction"),
    }


def main():
    OUT.mkdir(exist_ok=True)
    anonymous = {number: analyze_winner(h) for number, h in schematic_series()}
    high = CONFIG["minimum_mean_reversion"]
    checks = [
        {"test": "Drawing 1 high reversion", "passed": anonymous[1]["mean_reversion_score"] >= high},
        {"test": "Drawing 2 high reversion", "passed": anonymous[2]["mean_reversion_score"] >= high},
        {"test": "Drawing 2 small edge over 1 (0 < difference <= 10 points)",
         "passed": 0 < anonymous[2]["mean_reversion_score"]-anonymous[1]["mean_reversion_score"] <= 10},
        {"test": "Drawing 3 high reversion and growth winner",
         "passed": anonymous[3]["mean_reversion_score"] >= high and anonymous[3]["winner"]},
        {"test": "Drawing 4 high reversion but not a growth winner",
         "passed": anonymous[4]["mean_reversion_score"] >= high and not anonymous[4]["winner"]},
    ]
    dip = analyze_winner(qualified_flat_deep_dip())
    checks.append({"test": "Drawing 5-type flat range flags a deep dip once mature depth evidence qualifies",
                   "passed": dip["deep_dip"] and not dip["winner"]})
    # Frozen-trend crash check, independent of rolling fits that later collapse.
    _, crash_h = schematic_series()[3]
    crash_h["prices"] = [100. if i < 5000 else 20. for i in range(len(crash_h["prices"]))]
    crash = analyze_winner(crash_h)
    crash_event = next(e for e in crash["mature_events"] if e["opened"] == crash_h["dates"][5000])
    checks.append({"test": "Unrecovered crash gets no frozen-trend recovery credit", "passed": not crash_event["recovered"]})
    symbols = ("MSFT", "AAPL", "SOXL", "TQQQ", "QQQ", "SOXX", "DIS")
    def market(symbol):
        if "--cached" in sys.argv:
            h = json.loads((OUT/f"rolling-history-{symbol}.json").read_text())
        else:
            h = load_stock_history(symbol, start_date="1900-01-01", tiingo_only=True)
        (OUT/f"rolling-history-{symbol}.json").write_text(json.dumps(h))
        a = analyze_winner(h)
        return {**compact(a), "first_close": h["dates"][0], "last_close": h["dates"][-1],
                "eligible_days": len(a["trend_dates"])}, a
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(market, symbols))
    market_rows = [row for row, _ in results]
    report = {
        "config": dict(CONFIG), "schematic_checks": checks,
        "schematics": {str(i): compact(a) for i, a in anonymous.items()},
        "qualified_flat_deep_dip": compact(dip), "market": market_rows,
        "failed_checks": [c["test"] for c in checks if not c["passed"]],
        "conventions": [
            "Schematic series are transparent numerical approximations, not digitized original pictures. All use symbol HIDDEN.",
            "High schematic reversion means >=60 (the supplied default reversion threshold); small edge means <=10 points.",
            "Median slope uses all eligible daily annualized slopes; positive-year share uses completed calendar year ends.",
            "Five-year fitting windows and recovery horizons are calendar years. The scored close is excluded from its fit.",
            "Band is +/-10% in price; recovery halves the opening log-price gap against a frozen opening-day projected trend.",
            "New departure requires a return to the daily fitted band. Recovery alone does not re-arm departures.",
            "All recovery horizons use the same mature cohort, including failures; newer events are excluded.",
            "B uses only mature downside events recovered within five years. D uses full available 252-prior-session drawdowns.",
            "Deep-dip evidence is independent of growth-winner status; no ticker overrides or external reference normalization.",
            "Comparisons and tricolor touch estimates remain separate from the ranking scores; no publishing was performed.",
        ],
    }
    (OUT/"mean-reversion-rolling-validation.json").write_text(json.dumps(report, indent=2))
    with (OUT/"mean-reversion-rolling-validation.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(market_rows[0]))
        writer.writeheader()
        writer.writerows(market_rows)
    lines = ["MEAN REVERSION — ROLLING-TREND VALIDATION", "", *report["conventions"], "",
             "ANONYMOUS SCHEMATIC CHECKS"]
    lines += [f"{'PASS' if c['passed'] else 'FAIL'}: {c['test']}" for c in checks]
    lines += ["", "ALL 13 ANONYMOUS SCHEMATIC RESULTS"]
    lines += [f"Drawing {i}: "+json.dumps(compact(a)) for i,a in anonymous.items()]
    lines += ["", "REAL SECURITIES — FULL AVAILABLE ADJUSTED DAILY CLOSES"]
    def number(value, suffix=""):
        return "Unavailable" if value is None else f"{value:.6f}{suffix}"
    for row in market_rows:
        lines += [
            "", row["symbol"]+" — "+row["verdict"],
            f"Adjusted-close history: {row['first_close']} through {row['last_close']}; eligible days: {row['eligible_days']}",
            "Closeness: "+number(row["closeness"], "%"),
            "Recovery score: "+number(row["recovery"], " / 100"),
            "Mean Reversion Score: "+number(row["reversion"], " / 100"),
            "Mature / newer events: "+str(row["mature_events"])+" / "+str(row["newer_events"]),
            "5y / 3y / 1y recovery fractions: "+" / ".join(number(row[k]) for k in ("recovered_5y","recovered_3y","recovered_1y")),
            "Latest annualized trend: "+number(row["latest_growth_pct"], "%"),
            "Median annualized trend: "+number(row["median_growth_pct"], "%"),
            "Positive year-end slope fraction U: "+number(row["positive_year_fraction"]),
            "Signed gap: "+number(row["gap_pct"], "%")+"; historical percentile: "+number(row["gap_percentile"]),
            "Base ranking score: "+number(row["base"]),
            "Steel depth component B: "+number(row["depth_bonus_B"]),
            "90th-percentile drawdown: "+number(row["drawdown90"])+"; capped D: "+number(row["drawdown_D"]),
            "Steel Hands: "+number(row["steel"], " / 100"),
            "Paper Hands: "+number(row["paper"], " / 100"),
            "Deep-dip flag: "+str(row["deep_dip"])+"; matching mature downside events: "+str(row["dip_matched_events"]),
            "Matching downside recovery fraction: "+number(row["dip_recovery_fraction"]),
        ]
    (OUT/"mean-reversion-rolling-validation.txt").write_text("\n".join(lines)+"\n")
    for row in market_rows:
        print(json.dumps(row))
    print("SCHEMATIC CHECKS:", json.dumps(checks))
    print("Reports:", OUT/"mean-reversion-rolling-validation.txt")


if __name__ == "__main__":
    # The active scorer is no longer the rolling-recovery model. Keep this
    # historical report source, but never run its old assertions on new scores.
    from validate_mean_reversion_weighted import main as weighted_main
    print("Rolling scoring was superseded; generating the weighted regression report.")
    weighted_main()

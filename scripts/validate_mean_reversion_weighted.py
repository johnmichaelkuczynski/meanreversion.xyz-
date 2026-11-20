"""Frozen adjusted-close regression report; never tune formulas to ticker names."""
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mean_reversion_channels import fit_channel
from mean_reversion_winner import CONFIG, analyze_winner, normalize_scores
from stock_chart_api import load_stock_history

OUT = ROOT/"generated-artifacts"
AS_OF = "2026-11-19"
SYMBOLS = ("MSFT", "AAPL", "COST", "QQQ", "SOXX", "SOXL", "TQQQ",
           "V", "MA", "BJ", "IBN", "DIS", "INTC", "ACTG", "GRML", "VWAV", "BKHA")
# These are the only numeric references supplied in the current request.
# Comparing one-decimal rounding does not invent tolerances for other fields.
EXPECTED_SLOPES = {"MSFT": 18.5, "AAPL": 26.3, "COST": 17.1, "INTC": 8.6}


def snapshot(symbol):
    target = OUT/f"weighted-history-{symbol}.json"
    legacy = OUT/f"rolling-history-{symbol}.json"
    path = target if target.exists() else legacy
    if path.exists():
        history = json.loads(path.read_text())
    else:
        history = load_stock_history(symbol, start_date="1900-01-01", tiingo_only=True)
    pairs = [(day, price) for day, price in zip(history["dates"], history["prices"]) if day <= AS_OF]
    if len(pairs) < 2:
        raise ValueError("Fewer than two adjusted closes at the regression cutoff.")
    history.update(dates=[d for d, _ in pairs], prices=[p for _, p in pairs], through=pairs[-1][0])
    encoded = json.dumps(history, sort_keys=True)
    target.write_text(encoded)
    return history, hashlib.sha256(encoded.encode()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    histories, analyses, errors, hashes = {}, {}, {}, {}
    def load(symbol):
        try:
            history, digest = snapshot(symbol)
            return symbol, history, analyze_winner(history), digest, None
        except Exception as exc:
            # Do not serialize remote request URLs, headers, or credentials.
            return symbol, None, None, None, type(exc).__name__
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol, history, analysis, digest, error in pool.map(
                load, dict.fromkeys((*SYMBOLS, *CONFIG["reference_symbols"]))):
            if error:
                errors[symbol] = error
            else:
                histories[symbol], analyses[symbol], hashes[symbol] = history, analysis, digest
    rows, checks = [], []
    references = list(analyses.values())
    for symbol in SYMBOLS:
        if symbol not in analyses:
            rows.append({"Ticker": symbol, "Verdict": "DATA UNAVAILABLE",
                         "Reference check": "BLOCKED — adjusted history unavailable"})
            continue
        a, h = analyses[symbol], histories[symbol]
        scores = normalize_scores(a, references)
        channel = fit_channel(h, "2126-11-19")
        agreement = abs(channel["slope_pct"]-a["slope_pct"]) < 1e-10
        agreement &= abs(channel["position_pct"]-a["position_pct"]) < 1e-8
        checks.append({"ticker": symbol, "check": "chart/scorer slope and position agree",
                       "passed": bool(agreement)})
        reference = EXPECTED_SLOPES.get(symbol)
        if reference is not None:
            passed = round(a["slope_pct"], 1) == reference
            checks.append({"ticker": symbol, "check": "supplied slope rounded to one decimal",
                           "expected": reference, "actual": a["slope_pct"], "passed": passed})
            status = "PASS — supplied slope" if passed else "FAIL — supplied slope"
        else:
            status = "REFERENCE NOT SUPPLIED"
        if symbol == "INTC":
            passed = a["verdict"] == "NOT A GROWTH STOCK — not a winner"
            checks.append({"ticker": symbol, "check": "supplied INTC verdict", "passed": passed})
        rows.append({
            "Ticker": symbol, "Start": h["dates"][0], "Last close": h["dates"][-1],
            "Years": a["years"], "G %": a["slope_pct"], "W": a["swing"],
            "L": a["longest_excursion"], "PULL": a["pull"], "Pull": a["pull_strength"],
            "Volatility %": a["volatility"]*100 if a["volatility"] is not None else None,
            "Steel": scores["steel"], "Paper": scores["paper"],
            "Position %": a["position_pct"], "Verdict": a["verdict"],
            "Reference check": status,
        })
    missing = [s for s in CONFIG["reference_symbols"] if s not in analyses]
    report = {
        "as_of": AS_OF, "config": dict(CONFIG), "rows": rows, "checks": checks,
        "failed_checks": [c for c in checks if not c["passed"]],
        "unavailable_histories": errors, "missing_normalization_references": missing,
        "snapshot_sha256": hashes,
        "reference_coverage": {
            "supplied": "Four one-decimal slopes and INTC verdict.",
            "missing": "Full weighted regression table, short-history list, other expected metrics, and numerical tolerances were not in the available uploads.",
            "completion": "Not fully certified against the unavailable reference table.",
        },
        "conventions": [
            "Full available Tiingo adjusted daily history through the frozen cutoff; no ticker-specific formulas.",
            "t is calendar days / 365.25; w = 0.5 ** ((t_last-t)/7); polyfit receives sqrt(w).",
            "W and daily-return volatility are weighted population standard deviations.",
            "Returns use the recency weight of the ending close; annualized volatility multiplies by sqrt(252).",
            "20-session trailing mean uses available observations at the first 19 closes.",
            "Excursions split at zero crossings; sum |smoothed residual| * w / 252, including open/end excursions.",
            "L is the maximum weighted excursion area; Pull = 1/(1+L/8).",
            "The earlier excursion specification supplies the hand-score formulas and complete fixed reference normalization.",
            "The current request supersedes the earlier 5% growth threshold with 12%.",
            "GRML, VWAV and BKHA are the available conversation's short-history examples, not an invented exhaustive test list.",
        ],
    }
    (OUT/"mean-reversion-weighted-regression.json").write_text(json.dumps(report, indent=2))
    columns = list(next(r for r in rows if "G %" in r))
    with (OUT/"mean-reversion-weighted-regression.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    lines = ["RECENCY-WEIGHTED MEAN REVERSION REGRESSION", "As of "+AS_OF, "",
             *report["conventions"], "", "REFERENCE COVERAGE",
             *report["reference_coverage"].values(), "",
             "Ticker | G % | W | L | PULL | Steel | Paper | Position % | Verdict"]
    def n(value):
        return "Unavailable" if value is None else f"{value:.6f}"
    for r in rows:
        lines.append(" | ".join([r["Ticker"], *[n(r.get(k)) for k in
                     ("G %", "W", "L", "PULL", "Steel", "Paper", "Position %")], r["Verdict"]]))
    lines += ["", "CHECKS", *[json.dumps(c) for c in checks],
              "", "Unavailable histories: "+json.dumps(errors)]
    (OUT/"mean-reversion-weighted-regression.txt").write_text("\n".join(lines)+"\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

"""Full-history winner heuristic, with the user's fixed, untuned constants."""
from types import MappingProxyType

import numpy as np
import pandas as pd

CONFIG = MappingProxyType({
    "minimum_history_years": 5.,
    "pull_scale": 8.,
    "pull_threshold": .5,
    "strong_pull": .8,
    "minimum_slope": .05,
    "range_minimum_slope": -.10,
    "buy_zone_width": .5,
    "paper_penalty": 3.,
    "paper_exponent": 4,
    "smoothing_days": 20,
    "trading_days": 252,
    "calendar_days": 365.25,
})
REFERENCE_SYMBOLS = ("SOXL", "TQQQ", "SOXX", "QQQ", "SPY")


def excursion_statistics(smoothed):
    """Include boundary/open excursions: a missing return must not erase risk."""
    excursions = []
    area, count, peak, sign = 0., 0, 0., 0
    for value in np.asarray(smoothed, dtype=float):
        if not np.isfinite(value):
            raise ValueError("Excursions require finite residuals.")
        next_sign = int(np.sign(value))
        if next_sign == 0 or (sign and next_sign != sign):
            if count:
                excursions.append((area, count, peak))
            area, count, peak, sign = 0., 0, 0., 0
        if next_sign:
            sign = next_sign
            area += abs(float(value)) / CONFIG["trading_days"]
            count += 1
            peak = max(peak, abs(float(np.expm1(value))) * 100)
    if count:
        excursions.append((area, count, peak))
    if not excursions:
        return 0., 0., 0.
    largest_area = max(item[0] for item in excursions)
    longest = max(excursions, key=lambda item: item[1])
    return largest_area, longest[1] / CONFIG["trading_days"], longest[2]


def analyze_winner(history):
    prices = np.asarray(history["prices"], dtype=float)
    dates = pd.DatetimeIndex(pd.to_datetime(history["dates"], utc=True)).tz_localize(None)
    if len(prices) < 2 or len(prices) != len(dates):
        raise ValueError("At least two adjusted daily closes are required.")
    if not np.all(np.isfinite(prices) & (prices > 0)):
        raise ValueError("Adjusted closes must be positive and finite.")
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("History must have distinct ascending dates.")
    time = np.asarray((dates - dates[0]).days, dtype=float) / CONFIG["calendar_days"]
    y = np.log(prices)
    centered = time - time.mean()
    denominator = float(centered @ centered)
    if denominator <= 0:
        raise ValueError("Two distinct dates are required.")
    slope = float(centered @ (y - y.mean()) / denominator)
    intercept = float(y.mean() - slope * time.mean())
    residual = y - (intercept + slope * time)
    swing = float(np.std(residual, ddof=0))
    smoothed = pd.Series(residual).rolling(CONFIG["smoothing_days"]).mean().dropna()
    longest, duration, peak = excursion_statistics(smoothed)
    pull = 1. / (1. + longest / CONFIG["pull_scale"])
    growth = float(np.expm1(slope))
    has_mean = bool(time[-1] >= CONFIG["minimum_history_years"])
    if not has_mean:
        verdict = "NO MEAN YET"
    elif pull < CONFIG["pull_threshold"]:
        verdict = "NO RELIABLE MEAN"
    elif growth < CONFIG["minimum_slope"]:
        verdict = "NOT A GROWTH STOCK"
    else:
        verdict = "WINNER"
    winner = verdict == "WINNER"
    raw = {
        "steel": growth * pull * (1 + swing) if winner else 0.,
        "paper": growth * pull / (1 + CONFIG["paper_penalty"] * swing) ** CONFIG["paper_exponent"]
        if winner else 0.,
    }
    percentile = float(np.mean(residual <= residual[-1]) * 100)
    return {
        "symbol": history["symbol"], "years": float(time[-1]),
        "growth": growth, "slope_pct": growth * 100, "swing": swing,
        "longest_excursion": float(longest), "pull": float(pull),
        "verdict": verdict, "winner": winner, "has_mean": has_mean,
        "range_tradeable": bool(verdict == "NOT A GROWTH STOCK" and
                                pull >= CONFIG["strong_pull"] and
                                growth >= CONFIG["range_minimum_slope"]),
        "raw_scores": raw,
        "position_pct": float(np.expm1(residual[-1]) * 100),
        "percentile": percentile,
        "buy_zone": bool(has_mean and residual[-1] < -CONFIG["buy_zone_width"] * swing),
        "pull_label": ("Strong" if pull >= CONFIG["strong_pull"] else
                       "Moderate" if pull >= CONFIG["pull_threshold"] else "Weak"),
        "longest_years": float(duration), "longest_peak_pct": float(peak),
        "typical_swing_pct": float(np.expm1(swing) * 100),
        "intercept": intercept, "slope": slope,
        "origin": dates[0].date().isoformat(),
    }


def normalize_scores(analysis, references):
    missing = [symbol for symbol in REFERENCE_SYMBOLS if symbol not in references]
    if missing:
        raise ValueError("Reference history unavailable: " + ", ".join(missing))
    scores = {}
    for mode in ("steel", "paper"):
        denominator = max(references[symbol]["raw_scores"][mode]
                          for symbol in REFERENCE_SYMBOLS)
        if not np.isfinite(denominator) or denominator <= 0:
            raise ValueError(f"The {mode} reference score has no positive benchmark.")
        scores[mode] = min(100., max(0., 100 * analysis["raw_scores"][mode] / denominator))
    return scores


def fit_winner_channel(history, end_date=None):
    """Keep the three-channel controls, but center them on the specified OLS mean."""
    from mean_reversion_channels import fit_channel
    result = fit_channel(history, end_date=end_date)
    analysis = analyze_winner(history)
    years = np.asarray(
        (pd.to_datetime(result["line_dates"]) - pd.Timestamp(analysis["origin"])).days,
        dtype=float,
    ) / CONFIG["calendar_days"]
    mean_log = analysis["intercept"] + analysis["slope"] * years
    result["intercepts"]["median"] = analysis["intercept"]
    result["lines"]["median"] = np.exp(mean_log).tolist()
    result["lower_buy_zone"] = np.exp(
        mean_log - CONFIG["buy_zone_width"] * analysis["swing"]
    ).tolist()
    result["position_pct"] = analysis["position_pct"]
    return result

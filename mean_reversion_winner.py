"""Recency-weighted, straight-mean excursion scoring for Mean Reversion only."""

import numpy as np
import pandas as pd

from mean_reversion_weights import CONFIG, weighted_fit


def _history_arrays(history):
    prices = np.asarray(history["prices"], dtype=float)
    dates = pd.DatetimeIndex(pd.to_datetime(history["dates"], utc=True)).tz_localize(None).normalize()
    if len(prices) != len(dates) or len(prices) < 2:
        raise ValueError("At least two adjusted daily closes are required.")
    if not np.all(np.isfinite(prices) & (prices > 0)):
        raise ValueError("Adjusted closes must be positive and finite.")
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("History must have distinct ascending dates.")
    return dates, prices


def rolling_trends(history):
    """OLS windows use five calendar years and explicitly exclude the scored close."""
    dates, prices = _history_arrays(history)
    t = np.asarray((dates - dates[0]).days, dtype=float) / CONFIG["calendar_days"]
    y = np.log(prices)
    # Historical helper retained for the archived rolling-model report only.
    # Neither the active scorer nor the chart calls this function.
    starts = dates.searchsorted(dates - pd.DateOffset(years=5))
    indices = np.flatnonzero(dates >= dates[0] + pd.DateOffset(years=5))
    indices = indices[(indices - starts[indices]) >= 2]
    left = starts[indices]
    n = indices - left
    def window_sum(values):
        prefix = np.r_[0., np.cumsum(values)]
        return prefix[indices] - prefix[left]
    sx, sy = window_sum(t), window_sum(y)
    sxx, sxy, syy = window_sum(t*t), window_sum(t*y), window_sum(y*y)
    denominator = sxx - sx*sx/n
    slopes = (sxy - sx*sy/n) / denominator
    intercepts = (sy - slopes*sx) / n
    predictions = intercepts + slopes*t[indices]
    # Population SD of the preceding window's OLS residuals.
    sse = syy - sy*sy/n - slopes*(sxy-sx*sy/n)
    sigma = np.sqrt(np.maximum(0., sse/n))
    return dates, prices, indices, predictions, slopes, intercepts, sigma


def weighted_excursions(residual, weights, dates):
    """20-session smoothing; integrate |gap| * recency weight / 252 per side.

    Zero belongs to neither side. Include unfinished excursions at both ends;
    a price that has not returned must not disappear from the pull calculation.
    """
    smooth = pd.Series(residual).rolling(CONFIG["smoothing_days"], min_periods=1).mean().to_numpy()
    excursions = []
    start, sign = None, 0
    for i, value in enumerate(smooth):
        side = int(np.sign(value))
        if sign and side != sign:
            excursions.append(_excursion(start, i, smooth, weights, dates))
            start, sign = None, 0
        if side and start is None:
            start, sign = i, side
    if start is not None:
        excursions.append(_excursion(start, len(smooth), smooth, weights, dates))
    return excursions


def _excursion(start, stop, smooth, weights, dates):
    values = smooth[start:stop]
    return {
        "opened": dates[start].date().isoformat(),
        "ended": dates[stop-1].date().isoformat(),
        "side": "Above" if values[0] > 0 else "Below",
        "size": float(np.sum(np.abs(values)*weights[start:stop])/CONFIG["trading_days"]),
        "years": float((stop-start)/CONFIG["trading_days"]),
        "maximum_gap_pct": float(np.max(np.abs(np.expm1(values)))*100),
        "ongoing": stop == len(smooth),
    }


def analyze_winner(history):
    fit = weighted_fit(history)
    dates, prices = fit["dates"], fit["prices"]
    years = float(fit["t"][-1])
    has_mean = years >= CONFIG["minimum_history_years"]
    growth = float(np.expm1(fit["slope"]))
    excursions = weighted_excursions(fit["residual"], fit["weights"], dates) if has_mean else []
    longest = max(excursions, key=lambda e: e["size"]) if excursions else None
    area = longest["size"] if longest else None
    pull = 1/(1+area/CONFIG["pull_scale"]) if area is not None else None
    if not has_mean:
        verdict = "NO MEAN YET — not a winner"
    elif pull < CONFIG["minimum_pull"]:
        verdict = "NO RELIABLE MEAN — not a winner"
    elif growth < CONFIG["minimum_growth"]:
        verdict = "NOT A GROWTH STOCK — not a winner"
    else:
        verdict = "WINNER"
    winner = verdict == "WINNER"
    raw = {
        "steel": float(growth*pull*(1+fit["swing"])) if winner else 0.,
        "paper": float(growth*pull/(1+CONFIG["paper_penalty"]*fit["swing"])**
                       CONFIG["paper_exponent"]) if winner else 0.,
    }
    gaps = np.expm1(fit["residual"])
    strength = ("Strong" if pull >= CONFIG["strong_pull"] else
                "Moderate" if pull >= CONFIG["minimum_pull"] else "Weak") if has_mean else "Unavailable"
    return {
        "symbol": history["symbol"], "years": years, "has_mean": has_mean,
        "origin": dates[0].date().isoformat(), "last_date": dates[-1].date().isoformat(),
        "slope": fit["slope"], "intercept": fit["intercept"],
        "growth": growth, "slope_pct": growth*100,
        "swing": fit["swing"], "volatility": fit["volatility"], "drift": fit["drift"],
        "longest_excursion": area, "pull": pull, "pull_strength": strength,
        "excursions": excursions, "largest_excursion": longest,
        "winner": winner, "verdict": verdict, "raw_scores": raw,
        "scores": {"steel": None, "paper": None} if winner else dict(raw),
        "position_pct": float(gaps[-1]*100),
        "percentile": float(100*np.mean(gaps <= gaps[-1]+1e-12)),
        "historical_gaps": gaps.tolist(),
        "trend_dates": dates.strftime("%Y-%m-%d").tolist() if has_mean else [],
        "trend_prices": np.exp(fit["intercept"]+fit["slope"]*fit["t"]).tolist() if has_mean else [],
        "deep_dip": bool(has_mean and fit["residual"][-1] < -CONFIG["buy_zone_sigmas"]*fit["swing"]),
        "range_tradeable": bool(has_mean and not winner and
                               pull >= CONFIG["strong_pull"] and growth >= CONFIG["range_minimum_growth"]),
    }


def normalize_scores(analysis, references=None):
    """Normalize against the complete, fixed reference set, never a partial set."""
    if not analysis["winner"]:
        return dict(analysis["raw_scores"])
    by_symbol = {a["symbol"]: a for a in references or []}
    if not all(symbol in by_symbol for symbol in CONFIG["reference_symbols"]):
        return {"steel": None, "paper": None}
    result = {}
    for key, score in analysis["raw_scores"].items():
        denominator = max(by_symbol[s]["raw_scores"][key] for s in CONFIG["reference_symbols"])
        result[key] = min(100., 100*score/denominator) if denominator > 0 else None
    return result


def fit_winner_channel(history, end_date=None):
    """Compatibility entry point using the same fixed weighted chart as the UI."""
    from mean_reversion_channels import fit_channel
    return fit_channel(history, end_date)

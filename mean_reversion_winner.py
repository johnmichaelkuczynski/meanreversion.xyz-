"""Walk-forward five-year trends and ticker-independent Mean Reversion scores."""
from types import MappingProxyType

import numpy as np
import pandas as pd

from mean_reversion_recovery import recovery_components, recovery_events

CONFIG = MappingProxyType({
    "trend_years": 5,
    "calendar_days": 365.25,
    "trading_days": 252,
    "band_fraction": .10,
    "remaining_gap_fraction": .50,
    "maturity_years": 5,
    "minimum_mature_events": 3,
    "recovery_years": (5, 3, 1),
    "recovery_weights": (.90, .075, .025),
    "minimum_median_growth": .05,
    "minimum_positive_years": .60,
    "minimum_mean_reversion": 60.,
    "growth_scale": .35,
    "steel_base_weight": .75,
    "steel_depth_weight": .25,
    "depth_scale": .50,
    "minimum_mature_downside_events": 3,
    "paper_base_weight": .70,
    "paper_positive_weight": .30,
    "paper_drawdown_penalty": .65,
    "drawdown_sessions": 252,
    "drawdown_quantile": .90,
    "drawdown_scale": .50,
    "dip_gap_threshold": -.10,
    "dip_percentile": 10.,
    "dip_depth_fraction": .75,
    "dip_minimum_recovery": .60,
    "band_sigmas": 2.,
})


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
    starts = dates.searchsorted(dates - pd.DateOffset(years=CONFIG["trend_years"]))
    indices = np.flatnonzero(dates >= dates[0] + pd.DateOffset(years=CONFIG["trend_years"]))
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


def analyze_winner(history):
    dates, prices, indices, trends, slopes, intercepts, sigma = rolling_trends(history)
    base = {
        "symbol": history["symbol"], "years": float((dates[-1]-dates[0]).days/CONFIG["calendar_days"]),
        "has_mean": bool(len(indices)), "origin": dates[0].date().isoformat(),
        "trend_dates": dates[indices].strftime("%Y-%m-%d").tolist(),
        "trend_prices": np.exp(trends).tolist(),
        "trend_slopes": slopes.tolist(), "trend_sigmas": sigma.tolist(),
    }
    if not len(indices):
        return {**base, "winner": False, "verdict": "INSUFFICIENT TREND HISTORY",
                "scores": {"steel": None, "paper": None}, "deep_dip": False,
                "mean_reversion_score": None, "closeness_score": None,
                "recovery_score": None, "mature_events": [], "newer_events": [],
                "mature_count": 0, "newer_count": 0}
    residual = np.log(prices[indices]) - trends
    gaps = np.expm1(residual)
    closeness = float(100*np.mean(np.abs(gaps) <= CONFIG["band_fraction"]))
    events = recovery_events(dates, prices, indices, trends, slopes, CONFIG)
    recovery = recovery_components(events, CONFIG)
    mrs = max(closeness, recovery["recovery_score"] if recovery["recovery_score"] is not None else 0.)
    annual_slopes = np.expm1(slopes)
    median_growth = float(np.median(annual_slopes))
    # Only completed calendar years; do not count an incomplete current year.
    eligible_dates = dates[indices]
    year_end_indices = [i for i in range(len(indices)) if
                        (i == len(indices)-1 or eligible_dates[i+1].year != eligible_dates[i].year)
                        and (eligible_dates[i].year < dates[-1].year or
                             (dates[-1].month == 12 and dates[-1].day == 31))]
    yearly = annual_slopes[year_end_indices]
    positive_fraction = float(np.mean(yearly > 0)) if len(yearly) else None
    high = pd.Series(prices).shift(1).rolling(CONFIG["drawdown_sessions"],
                                             min_periods=CONFIG["drawdown_sessions"]).max()
    drawdowns = np.maximum(0., 1-pd.Series(prices)/high).dropna().to_numpy()
    drawdown90 = float(np.quantile(drawdowns, CONFIG["drawdown_quantile"])) if len(drawdowns) else 0.
    d = min(1., drawdown90/CONFIG["drawdown_scale"])
    g = float(np.clip(median_growth/CONFIG["growth_scale"], 0., 1.))
    m = mrs/100
    base_score = float(100*np.sqrt(g*m))
    steel = base_score*(CONFIG["steel_base_weight"] + CONFIG["steel_depth_weight"]*recovery["depth_bonus"])
    paper = (base_score*(CONFIG["paper_base_weight"] + CONFIG["paper_positive_weight"]*positive_fraction)*
             (1-CONFIG["paper_drawdown_penalty"]*d)) if positive_fraction is not None else None
    winner = bool(median_growth >= CONFIG["minimum_median_growth"] and
                  positive_fraction is not None and positive_fraction >= CONFIG["minimum_positive_years"] and
                  mrs >= CONFIG["minimum_mean_reversion"])
    percentile = float(100*np.mean(gaps <= gaps[-1]))
    depth = -float(gaps[-1])
    matched = [event for event in recovery["mature_events"] if
               event["direction"] == "downside" and
               event["opening_depth"] >= CONFIG["dip_depth_fraction"]*depth]
    dip_recovery = sum(e["recovered"] for e in matched)/len(matched) if matched else None
    deep_dip = bool(gaps[-1] < CONFIG["dip_gap_threshold"] and percentile <= CONFIG["dip_percentile"] and
                    len(matched) >= CONFIG["minimum_mature_downside_events"] and
                    dip_recovery >= CONFIG["dip_minimum_recovery"])
    return {
        **base, **recovery, "winner": winner, "verdict": "WINNER" if winner else "NOT A WINNER",
        "slope": float(slopes[-1]), "intercept": float(intercepts[-1]),
        "growth": float(annual_slopes[-1]), "slope_pct": float(annual_slopes[-1]*100),
        "median_growth": median_growth, "median_growth_pct": median_growth*100,
        "positive_year_fraction": positive_fraction,
        "year_end_slopes": {str(eligible_dates[i].year): float(annual_slopes[i]) for i in year_end_indices},
        "closeness_score": closeness, "mean_reversion_score": float(mrs),
        "base_score": base_score, "scores": {"steel": float(steel), "paper": float(paper) if paper is not None else None},
        "drawdown90": drawdown90, "drawdown_factor": d,
        "position_pct": float(gaps[-1]*100), "percentile": percentile,
        "historical_gaps": gaps.tolist(), "deep_dip": deep_dip,
        "matched_dip_count": len(matched), "matched_dip_recovery_fraction": dip_recovery,
        "swing": float(sigma[-1]),
    }


def normalize_scores(analysis, references=None):
    """Scores are absolute formulas; no ticker/reference-set normalization."""
    return dict(analysis["scores"])


def fit_winner_channel(history, end_date=None):
    """Plot each day's excluded-close rolling fit and extend only the latest fit."""
    dates, prices = _history_arrays(history)
    analysis = analyze_winner(history)
    last = dates[-1]
    end = max(last, pd.Timestamp(end_date).normalize() if end_date else last + pd.DateOffset(years=1))
    log_returns = np.diff(np.log(prices))
    result = {
        "symbol": history["symbol"], "dates": history["dates"], "prices": history["prices"],
        "latest_price": float(prices[-1]), "last_date": last.date().isoformat(),
        "projection_end": end.date().isoformat(), "origin": analysis["origin"],
        "observations": len(prices), "source": history.get("source", "Adjusted daily closes"),
        "drift": float(np.mean(log_returns)*CONFIG["trading_days"]) if len(prices) >= 30 else None,
        "volatility": float(np.std(log_returns, ddof=1)*np.sqrt(CONFIG["trading_days"])) if len(prices) >= 30 else None,
        "line_dates": [], "lines": {"upper": [], "median": [], "lower": []},
        "lower_buy_zone": [], "has_mean": analysis["has_mean"],
    }
    if not analysis["has_mean"]:
        return result
    historical = pd.DatetimeIndex(pd.to_datetime(analysis["trend_dates"]))
    future = pd.date_range(last, end, freq="7D").union(pd.DatetimeIndex([end]))
    future = future[future > last]
    future_log = analysis["intercept"] + analysis["slope"]*np.asarray(
        (future-dates[0]).days, dtype=float)/CONFIG["calendar_days"]
    trend_log = np.r_[np.log(analysis["trend_prices"]), future_log]
    sigma = np.r_[analysis["trend_sigmas"], np.full(len(future), analysis["swing"])]
    offset = CONFIG["band_sigmas"]*sigma
    result.update({
        "line_dates": historical.append(future).strftime("%Y-%m-%d").tolist(),
        "lines": {"upper": np.exp(trend_log+offset).tolist(),
                  "median": np.exp(trend_log).tolist(), "lower": np.exp(trend_log-offset).tolist()},
        "lower_buy_zone": (np.exp(trend_log)*(1-CONFIG["band_fraction"])).tolist(),
        "slope": analysis["slope"], "slope_pct": analysis["slope_pct"],
        "intercepts": {"upper": analysis["intercept"]+CONFIG["band_sigmas"]*analysis["swing"],
                       "median": analysis["intercept"],
                       "lower": analysis["intercept"]-CONFIG["band_sigmas"]*analysis["swing"]},
        "position_pct": analysis["position_pct"],
    })
    return result

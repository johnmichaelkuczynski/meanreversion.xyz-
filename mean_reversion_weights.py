"""Shared seven-year recency weighting for page-one statistics and chart lines."""
from types import MappingProxyType

import numpy as np
import pandas as pd


CONFIG = MappingProxyType({
    "calendar_days": 365.25,
    "trading_days": 252,
    "half_life_years": 7.,
    "minimum_history_years": 5.,
    "minimum_growth": .12,
    "pull_scale": 8.,
    "minimum_pull": .5,
    "strong_pull": .8,
    "smoothing_days": 20,
    "buy_zone_sigmas": .5,
    "range_minimum_growth": -.10,
    "paper_penalty": 3.,
    "paper_exponent": 4,
    "reference_symbols": ("SOXL", "TQQQ", "SOXX", "QQQ", "SPY"),
})


def weighted_std(values, weights):
    """Population SD under normalized observation weights."""
    center = np.average(values, weights=weights)
    return float(np.sqrt(np.average((values-center)**2, weights=weights)))


def weighted_fit(history):
    prices = np.asarray(history["prices"], dtype=float)
    dates = pd.DatetimeIndex(pd.to_datetime(history["dates"], utc=True)).tz_localize(None).normalize()
    if len(prices) != len(dates) or len(prices) < 2:
        raise ValueError("At least two adjusted daily closes are required.")
    if not np.all(np.isfinite(prices) & (prices > 0)):
        raise ValueError("Adjusted closes must be positive and finite.")
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("History must have distinct ascending dates.")
    t = np.asarray((dates-dates[0]).days, dtype=float)/CONFIG["calendar_days"]
    y = np.log(prices)
    weights = .5**((t[-1]-t)/CONFIG["half_life_years"])
    slope, intercept = np.polyfit(t, y, 1, w=np.sqrt(weights))
    residual = y-(intercept+slope*t)
    returns = np.diff(y)
    # Each return receives the weight of its ending observation.
    volatility = (weighted_std(returns, weights[1:])*np.sqrt(CONFIG["trading_days"])
                  if len(prices) >= 30 else None)
    drift = (float(np.average(returns, weights=weights[1:])*CONFIG["trading_days"])
             if len(prices) >= 30 else None)
    return {
        "dates": dates, "prices": prices, "t": t, "weights": weights,
        "slope": float(slope), "intercept": float(intercept),
        "residual": residual, "swing": weighted_std(residual, weights),
        "volatility": volatility, "drift": drift,
    }

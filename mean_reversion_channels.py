"""The existing SOXL channel geometry and hit model, reusable for any ticker.

These channels describe historical prices. They do not supply a replacement
mean-reversion score. That calculation remains separate pending the new logic.
"""
from datetime import date
import math

import numpy as np
import pandas as pd
from scipy.special import log_ndtr, ndtr


CHANNELS = (
    ("upper", "Upper channel", "#E53935"),
    ("median", "Median trend", "#475569"),
    ("lower", "Lower channel", "#43A047"),
)
YEAR_DAYS = 365.25


def _day(value):
    return pd.Timestamp(value).tz_localize(None).normalize()


def fit_channel(history, end_date=None):
    """OLS log slope; median/min/max intercepts, matching SOXL auto channels."""
    prices = np.asarray(history["prices"], dtype=float)
    dates = pd.DatetimeIndex(pd.to_datetime(history["dates"], utc=True)).tz_localize(None).normalize()
    if len(prices) != len(dates) or len(prices) < 2:
        raise ValueError("At least two adjusted daily closes are needed for trend lines.")
    if not np.all(np.isfinite(prices) & (prices > 0)):
        raise ValueError("Adjusted closing prices must be positive and finite.")
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("Price history must have unique dates in ascending order.")
    origin = dates[0]
    years = np.asarray((dates - origin).days, dtype=float) / YEAR_DAYS
    log_prices = np.log(prices)
    centered = years - years.mean()
    denominator = float(centered @ centered)
    if denominator <= 0:
        raise ValueError("Two distinct dates are needed for trend lines.")
    slope = float(centered @ (log_prices - log_prices.mean()) / denominator)
    intercepts = log_prices - slope * years
    offsets = {
        "upper": float(np.max(intercepts)),
        "median": float(np.median(intercepts)),
        "lower": float(np.min(intercepts)),
    }
    last = dates[-1]
    end = (_day(end_date) if end_date is not None else
           max(last, _day(date.today())) + pd.DateOffset(years=10))
    end = max(last, end)
    future = pd.date_range(last, end, freq="7D")
    line_dates = dates.union(future).union(pd.DatetimeIndex([end]))
    line_years = np.asarray((line_dates - origin).days, dtype=float) / YEAR_DAYS
    lines = {}
    for kind, _, _ in CHANNELS:
        with np.errstate(over="ignore", under="ignore"):
            values = np.exp(offsets[kind] + slope * line_years)
        if not np.all(np.isfinite(values) & (values > 0)):
            raise ValueError("The selected projection date exceeds the fitted price range.")
        lines[kind] = values.tolist()
    log_returns = np.diff(log_prices)
    volatility = float(np.std(log_returns, ddof=1) * np.sqrt(252)) if len(prices) >= 30 else None
    drift = float(np.mean(log_returns) * 252) if len(prices) >= 30 else None
    latest_trend_log = offsets["median"] + slope * years[-1]
    return {
        "symbol": history["symbol"],
        "dates": dates.strftime("%Y-%m-%d").tolist(),
        "prices": prices.tolist(),
        "line_dates": line_dates.strftime("%Y-%m-%d").tolist(),
        "lines": lines,
        "slope_pct": float(np.expm1(slope) * 100),
        "position_pct": float(np.expm1(log_prices[-1] - latest_trend_log) * 100),
        "latest_price": float(prices[-1]),
        "last_date": last.date().isoformat(),
        "projection_end": end.date().isoformat(),
        "origin": origin.date().isoformat(),
        "slope": slope,
        "intercepts": offsets,
        "observations": len(prices),
        "drift": drift,
        "volatility": volatility,
        "source": history.get("source", "Adjusted daily history"),
    }


def hit_probability(model, target_price, target_date):
    """Directional first passage to a fixed price by a date, as on SOXL page."""
    try:
        target = float(target_price)
        years = (_day(target_date) - _day(model["last_date"])).days / YEAR_DAYS
    except (TypeError, ValueError, OverflowError):
        return None
    sigma, drift = model.get("volatility"), model.get("drift")
    if (not math.isfinite(target) or target <= 0 or years < 0 or
            sigma is None or drift is None or not math.isfinite(sigma) or
            not math.isfinite(drift) or sigma <= 0):
        return None
    latest = model["latest_price"]
    if target == latest:
        return 1.
    if years == 0:
        return 0.
    direction = 1 if target > latest else -1
    barrier = abs(math.log(target / latest))
    drift = direction * drift
    scale = sigma * math.sqrt(years)
    first = float(ndtr((drift * years - barrier) / scale))
    second_log = 2 * drift * barrier / (sigma * sigma) + float(
        log_ndtr((-drift * years - barrier) / scale))
    second = math.exp(min(0., second_log))
    return min(1., max(0., first + second))


def channel_readout(model, selected_date):
    """All three projected prices and hit probabilities at one shared date."""
    when = _day(selected_date)
    years = (when - _day(model["origin"])).days / YEAR_DAYS
    rows = []
    for kind, label, color in CHANNELS:
        log_price = model["intercepts"][kind] + model["slope"] * years
        try:
            price = math.exp(log_price)
        except OverflowError:
            price = float("inf")
        rows.append({
            "kind": kind, "label": label, "color": color,
            "target_price": price if math.isfinite(price) and price > 0 else None,
            "hit_probability": hit_probability(model, price, when),
        })
    return rows

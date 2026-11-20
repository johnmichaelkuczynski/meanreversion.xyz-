"""The existing SOXL channel geometry and hit model, reusable for any ticker.

These channels describe historical prices. They do not supply a replacement
mean-reversion score. That calculation remains separate pending the new logic.
"""
from datetime import date, timedelta
import math

import numpy as np
import pandas as pd
from scipy.special import log_ndtr, ndtr
from mean_reversion_weights import weighted_fit


CHANNELS = (
    ("upper", "Upper channel", "#E53935"),
    ("median", "Median trend", "#475569"),
    ("lower", "Lower channel", "#43A047"),
)
YEAR_DAYS = 365.25


def _day(value):
    return pd.Timestamp(value).tz_localize(None).normalize()


def _calendar_day(value):
    """Native calendar arithmetic supports horizons beyond pandas' nanoseconds."""
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value.date() if hasattr(value, "date") else value


def fit_channel(history, end_date=None):
    """Weighted straight log mean; parallel full-history envelope lines."""
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
    fit = weighted_fit(history)
    slope = fit["slope"]
    intercepts = log_prices - slope * years
    offsets = {
        "upper": float(np.max(intercepts)),
        "median": fit["intercept"],
        "lower": float(np.min(intercepts)),
    }
    last = dates[-1]
    end = (_calendar_day(end_date) if end_date is not None else
           (max(last, _day(date.today())) + pd.DateOffset(years=10)).date())
    last_day, origin_day = last.date(), origin.date()
    end = max(last_day, end)
    # Straight lines need no daily resampling in distant future space. Bound
    # rendering cost, not the user's requested projection date.
    duration = (end-last_day).days
    step = max(7, math.ceil(duration/2000))
    future = [last_day+timedelta(days=offset) for offset in range(0, duration, step)]
    line_dates = sorted(set(dates.date).union(future, [end]))
    line_years = np.asarray([(day-origin_day).days for day in line_dates], dtype=float) / YEAR_DAYS
    lines = {}
    for kind, _, _ in CHANNELS:
        with np.errstate(over="ignore", under="ignore"):
            values = np.exp(offsets[kind] + slope * line_years)
        if not np.all(np.isfinite(values) & (values > 0)):
            raise ValueError("The selected projection date exceeds the fitted price range.")
        lines[kind] = values.tolist()
    volatility, drift = fit["volatility"], fit["drift"]
    latest_trend_log = offsets["median"] + slope * years[-1]
    return {
        "symbol": history["symbol"],
        "has_mean": True,
        "dates": dates.strftime("%Y-%m-%d").tolist(),
        "prices": prices.tolist(),
        "line_dates": [day.isoformat() for day in line_dates],
        "lines": lines,
        "slope_pct": float(np.expm1(slope) * 100),
        "position_pct": float(np.expm1(log_prices[-1] - latest_trend_log) * 100),
        "latest_price": float(prices[-1]),
        "last_date": last.date().isoformat(),
        "projection_end": end.isoformat(),
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
        years = (_calendar_day(target_date) - _calendar_day(model["last_date"])).days / YEAR_DAYS
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
    when = _calendar_day(selected_date)
    years = (when - _calendar_day(model["origin"])).days / YEAR_DAYS
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

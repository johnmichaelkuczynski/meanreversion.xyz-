"""Independent log-trend / AR(1) research model; existing signals are untouched."""
from datetime import date
import math

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller
from threadpoolctl import threadpool_limits


CONFIG = {
    "strong": {"half_life": 60, "consistency": .6, "pass_rate": .6},
    "moderate": {"half_life": 250, "consistency": .4, "pass_rate": .4},
    "minimum_years": 3,
    "adf_max_lags": 10,
    "window_minimum": 504,
    "window_step": 126,
    "simulation_paths": 20_000,
}


def _fit(prices, dates):
    y = np.log(np.asarray(prices, dtype=float))
    t = np.asarray((dates - dates[0]).days, dtype=float) / 365.2425
    a, g = np.linalg.lstsq(np.column_stack([np.ones(len(t)), t]), y, rcond=None)[0]
    residuals = y - (a + g * t)
    denominator = float(residuals[:-1] @ residuals[:-1])
    phi = float(residuals[:-1] @ residuals[1:] / denominator) if denominator > 1e-20 else 1.
    innovations = residuals[1:] - phi * residuals[:-1]
    sigma = float(np.std(innovations, ddof=1))
    half_life = math.log(2) / -math.log(phi) if 0 < phi < 1 else None
    width = sigma / math.sqrt(1 - phi**2) if 0 < phi < 1 else None
    if np.ptp(y) < 1e-12:
        adf_p = 1.
    else:
        try:
            with threadpool_limits(limits=1):
                adf_p = float(adfuller(
                    y, regression="ct", autolag="AIC",
                    maxlag=min(CONFIG["adf_max_lags"], len(y) // 2 - 3),
                    result_object=False,
                )[1])
        except (ValueError, np.linalg.LinAlgError):
            adf_p = 1.
    passed = adf_p < .05 and half_life is not None and half_life <= len(y) / 20
    return {
        "a": float(a), "g": float(g), "phi": phi, "sigma": sigma,
        "half_life": half_life, "band_width": width, "adf_p": adf_p,
        "gate_passed": bool(passed), "residuals": residuals.tolist(),
    }


def half_life_words(days):
    if days < 10:
        return f"{max(1, round(days))} trading days"
    if days < 60:
        return f"{round(days / 5)} weeks"
    if days < 252:
        return f"{round(days / 21)} months"
    return f"{days / 252:.1f} years"


def analyze(prices, dates, config=None):
    """All inputs must be full-history, positive adjusted closes."""
    config = CONFIG if config is None else {**CONFIG, **config}
    values = np.asarray(prices, dtype=float)
    dates = pd.DatetimeIndex(pd.to_datetime(dates, utc=True)).tz_localize(None).normalize()
    if len(values) != len(dates) or not len(values):
        raise ValueError("No adjusted daily history was found.")
    if not np.all(np.isfinite(values) & (values > 0)):
        raise ValueError("Adjusted prices must be finite and positive.")
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("History must contain unique dates in ascending order.")
    result = {
        "count": len(values), "start": dates[0].date().isoformat(),
        "through": dates[-1].date().isoformat(), "gate_passed": False,
        "half_life": None, "consistency": None, "pass_rate": None,
        "position_pct": None, "percentile": None, "trend_pct": None,
        "residuals": [], "band_width": None,
    }
    if (dates[-1] - dates[0]).days / 365.2425 < config["minimum_years"] or len(values) < 504:
        result.update(status="Not enough history to assess", grade=None, position_text="")
        return result
    result.update(_fit(values, dates))
    residuals = np.array(result["residuals"])
    position = float(np.expm1(residuals[-1]) * 100)
    percentile = float((np.sum(residuals < residuals[-1]) +
                        .5 * np.sum(residuals == residuals[-1])) / len(residuals) * 100)
    trend = float(np.expm1(result["g"]) * 100)
    side = "below" if position < 0 else "above"
    position_text = f"{abs(position):.1f}% {side} trend"
    comparison = (f"lower than {100 - percentile:.0f}% of its history"
                  if position < 0 else f"higher than {percentile:.0f}% of its history")
    result.update(
        position_pct=position, percentile=percentile, trend_pct=trend,
        position_text=position_text, position_sentence=f"{position_text} — {comparison}.",
        trend_sentence=(f"Trend rising {trend:.1f}% per year." if result["g"] > 0 else
                        f"Trend flat or declining ({trend:.1f}% per year)."),
    )
    # Stability is reported even when the full-history gate fails. It cannot
    # override that gate or manufacture a grade.
    half_life = result["half_life"]
    window = max(math.ceil(10 * half_life), config["window_minimum"]) if half_life else config["window_minimum"]
    windows = []
    for start in range(0, len(values) - window + 1, config["window_step"]):
        windows.append(_fit(values[start:start + window], dates[start:start + window]))
    finite = [w["half_life"] for w in windows if w["half_life"] is not None]
    consistency = (float(np.clip(1 - np.std(finite) / np.mean(finite), 0, 1))
                   if finite else None)
    pass_rate = sum(w["adf_p"] < .1 for w in windows) / len(windows) if windows else None
    result.update(consistency=consistency, pass_rate=pass_rate,
                  window_count=len(windows), valid_half_life_windows=len(finite),
                  window_length=window)
    if not result["gate_passed"]:
        result.update(status="Random walk — no reliable trend line to revert to.", grade=None)
        return result
    grade = "Weak"
    for name in ("strong", "moderate"):
        rule = config[name]
        if (half_life <= rule["half_life"] and consistency is not None
                and pass_rate is not None and consistency >= rule["consistency"]
                and pass_rate >= rule["pass_rate"]):
            grade = name.title()
            break
    result.update(
        grade=grade,
        status=f"{grade} — gaps from trend typically close halfway in about {half_life_words(half_life)}.",
    )
    return result


def trend_lines(model, dates):
    times = (pd.DatetimeIndex(dates) - pd.Timestamp(model["start"])).days.to_numpy() / 365.2425
    trend = model["a"] + model["g"] * times
    return {
        "dates": [pd.Timestamp(d).date().isoformat() for d in dates],
        "trend": np.exp(trend).tolist(),
        "upper": np.exp(trend + 2 * model["band_width"]).tolist(),
        "lower": np.exp(trend - 2 * model["band_width"]).tolist(),
    }


def simulate_touches(model, end_date, *, paths=None, seed=7319, today=None):
    """Streaming O(paths) memory, one pass; cumulative two-sided crossings.

    A touch includes crossing in either direction. Initial points exactly on
    a boundary count as already touched, not paths merely on the same side.
    Business days exclude weekends, but not exchange holidays.
    """
    if not model["gate_passed"]:
        return None
    end = pd.Timestamp(end_date).normalize()
    today = pd.Timestamp(today or date.today()).normalize()
    if end <= today:
        raise ValueError("Choose a projection end date after today.")
    last = pd.Timestamp(model["through"])
    dates = pd.bdate_range(last + pd.Timedelta(days=1), end)
    if len(dates) > 252 * 30:
        raise ValueError("Choose a projection end date within 30 years.")
    paths = CONFIG["simulation_paths"] if paths is None else paths
    rng = np.random.default_rng(seed)
    x = np.full(paths, model["residuals"][-1], dtype=float)
    levels = np.array([2 * model["band_width"], 0., -2 * model["band_width"]])
    touched = np.isclose(x[:, None], levels[None, :], rtol=0, atol=1e-14)
    probabilities = np.empty((len(dates), 3))
    for i in range(len(dates)):
        previous = x
        x = model["phi"] * x + rng.normal(0, model["sigma"], paths)
        touched |= ((previous[:, None] - levels) * (x[:, None] - levels)) <= 0
        probabilities[i] = touched.mean(axis=0)
    result = trend_lines(model, dates)
    result["probabilities"] = {key: probabilities[:, i].tolist()
                               for i, key in enumerate(("upper", "trend", "lower"))}
    result["paths"] = paths
    return result

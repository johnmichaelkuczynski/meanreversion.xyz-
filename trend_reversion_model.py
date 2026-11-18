"""Independent log-trend / AR(1) research model; existing signals are untouched."""
from datetime import date
import math

import numpy as np
import pandas as pd


CONFIG = {
    "strong": {"cycles": 8, "half_life": 120},
    "moderate": {"cycles": 6, "half_life": 300},
    "minimum_cycles": 4,
    "random_walk_phi": .9995,
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
    sigma = float(np.std(innovations, ddof=1)) if len(innovations) > 1 else 0.
    half_life = math.log(2) / -math.log(phi) if 0 < phi < 1 else None
    stationary_width = sigma / math.sqrt(1 - phi**2) if abs(phi) < 1 else None
    # Nonstationary fits have no finite AR(1) long-run spread. Keep descriptive
    # bands visible using observed residual dispersion, explicitly labeled.
    width = stationary_width if stationary_width is not None else float(np.std(residuals))
    return {
        "a": float(a), "g": float(g), "phi": phi, "sigma": sigma,
        "half_life": half_life, "band_width": width,
        "band_basis": "AR(1) long-run spread" if stationary_width is not None else "observed residual spread",
        "residuals": residuals.tolist(),
    }


def count_cycles(residuals, width):
    """Count one completed excursion per >1s departure and return through zero."""
    armed = 0
    cycles = 0
    if width <= 1e-12:
        return 0
    for x in residuals:
        if armed and armed * x <= 0:
            cycles += 1
            armed = 0
        if not armed and abs(x) > width:
            armed = 1 if x > 0 else -1
    return cycles


def classify(cycles, phi, half_life, config):
    if cycles < config["minimum_cycles"] or phi >= config["random_walk_phi"]:
        return None
    for name in ("strong", "moderate"):
        rule = config[name]
        if cycles >= rule["cycles"] and half_life is not None and half_life <= rule["half_life"]:
            return name.title()
    return "Weak"


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
        "through": dates[-1].date().isoformat(),
        "half_life": None,
        "position_pct": None, "percentile": None, "trend_pct": None,
        "residuals": [], "band_width": None,
    }
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
    half_life = result["half_life"]
    cycles = count_cycles(residuals, result["band_width"])
    grade = classify(cycles, result["phi"], half_life, config)
    timing = (f"gaps typically close halfway in about {half_life_words(half_life)}"
              if half_life is not None else "no finite positive-AR(1) half-life")
    result.update(
        grade=grade, cycles=cycles, random_walk=grade is None,
        status=(f"{grade} — {cycles} round trips to trend since {dates[0].year}; {timing}."
                if grade else "Random walk — price does not reliably return to its trend line"),
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
    if not abs(model["phi"]) < 1:
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

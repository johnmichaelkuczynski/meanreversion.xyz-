"""Contract tests for the new model, independent of the existing indicators."""
import numpy as np
import pandas as pd
import pytest

from trend_reversion_model import analyze, simulate_touches, trend_lines


@pytest.fixture(scope="module")
def reverting():
    rng = np.random.default_rng(2026)
    n = 20 * 252
    dates = pd.bdate_range("2000-01-03", periods=n)
    residuals = np.zeros(n)
    for i in range(1, n):
        residuals[i] = .97 * residuals[i - 1] + rng.normal(0, .015)
    prices = np.exp(4 + .08 * np.arange(n) / 252 + residuals)
    return analyze(prices, dates), prices, dates


def test_twenty_year_ar1(reverting):
    model, _, _ = reverting
    assert model["gate_passed"]
    assert model["half_life"] == pytest.approx(np.log(2) / -np.log(.97), abs=5)
    assert model["grade"] in ("Strong", "Moderate", "Weak")
    assert 0 <= model["consistency"] <= 1
    assert 0 <= model["pass_rate"] <= 1
    assert model["window_length"] >= 504


def test_random_walk_with_drift():
    rng = np.random.default_rng(12345)
    prices = np.exp(4 + np.cumsum(rng.normal(.0003, .015, 5040)))
    model = analyze(prices, pd.bdate_range("2000-01-03", periods=5040))
    assert not model["gate_passed"]
    assert model["grade"] is None
    assert model["status"] == "Random walk — no reliable trend line to revert to."


def test_short_history_still_has_price_data():
    dates = pd.bdate_range("2025-01-01", periods=200)
    model = analyze(np.linspace(100, 130, 200), dates)
    assert model["status"] == "Not enough history to assess"
    assert not model["gate_passed"]
    assert model["count"] == 200


def test_flat_and_invalid_prices():
    dates = pd.bdate_range("2020-01-01", periods=1000)
    assert not analyze(np.ones(1000), dates)["gate_passed"]
    with pytest.raises(ValueError):
        analyze(np.zeros(1000), dates)


def test_band_formula_and_position(reverting):
    model, prices, dates = reverting
    lines = trend_lines(model, dates)
    np.testing.assert_allclose(np.log(lines["upper"]) - np.log(lines["trend"]),
                               2 * model["band_width"])
    np.testing.assert_allclose(np.log(prices) - np.log(lines["trend"]), model["residuals"])
    assert model["position_pct"] == pytest.approx(
        (prices[-1] / lines["trend"][-1] - 1) * 100)
    assert model["trend_pct"] == pytest.approx(np.expm1(model["g"]) * 100)


def test_monte_carlo_is_cumulative_and_reproducible(reverting):
    model, _, _ = reverting
    # A short deterministic horizon is sufficient for contract checks.
    a = simulate_touches(model, "2019-05-01", today="2019-04-29", paths=500)
    b = simulate_touches(model, "2019-05-01", today="2019-04-29", paths=500)
    assert a == b
    assert a["paths"] == 500
    for series in a["probabilities"].values():
        assert np.all((np.asarray(series) >= 0) & (np.asarray(series) <= 1))
        assert np.all(np.diff(series) >= 0)


def test_crossing_is_not_same_side_occupancy(reverting):
    model = {**reverting[0], "phi": 1., "sigma": 0.}
    model["residuals"] = [.5]
    result = simulate_touches(model, "2019-05-01", today="2019-04-29", paths=10)
    assert all(p == 0 for p in result["probabilities"]["trend"])
    assert all(p == 0 for p in result["probabilities"]["lower"])


def test_failed_gate_has_no_simulation():
    assert simulate_touches({"gate_passed": False}, "2030-01-01") is None

"""Contract tests for the new model, independent of the existing indicators."""
import numpy as np
import pandas as pd
import pytest

from trend_reversion_model import CONFIG, analyze, classify, count_cycles, simulate_touches, trend_lines


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
    assert not model["random_walk"]
    assert model["half_life"] == pytest.approx(np.log(2) / -np.log(.97), abs=5)
    assert model["grade"] in ("Strong", "Moderate", "Weak")
    assert model["cycles"] >= 8
    assert model["band_width"] == pytest.approx(model["sigma"] / np.sqrt(1 - model["phi"] ** 2))
    assert model["cycles"] == count_cycles(model["residuals"], model["band_width"])
    assert "adf_p" not in model


def test_random_walk_with_drift():
    rng = np.random.default_rng(12345)
    prices = np.exp(4 + np.cumsum(rng.normal(.0003, .015, 5040)))
    model = analyze(prices, pd.bdate_range("2000-01-03", periods=5040))
    # This descriptive rule is not a random-walk hypothesis test. A simulated
    # random walk may complete enough in-sample cycles to receive a grade.
    assert model["random_walk"] == (model["cycles"] < 4 or model["phi"] >= .9995)
    assert model["position_sentence"]
    assert model["trend_sentence"]
    assert len(trend_lines(model, ["2030-01-01"])["trend"]) == 1


def test_short_history_still_has_price_data():
    dates = pd.bdate_range("2025-01-01", periods=200)
    model = analyze(np.linspace(100, 130, 200), dates)
    assert model["trend_sentence"]
    assert model["position_sentence"]
    assert len(trend_lines(model, dates)["upper"]) == 200
    assert model["count"] == 200


def test_flat_and_invalid_prices():
    dates = pd.bdate_range("2020-01-01", periods=1000)
    flat = analyze(np.ones(1000), dates)
    assert flat["random_walk"]
    assert flat["cycles"] == 0
    assert np.all(np.isfinite(trend_lines(flat, dates)["upper"]))
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
    model = {**reverting[0], "phi": .999, "sigma": 0.}
    model["residuals"] = [.5]
    result = simulate_touches(model, "2019-05-01", today="2019-04-29", paths=10)
    assert all(p == 0 for p in result["probabilities"]["trend"])
    assert all(p == 0 for p in result["probabilities"]["lower"])


def test_undefined_stationary_spread_has_no_probabilities():
    assert simulate_touches({"phi": 1.}, "2030-01-01") is None


def test_cycles_require_one_s_excursion_then_zero_return():
    # Numerous noise crossings under s are NOT cycles, even though they
    # exceed a hypothetical daily innovation sigma of 0.1.
    assert count_cycles([.2, -.2] * 20, 1.) == 0
    assert count_cycles([1., 0., -1., 0.], 1.) == 0  # strictly exceeds
    assert count_cycles([1.1, 1.3, .3, 0., -.2, -1.2, -.1, .1], 1.) == 2
    assert count_cycles([1.1, .5, .2], 1.) == 0  # unfinished excursion
    assert count_cycles([1.2, -1.2, 1.2, 0.], 1.) == 3


@pytest.mark.parametrize("cycles,phi,half_life,expected", [
    (3, .9, 10, None), (100, .9995, 100, None),
    (8, .9, 120, "Strong"), (8, .9, 120.01, "Moderate"),
    (6, .9, 300, "Moderate"), (6, .9, 300.01, "Weak"),
    (4, .9, 10, "Weak"), (5, .9, 10, "Weak"),
    (8, -.5, None, "Weak"),
])
def test_exact_grade_thresholds(cycles, phi, half_life, expected):
    assert classify(cycles, phi, half_life, CONFIG) == expected


def test_single_close_still_displays_descriptive_lines():
    model = analyze([100.], ["2026-01-01"])
    assert model["trend_pct"] == 0.
    assert model["position_sentence"]
    assert model["random_walk"]
    assert trend_lines(model, ["2027-01-01"])["trend"][0] == pytest.approx(100.)

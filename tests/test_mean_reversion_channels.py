from math import erf, exp, sqrt

import numpy as np
import pandas as pd
import pytest

from mean_reversion_channels import channel_readout, fit_channel, hit_probability


def history(count=600):
    dates = pd.bdate_range("2020-01-02", periods=count)
    years = (dates - dates[0]).days / 365.25
    values = np.exp(3 + .15 * years + .2 * np.sin(np.arange(count) / 24))
    return {"symbol": "TEST", "dates": dates.strftime("%Y-%m-%d").tolist(),
            "prices": values.tolist(), "source": "synthetic test"}


def test_three_channels_are_automatic_and_cover_observed_prices():
    data = history()
    model = fit_channel(data, "2030-11-19")
    assert list(model["lines"]) == ["upper", "median", "lower"]
    assert model["line_dates"][-1] == "2030-11-19"
    mapping = {day: i for i, day in enumerate(model["line_dates"])}
    for day, price in zip(model["dates"], model["prices"]):
        i = mapping[day]
        assert model["lines"]["lower"][i] <= price * (1 + 1e-12)
        assert model["lines"]["upper"][i] >= price * (1 - 1e-12)
        assert model["lines"]["upper"][i] >= model["lines"]["median"][i]
        assert model["lines"]["median"][i] >= model["lines"]["lower"][i]
    assert model["slope_pct"] > 0
    assert "scores" not in model  # Do not reintroduce the rejected score.


def test_readout_matches_the_three_plotted_endpoints():
    model = fit_channel(history(), "2030-11-19")
    rows = channel_readout(model, "2030-11-19")
    assert [row["kind"] for row in rows] == ["upper", "median", "lower"]
    for row in rows:
        assert row["target_price"] == pytest.approx(model["lines"][row["kind"]][-1])
        assert 0 <= row["hit_probability"] <= 1


def test_directional_hits_match_zero_drift_reflection_formula():
    model = {"latest_price": 100, "last_date": "2020-01-01",
             "volatility": .2, "drift": 0}
    years = 366 / 365.25
    z = .2 / (.2 * sqrt(years))
    expected = 1 - erf(z / sqrt(2))
    assert hit_probability(model, 100 * exp(.2), "2021-01-01") == pytest.approx(expected)
    assert hit_probability(model, 100 * exp(-.2), "2021-01-01") == pytest.approx(expected)
    assert hit_probability(model, 90, "2020-01-02") < 1
    assert hit_probability(model, 100, "2020-01-01") == 1
    assert hit_probability(model, 110, "2020-01-01") == 0
    assert hit_probability(model, 100, "2019-12-31") is None


def test_higher_targets_and_shorter_deadlines_are_harder_to_hit():
    model = fit_channel(history())
    assert hit_probability(model, 2 * model["latest_price"], "2030-01-01") <= \
        hit_probability(model, 1.1 * model["latest_price"], "2030-01-01")
    assert hit_probability(model, 2 * model["latest_price"], "2025-01-01") <= \
        hit_probability(model, 2 * model["latest_price"], "2030-01-01")


def test_short_history_still_has_all_lines_without_invented_probabilities():
    model = fit_channel(history(2))
    assert len(model["lines"]) == 3
    assert all(row["hit_probability"] is None for row in channel_readout(model, "2030-01-01"))


@pytest.mark.parametrize("prices", [[0, 10], [10, float("nan")], [10, -1]])
def test_bad_prices_fail_explicitly(prices):
    data = history(2)
    data["prices"] = prices
    with pytest.raises(ValueError):
        fit_channel(data)


def test_channels_match_existing_soxl_log10_algorithm():
    data = history()
    model = fit_channel(data, "2030-01-01")
    times = np.asarray((pd.to_datetime(data["dates"]) - pd.Timestamp(data["dates"][0])).days, float)
    transformed = np.log10(data["prices"])
    slope = ((times - times.mean()) @ (transformed - transformed.mean()) /
             ((times - times.mean()) @ (times - times.mean())))
    intercepts = transformed - slope * times
    duration = (pd.Timestamp("2030-01-01") - pd.Timestamp(data["dates"][0])).days
    for kind, intercept in [("upper", max(intercepts)), ("median", np.median(intercepts)),
                            ("lower", min(intercepts))]:
        assert model["lines"][kind][-1] == pytest.approx(10 ** (intercept + slope * duration))

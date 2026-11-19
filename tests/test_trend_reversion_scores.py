"""Exact scorecard formulas; no changes to the existing reversion verdict."""
import math

import numpy as np
import pytest

from trend_reversion_model import CONFIG, analyze, score_model


def model(**changes):
    return {
        "start": "2000-01-01", "through": "2020-01-01",
        "cycles": 9, "half_life": 117., "random_walk": False,
        "g": math.log(1.2), **changes,
    }


def test_exact_formulas_and_round_only_at_end():
    m = model()
    result = score_model(m)
    years = 7305 / 365.2425
    rate = 9 / years * 10
    reversion = 100 * min(1, rate / 6) * math.exp(-117 / 250)
    growth = 100 * (math.exp(m["g"]) - 1) / .40
    overall = math.sqrt(reversion * growth)
    assert result["cycles_per_decade"] == pytest.approx(rate)
    assert result["scores_raw"] == pytest.approx({
        "mean_reversion": reversion, "growth": growth, "overall": overall})
    assert result["scores"] == {
        "mean_reversion": round(reversion), "growth": round(growth), "overall": round(overall)}


@pytest.mark.parametrize("g,expected", [(0, 0), (-.1, 0), (math.log(1.4), 100),
                                      (math.log(2), 100)])
def test_growth_limits(g, expected):
    result = score_model(model(g=g))
    assert result["scores"]["growth"] == expected
    if expected == 0:
        assert result["scores"]["overall"] == 0


def test_random_walk_zeroes_reversion_not_growth():
    result = score_model(model(random_walk=True, g=math.log(1.5)))
    assert result["scores"] == {"mean_reversion": 0, "growth": 100, "overall": 0}


def test_cycle_component_saturates_and_half_life_penalizes():
    low = score_model(model(cycles=1))
    high = score_model(model(cycles=100))
    higher = score_model(model(cycles=1000))
    slow = score_model(model(cycles=100, half_life=500))
    assert low["scores"]["mean_reversion"] < high["scores"]["mean_reversion"]
    assert high["scores"] == higher["scores"]
    assert slow["scores"]["mean_reversion"] < high["scores"]["mean_reversion"]


def test_undefined_half_life_and_zero_history_are_explicit():
    assert score_model(model(half_life=None))["score_note"]
    assert score_model(model(half_life=None))["scores"]["overall"] == 0
    assert score_model(model(through="2000-01-01"))["cycles_per_decade"] == 0


def test_config_constants_control_scores():
    m = model(cycles=100)
    result = score_model(m, {"score_half_life_days": 117, "score_growth_rate": .2})
    assert result["scores"]["mean_reversion"] == round(100 / math.e)
    assert result["scores"]["growth"] == 100
    assert CONFIG["score_cycles_per_decade"] == 6


def test_analyze_attaches_scorecard_without_hiding_random_walk():
    prices = np.ones(100)
    dates = np.arange("2020-01-01", "2020-04-10", dtype="datetime64[D]")
    result = analyze(prices, dates)
    assert result["random_walk"]
    assert result["scores"]["mean_reversion"] == result["scores"]["overall"] == 0
    assert result["position_sentence"] and result["trend_sentence"] and result["cycle_sentence"]

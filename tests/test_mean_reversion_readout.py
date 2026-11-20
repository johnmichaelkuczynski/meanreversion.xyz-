from datetime import date
import math

from mean_reversion_readout import dated_position, summary_lines


def analysis(**changes):
    value = {"has_mean": True, "pull": .8, "pull_label": "Strong",
             "slope": .1, "slope_pct": math.expm1(.1) * 100,
             "intercept": math.log(100), "origin": "2020-01-01"}
    return {**value, **changes}


def test_dated_position_uses_actual_close_and_same_date_mean():
    history = {"dates": ["2020-01-01", "2020-01-03"], "prices": [80, 120]}
    day, value = dated_position(history, analysis(), date(2020, 1, 4))
    assert day == "2020-01-03"
    expected = (120 / (100 * math.exp(.1 * 2 / 365.25)) - 1) * 100
    assert abs(value - expected) < 1e-10
    assert dated_position(history, analysis(), date(2020, 1, 1))[1] < 0


def test_separate_growth_and_reversion_facts_and_explicit_missing_scores():
    lines = dict(summary_lines(analysis(pull=.2, pull_label="Weak"), None, ("2026-11-19", -25)))
    assert lines["Mean reverting"] == "No — weak pull"
    assert lines["Mean trends up"] == "Yes"
    assert lines["Position on 2026-11-19"] == "25.0% BELOW the mean trend line"
    assert "Unavailable" in lines["Mean reversion + growth score · Steel hands"]
    assert "\n" not in "".join(lines.values())


def test_insufficient_history_does_not_claim_a_mean_or_direction():
    lines = dict(summary_lines(analysis(has_mean=False), {"steel": 0, "paper": 0}, None))
    assert lines["Mean reverting"].startswith("Not established")
    assert lines["Mean trends up"] == "Not established"
    assert lines["Mean trend growth"] == "Not established"
    assert "no established mean" in lines["Position"]


def test_flat_or_declining_mean_is_not_reported_as_rising():
    for slope in (0, -.1):
        lines = dict(summary_lines(analysis(slope=slope), {"steel": 0, "paper": 0}, ("2026-11-19", 10)))
        assert lines["Mean trends up"] == "No"
        assert lines["Position on 2026-11-19"] == "10.0% ABOVE the mean trend line"

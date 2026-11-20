from datetime import date
import pytest
from mean_reversion_readout import dated_position, summary_lines
from mean_reversion_winner import analyze_winner
from test_mean_reversion_winner import history


def test_dated_position_uses_that_days_fit_not_the_latest_fit():
    h = history()
    a = analyze_winner(h)
    selected = date.fromisoformat(a["trend_dates"][200])
    day, gap, percentile = dated_position(h, a, selected)
    assert day == selected.isoformat()
    assert gap == pytest.approx(a["historical_gaps"][200]*100)
    assert 0 <= percentile <= 100
    with pytest.raises(ValueError):
        dated_position(h, a, date.fromisoformat(h["dates"][0]))


def test_key_facts_and_dip_are_separate_one_line_each():
    h = history()
    a = analyze_winner(h)
    position = dated_position(h, a, date.fromisoformat(h["dates"][-1]))
    facts = dict(summary_lines(a, a["scores"], position))
    for key in ("Mean Reversion Score", "Closeness", "Recovery score",
                "Median annualized trend slope", "Positive year-end slopes",
                "Steel hands score", "Paper hands score", "Deep-dip flag"):
        assert key in facts
    assert "\n" not in "".join(facts.values())
    a["winner"] = False
    a["deep_dip"] = True
    assert dict(summary_lines(a, a["scores"], position))["Deep-dip flag"] == "YES"


def test_insufficient_recovery_uses_closeness_not_missing_or_zero_score():
    h = history(width=.001)
    a = analyze_winner(h)
    facts = dict(summary_lines(a, a["scores"], dated_position(h, a, date.fromisoformat(h["dates"][-1]))))
    assert facts["Recovery score"] == "Insufficient recovery history"
    assert a["mean_reversion_score"] == 100


def test_insufficient_trend_history_is_explicit():
    a = analyze_winner(history(years=4))
    assert "five preceding years" in dict(summary_lines(a, a["scores"], None))["Trend"]

from datetime import date
import pytest
from mean_reversion_readout import dated_position, chart_position, summary_lines
from mean_reversion_winner import analyze_winner
from test_mean_reversion_winner import history


def test_dated_position_uses_the_same_fixed_weighted_mean():
    h = history()
    a = analyze_winner(h)
    selected = date.fromisoformat(a["trend_dates"][200])
    day, gap, percentile = dated_position(h, a, selected)
    assert day == selected.isoformat()
    assert gap == pytest.approx(a["historical_gaps"][200]*100)
    assert 0 <= percentile <= 100
    assert dated_position(h, a, date.fromisoformat(h["dates"][0]))[0] == h["dates"][0]


def test_key_facts_and_dip_are_separate_one_line_each():
    h = history()
    a = analyze_winner(h)
    position = dated_position(h, a, date.fromisoformat(h["dates"][-1]))
    facts = dict(summary_lines(a, a["scores"], position))
    for key in ("Pull", "Weighted excursion size L", "Weighted swing W",
                "Mean trend growth", "Weighted annualized volatility",
                "Steel hands score", "Paper hands score", "Deep-dip flag"):
        assert key in facts
    assert "\n" not in "".join(facts.values())
    a["winner"] = False
    a["deep_dip"] = True
    assert dict(summary_lines(a, a["scores"], position))["Deep-dip flag"] == "YES"


def test_mean_hugging_series_has_strong_pull_without_crossing_count_gate():
    h = history(width=.001)
    a = analyze_winner(h)
    facts = dict(summary_lines(a, a["scores"], dated_position(h, a, date.fromisoformat(h["dates"][-1]))))
    assert facts["Pull"].startswith("Strong")
    assert a["pull"] > .99
    assert not any("recovery" in label.lower() for label in facts)


def test_insufficient_trend_history_is_explicit():
    a = analyze_winner(history(years=4))
    assert "five years" in dict(summary_lines(a, a["scores"], None))["Trend"]


def test_priority_readout_escapes_identity_and_keeps_unavailable_facts_explicit():
    from streamlit.testing.v1 import AppTest
    script = """
from mean_reversion_readout import render_stock_readout
render_stock_readout({"symbol": "<BAD>"}, "<script>untrusted</script>", None, None)
"""
    app = AppTest.from_string(script).run()
    assert not app.exception
    facts = next(m.value for m in app.markdown
                 if '<section class="mr-priority-readout"' in m.value)
    assert "TICKER: &lt;BAD&gt;" in facts
    assert "&lt;script&gt;untrusted&lt;/script&gt;" in facts
    assert "<script>untrusted</script>" not in facts
    assert "Verdict: UNAVAILABLE" in facts
    assert "Pull: Insufficient" in facts
    assert "Annualized slope: Insufficient" in facts


def test_visible_position_matches_the_fixed_straight_mean_on_the_chart():
    from mean_reversion_channels import fit_channel
    h = history()
    model = fit_channel(h, "2126-11-19")
    selected = date.fromisoformat(h["dates"][-200])
    day, gap, percentile = chart_position(h, model, selected)
    index = model["line_dates"].index(day)
    price_index = h["dates"].index(day)
    assert gap == pytest.approx((h["prices"][price_index]/model["lines"]["median"][index]-1)*100)
    assert 0 <= percentile <= 100

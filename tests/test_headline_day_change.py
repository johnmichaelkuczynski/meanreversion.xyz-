import pytest

from mean_reversion_readout import headline_day_change


def quote(price=40.144, prev_close=30.88, observed_at="2026-11-23T19:00:00Z"):
    return {"price": price, "prev_close": prev_close, "observed_at": observed_at}


def test_live_gain_uses_the_provider_previous_close_not_old_adjusted_history():
    history = {"prices": [100, 200], "dates": ["2026-11-19", "2026-11-20"]}
    text, context = headline_day_change(history, quote())
    assert text == "Day change: +30.00% (+$9.26)"
    assert "2026-11-23" in context
    assert "previous trading day's close" in context


@pytest.mark.parametrize("price, expected", [
    (90, "Day change: -10.00% (−$10.00)"),
    (100, "Day change: +0.00% (+$0.00)"),
    (110, "Day change: +10.00% (+$10.00)"),
])
def test_declines_flat_days_and_gains(price, expected):
    assert headline_day_change({}, quote(price, 100))[0] == expected


def test_closed_market_without_quote_uses_last_completed_trading_day():
    text, context = headline_day_change(
        {"prices": [45.30, 30.88], "dates": ["2026-11-19", "2026-11-20"]}, None
    )
    assert text == "Day change: -31.83% (−$14.42)"
    assert context == "2026-11-20 · close-to-close"


def test_observation_date_uses_new_york_not_utc_or_today():
    _, context = headline_day_change(
        {}, quote(observed_at="2026-11-24T00:55:00Z")
    )
    assert context.startswith("2026-11-23")


@pytest.mark.parametrize("baseline", [None, 0, -1, float("nan"), float("inf"), True])
def test_missing_or_invalid_quote_baseline_never_uses_adjusted_history(baseline):
    history = {"prices": [10, 20], "dates": ["2026-11-19", "2026-11-20"]}
    text, context = headline_day_change(history, quote(prev_close=baseline))
    assert text == "Day change: unavailable"
    assert "Previous close unavailable" in context


def test_numeric_string_previous_close_from_provider():
    assert headline_day_change({}, quote(prev_close="30.88"))[0].startswith(
        "Day change: +30.00%"
    )


def test_missing_history_does_not_invent_a_daily_change():
    assert headline_day_change({}, None)[0] == "Day change: unavailable"
    assert headline_day_change({"prices": [10], "dates": ["2026-11-20"]}, None)[0] == "Day change: unavailable"


def test_missing_quote_timestamp_does_not_mislabel_the_day():
    assert headline_day_change({}, {"price": 40, "prev_close": 30})[0] == "Day change: unavailable"


def test_daily_change_is_visible_near_top_of_primary_readout(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import mean_reversion_readout
    monkeypatch.setattr(mean_reversion_readout, "_current_quote", lambda symbol: quote())
    app = AppTest.from_string("""
from mean_reversion_readout import render_stock_readout
render_stock_readout({"symbol": "SOXL", "prices": [30.88],
                     "dates": ["2026-11-20"]}, "SOXL company", None, None)
""").run()
    assert not app.exception
    html = next(m.value for m in app.markdown if '<section class="mr-priority-readout"' in m.value)
    assert html.index("Current price:") < html.index("Day change: +30.00% (+$9.26)") < html.index("Company:")
    assert 'class="mr-fact mr-day-change"' in html
    assert "2026-11-23" in html

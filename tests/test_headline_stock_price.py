from mean_reversion_readout import headline_price


def test_current_quote_takes_precedence_over_daily_close():
    history = {"prices": [100.0], "dates": ["2026-11-20"]}
    quote = {"price": 1234.56, "source": "Tiingo",
             "observed_label": "Nov 22, 2026 10:00:00 AM ET"}
    label, stamp = headline_price(history, quote)
    assert label == "Current price: $1,234.56"
    assert "Tiingo" in stamp and quote["observed_label"] in stamp


def test_history_fallback_is_explicitly_not_a_live_quote():
    label, stamp = headline_price(
        {"prices": [42.125], "dates": ["2026-11-20"]}, None
    )
    assert label == "Latest close: $42.12"
    assert "2026-11-20" in stamp and "Not a live quote" in stamp


def test_missing_price_is_not_invented():
    assert headline_price({}, None) == ("Current price: unavailable", "")


def test_invalid_quote_is_not_displayed_as_a_current_price():
    for invalid in (float("nan"), float("inf"), -1, 0):
        label, _ = headline_price(
            {"prices": [42.0], "dates": ["2026-11-20"]}, {"price": invalid}
        )
        assert label == "Latest close: $42.00"


def test_price_is_directly_under_ticker(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import mean_reversion_readout
    monkeypatch.setattr(mean_reversion_readout, "_current_quote",
                        lambda symbol: {"price": 270.25, "source": "Tiingo",
                                        "observed_at": "2026-11-20T21:00:00Z"})
    app = AppTest.from_string("""
from mean_reversion_readout import render_stock_readout
render_stock_readout({"symbol": "ADI", "prices": [260.0],
                     "dates": ["2026-11-20"]}, "Analog Devices", None, None)
""").run()
    assert not app.exception
    html = next(m.value for m in app.markdown if '<section class="mr-priority-readout"' in m.value)
    assert html.index("TICKER: ADI") < html.index("Current price: $270.25") < html.index("Company: Analog Devices")

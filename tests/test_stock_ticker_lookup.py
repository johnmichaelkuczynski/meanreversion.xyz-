"""Real-provider contract and the compact company-name lookup interaction."""

from unittest.mock import Mock, patch

import pytest
import requests
from streamlit.testing.v1 import AppTest

from stock_ticker_lookup import search_stock_tickers, TickerLookupUnavailable


@pytest.fixture(autouse=True)
def clear_search_cache():
    search_stock_tickers.clear()
    yield
    import stock_ticker_lookup
    stock_ticker_lookup.search_stock_tickers = search_stock_tickers
    search_stock_tickers.clear()


def response(rows):
    return Mock(json=Mock(return_value=rows), raise_for_status=Mock())


def test_company_name_search_uses_real_provider_and_filters_inactive(monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", "test-only")
    rows = [
        {"ticker": "dis", "name": "Walt Disney Co.", "assetType": "Stock", "isActive": True},
        {"ticker": "OLD", "name": "Old Disney", "assetType": "Stock", "isActive": False},
        {"ticker": "DIS", "name": "Duplicate", "assetType": "Stock"},
        {"ticker": "<bad>", "name": "Invalid"},
        {"ticker": "BTCUSD", "name": "Bitcoin", "assetType": "Crypto"},
    ]
    with patch("stock_ticker_lookup.requests.get", return_value=response(rows)) as get:
        assert search_stock_tickers("Disney") == [{"symbol": "DIS", "name": "Walt Disney Co."}]
        search_stock_tickers("Disney")
        get.assert_called_once()
        assert get.call_args.kwargs["params"] == {"query": "Disney"}


def test_exact_ticker_first_and_results_bounded(monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", "test-only")
    rows = [{"ticker": f"ABC{i}", "name": f"Company {i}"} for i in range(12)]
    rows.append({"ticker": "ABC", "name": "Exact ticker"})
    with patch("stock_ticker_lookup.requests.get", return_value=response(rows)):
        found = search_stock_tickers("abc")
    assert len(found) == 8
    assert found[0]["symbol"] == "ABC"


@pytest.mark.parametrize("query", ["", "D", " " * 10, "x" * 81])
def test_invalid_query_makes_no_network_request(query):
    with patch("stock_ticker_lookup.requests.get") as get:
        with pytest.raises(ValueError):
            search_stock_tickers(query)
        get.assert_not_called()


@pytest.mark.parametrize("failure", [
    requests.Timeout("provider timeout"),
    requests.HTTPError("provider failure"),
])
def test_provider_failure_is_explicit_and_can_be_retried(monkeypatch, failure):
    monkeypatch.setenv("TIINGO_API_KEY", "test-only")
    with patch("stock_ticker_lookup.requests.get", side_effect=failure):
        with pytest.raises(TickerLookupUnavailable):
            search_stock_tickers("Disney")
    with patch("stock_ticker_lookup.requests.get", return_value=response([])):
        assert search_stock_tickers("Disney") == []


def test_unexpected_response_is_not_reported_as_no_matches(monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", "test-only")
    with patch("stock_ticker_lookup.requests.get", return_value=response({"error": "unavailable"})):
        with pytest.raises(TickerLookupUnavailable):
            search_stock_tickers("Disney")


UI_SCRIPT = """
import streamlit as st
import stock_ticker_lookup as lookup
def search(query):
    st.session_state['search_calls'] = st.session_state.get('search_calls', 0) + 1
    if query == 'error':
        raise lookup.TickerLookupUnavailable()
    return [] if query == 'unknown' else [{'symbol':'DIS','name':'Walt Disney Co.'}]
lookup.search_stock_tickers = search
def select(symbol):
    st.session_state['selected_ticker'] = symbol
lookup.render_ticker_lookup(select)
st.text_input('Enter stock ticker', key='original_ticker')
"""


def test_lookup_shows_real_results_and_selection_without_touching_original_input():
    app = AppTest.from_string(UI_SCRIPT).run()
    assert not app.exception
    assert "search_calls" not in app.session_state
    assert app.text_input[0].label == "Find a stock ticker by company name"
    app.text_input(key="mr_ticker_lookup_query").input("Disney")
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["search_calls"] == 1
    assert app.button[1].label == "DIS — Walt Disney Co."
    assert app.text_input(key="original_ticker").value == ""
    app.button[1].click().run()
    assert app.session_state["selected_ticker"] == "DIS"
    assert app.session_state["search_calls"] == 1


@pytest.mark.parametrize("query, message", [
    ("unknown", "No matching stocks found"),
    ("error", "temporarily unavailable"),
])
def test_lookup_empty_and_failure_states_leave_ticker_entry_available(query, message):
    app = AppTest.from_string(UI_SCRIPT).run()
    app.text_input(key="mr_ticker_lookup_query").input(query)
    app.button[0].click().run()
    assert not app.exception
    assert message in app.info[0].value
    assert app.text_input(key="original_ticker").value == ""

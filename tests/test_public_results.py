from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

import mean_reversion_workspace as workspace
from public_results import preview_payload, preview_figure


HISTORY = {
    "symbol": "AAPL",
    "dates": [(date(2020, 1, 1) + timedelta(days=n)).isoformat() for n in range(200)],
    "prices": [100.0 + n for n in range(200)],
    "through": "2020-07-18",
}
ANALYSIS = {
    "has_mean": True, "verdict": "WINNER", "pull_strength": "Strong",
    "slope_pct": 77.123456, "pull": .987654321,
    "steel": 96.123456, "paper": 87.654321,
    "trend_prices": [99999999], "historical_gaps": [987654321],
}


def test_public_payload_whitelists_only_partial_data():
    payload = preview_payload(HISTORY, ANALYSIS, "Apple")
    assert set(payload) == {
        "symbol", "company", "last_price", "through", "verdict", "pull_strength",
        "trend", "dates", "prices",
    }
    assert len(payload["dates"]) == len(payload["prices"]) == 90
    assert payload["prices"] == HISTORY["prices"][-90:]
    assert payload["verdict"] == "WINNER"
    assert payload["trend"] == "UP"
    assert "77.123456" not in str(payload)
    assert "0.987654321" not in str(payload)


def test_public_chart_contains_no_model_or_hidden_paid_traces():
    fig = preview_figure(preview_payload(HISTORY, ANALYSIS)).to_plotly_json()
    assert len(fig["data"]) == 1
    assert len(fig["data"][0]["x"]) == 90
    assert "customdata" not in fig["data"][0]
    assert not fig["layout"].get("shapes")
    assert not fig["layout"].get("annotations")


def test_public_stock_lookup_updates_real_partial_result_without_paid_rendering(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    script = """
import streamlit as st
import mean_reversion_workspace as w
if "mr_workspace_primary" not in st.session_state:
    st.session_state["mr_workspace_primary"] = w._load_history("AAPL")
w.render_mean_reversion_workspace()
"""
    def history(symbol):
        return dict(HISTORY, symbol=symbol)
    with patch.object(workspace, "has_paid_access", return_value=False), \
         patch.object(workspace, "_load_history", side_effect=history), \
         patch.object(workspace, "analyze_winner", return_value=ANALYSIS), \
         patch.object(workspace, "_cached_company_name", return_value="Test company"), \
         patch.object(workspace, "_cached_channel", side_effect=AssertionError("Full channel ran")), \
         patch.object(workspace, "_cached_reference_analyses", side_effect=AssertionError("Full scores ran")), \
         patch.object(workspace, "render_channel_chart", side_effect=AssertionError("Full chart sent")), \
         patch.object(workspace, "_render_winner_analysis", side_effect=AssertionError("Full analysis sent")), \
         patch.object(workspace, "render_illustrated_rankings", side_effect=AssertionError("Full rankings sent")), \
         patch.object(workspace, "render_unlock_prompt"):
        app = AppTest.from_string(script).run()
        assert not app.exception
        assert any("TICKER: AAPL" in x.value for x in app.markdown)
        assert any("REDACTED" in x.value for x in app.markdown)
        app.text_input(key="mr_workspace_top_primary_input").set_value("MSFT").run()
        assert not app.exception
        assert app.session_state["mr_workspace_primary"]["symbol"] == "MSFT"
        assert any("TICKER: MSFT" in x.value for x in app.markdown)
        assert not any("77.123456" in x.value for x in app.markdown)


def test_soxl_stops_unpaid_execution_before_full_chart_and_advanced_tabs():
    source = Path("app.py").read_text()
    public_branch = source.index("if not has_paid_access():")
    assert public_branch < source.index("render_landing_signal(")
    assert "render_soxl_preview(data)\n    st.stop()" in source

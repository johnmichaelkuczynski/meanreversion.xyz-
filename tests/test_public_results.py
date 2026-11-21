from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import mean_reversion_workspace as workspace
import mean_reversion_chart as chart
from mean_reversion_channels import fit_channel
from mean_reversion_winner import analyze_winner
from public_results import historical_channel, redacted_channel_rows


HISTORY = {
    "symbol": "AAPL",
    "dates": [(date(2020, 1, 1) + timedelta(days=n)).isoformat() for n in range(200)],
    "prices": [100.0 + n for n in range(200)],
    "through": "2020-07-18",
}


def test_public_chart_retains_original_log_history_and_three_straight_lines():
    model = fit_channel(HISTORY, end_date="2027-01-01")
    selected = date(2027, 1, 1)
    with patch.object(workspace, "hit_probability", side_effect=AssertionError("Paid probability ran")):
        fig = workspace._make_figure(
            HISTORY, [], model, redacted_channel_rows(selected), redacted=True,
        ).to_plotly_json()
    assert fig["layout"]["yaxis"]["type"] == "log"
    assert fig["layout"]["height"] == 520
    assert len(fig["data"][0]["x"]) == len(HISTORY["dates"])
    assert list(fig["data"][0]["x"]) == HISTORY["dates"]
    assert {trace["name"] for trace in fig["data"]} >= {
        "AAPL · actual", "Upper trend", "Mean trend", "Lower trend",
    }
    for trace in fig["data"]:
        assert max(trace["x"]) <= HISTORY["dates"][-1]
        if trace["name"].endswith("trend"):
            assert all(row[1:] == ["REDACTED"] * 6 for row in trace["customdata"])
            assert trace["line"]["dash"] == "solid"


def test_public_model_and_panel_never_forward_future_prices_or_probabilities():
    model = fit_channel(HISTORY, end_date="2027-01-01")
    public = historical_channel(model)
    assert set(public) == {"last_date", "line_dates", "lines"}
    assert max(public["line_dates"]) == HISTORY["dates"][-1]
    rows = redacted_channel_rows(date(2027, 1, 1))
    assert len(rows) == 3
    assert all(r["target_price"] == "REDACTED" and r["hit_probability"] is None
               and r["probability_text"] == "REDACTED" for r in rows)
    figure = workspace._make_figure(HISTORY, [], model, rows, redacted=True)
    with patch.object(chart, "_channel_panel") as component:
        chart.render_channel_chart(figure, HISTORY, model, rows, date(2027, 1, 1), redacted=True)
        args = component.call_args.kwargs
    assert args["key"].endswith("_redacted")
    assert args["rows"] == rows
    assert "model" not in args and "intercepts" not in args


def test_public_ticker_uses_original_readout_and_chart_with_only_paid_values_redacted(monkeypatch):
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
         patch.object(workspace, "_cached_company_name", return_value="Test company"), \
         patch.object(workspace, "_cached_reference_analyses", side_effect=AssertionError("Full scores ran")), \
         patch.object(workspace, "render_channel_chart") as component, \
         patch.object(workspace, "render_illustrated_rankings", side_effect=AssertionError("Full rankings sent")), \
         patch.object(workspace, "render_unlock_prompt"):
        app = AppTest.from_string(script).run()
        assert not app.exception
        readout = next(x.value for x in app.markdown if 'class="mr-priority-readout"' in x.value)
        for label in ("TICKER: AAPL", "Steel hands: REDACTED", "Paper hands: REDACTED",
                      "Mean trend:", "Annualized slope: REDACTED", "Position: REDACTED"):
            assert label in readout
        assert not any('<section class="zhi-preview-readout"' in x.value for x in app.markdown)
        assert not app.date_input(key="mr_workspace_projection_date").disabled
        assert component.call_args.kwargs["redacted"] is True
        assert len(component.call_args.args[0].data[0].x) == len(HISTORY["dates"])
        app.text_input(key="mr_workspace_top_primary_input").set_value("MSFT").run()
        assert not app.exception
        assert app.session_state["mr_workspace_primary"]["symbol"] == "MSFT"
        assert any("TICKER: MSFT" in x.value for x in app.markdown)


def test_original_score_sections_keep_controls_but_redact_every_private_value():
    script = """
import math
from datetime import date, timedelta
from mean_reversion_winner import analyze_winner
from mean_reversion_readout import render_score_details
h = {"symbol":"TEST", "dates":[(date(2010,1,1)+timedelta(days=i)).isoformat() for i in range(2600)],
     "prices":[100*math.exp(i*.0005+.2*math.sin(i/40)) for i in range(2600)]}
render_score_details(analyze_winner(h), None, "style", h, redacted=True)
"""
    app = AppTest.from_string(script).run()
    assert not app.exception
    assert len(app.radio) == 1
    assert all(metric.value == "REDACTED" for metric in app.metric)
    assert {e.label for e in app.expander} == {
        "Additional model facts", "Method and weighted excursions",
    }
    for table in app.dataframe:
        assert (table.value == "REDACTED").all().all()


def test_soxl_uses_the_original_readout_and_channel_not_a_short_sparkline():
    source = Path("public_results.py").read_text()
    assert "render_stock_readout(" in source
    assert "render_channel_chart(" in source
    assert "preview_figure" not in source and "[-90:]" not in source
    app_source = Path("app.py").read_text()
    assert "render_soxl_preview(data)\n    st.stop()" in app_source

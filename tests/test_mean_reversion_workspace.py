"""Chart-first layout and immediate removal without market requests in tests."""
import ast
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


SCRIPT = """
import mean_reversion_workspace as workspace
import pandas as pd
import numpy as np
def fixture_history(symbol):
    if symbol == "BAD":
        raise ValueError("No daily price history was found for BAD.")
    dates = pd.bdate_range(end="2026-11-18", periods=3024)
    values = np.exp(4 + .002*np.arange(3024) + .1*np.sin(np.arange(3024)/10))
    if symbol == "AAPL":
        values *= 2
    elif symbol == "MSFT":
        values *= 3
    elif symbol == "VWAV":
        dates, values = dates[-342:], values[-342:]/5
    return {"symbol": symbol, "dates": dates.strftime("%Y-%m-%d").tolist(),
            "prices": values.tolist(), "through": "2026-11-18", "source": "test fixture"}
workspace._cached_stock_history = fixture_history
workspace._cached_company_name = lambda s: {"AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation"}.get(s, s + " security")
workspace.render_mean_reversion_workspace()
"""


def chart(app):
    figure = chart_args(app)["figure"]
    figure["data"] = [t for t in figure["data"]
                      if t["name"] not in ("Buy-zone plot floor", "Below buy zone")]
    return figure


def chart_args(app):
    component = next(item for item in app.get("component_instance")
                     if item.proto.component_name.endswith("mean_reversion_channel_panel"))
    return json.loads(component.proto.json_args)


def top_facts(app):
    """The selected stock has one prominent, semantic, live readout."""
    return next(m.value for m in app.markdown
                if '<section class="mr-priority-readout"' in m.value)


def test_mean_reversion_and_soxl_have_separate_pages():
    tree = ast.parse(Path("main.py").read_text())
    pages = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "Page"]
    assert len(pages) == 2
    assert pages[0].args[0].id == "render_mean_reversion_workspace"
    assert any(kw.arg == "default" and kw.value.value is True for kw in pages[0].keywords)
    assert pages[1].args[0].value == "app.py"
    assert any(kw.arg == "url_path" and kw.value.value == "soxl" for kw in pages[1].keywords)
    assert "render_mean_reversion_workspace" not in Path("app.py").read_text()
    assert 'with_name("main.py")' in Path("streamlit_backend.py").read_text()


def test_soxl_and_three_lines_load_without_input():
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    assert not app.exception
    assert not app.title
    assert "TICKER: SOXL" in top_facts(app)
    assert "Company: SOXL security" in top_facts(app)
    assert "Verdict: WINNER" in top_facts(app)
    assert len(app.get("component_instance")) == 1
    assert len(app.metric) == 8
    figure = chart(app)
    assert len(figure["data"]) == 4
    assert figure["data"][0]["name"] == "SOXL · actual"
    assert [trace["name"] for trace in figure["data"][1:]] == [
        "Upper trend", "Mean trend", "Lower trend"]
    assert figure["layout"]["height"] >= 500
    assert " / 100" in next(m for m in app.metric if m.label == "Steel hands score · 0–100").value
    assert all(label.startswith("$") for label in figure["layout"]["yaxis"]["ticktext"])
    app.radio[0].set_value("Paper hands").run()
    assert next(m for m in app.metric if m.label == "Paper hands score · 0–100")
    source = Path("mean_reversion_workspace.py").read_text()
    assert source.index('with st.form("mr_replace_primary_top_form")') < source.index("render_channel_chart(")
    assert source.index("render_channel_chart(") < source.index('with st.form("mr_replace_primary_form")')


def test_replacement_comparisons_and_removal_are_separate():
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    previous_prices = chart(app)["data"][0]["y"]
    app.text_input[0].input("AAPL")
    next(b for b in app.button if b.label == "Replace primary").click().run()
    assert not app.exception
    data = chart(app)["data"]
    assert len(data) == 4
    assert data[0]["name"] == "AAPL · actual"
    assert "TICKER: AAPL" in top_facts(app)
    assert "Company: Apple Inc." in top_facts(app)
    assert data[0]["y"] != previous_prices
    assert not any("SOXL" in trace["name"] for trace in data)
    for symbol in ["MSFT", "KO", "SPY"]:
        app.text_input("mr_workspace_compare_input").input(symbol)
        next(b for b in app.button if b.label == "Add comparison").click().run()
    assert len(chart(app)["data"]) == 7
    assert "TICKER: AAPL" in top_facts(app)
    next(b for b in app.button if b.label == "Remove KO").click().run()
    assert len(chart(app)["data"]) == 6
    next(b for b in app.button if b.label == "Remove last added").click().run()
    data = chart(app)["data"]
    assert len(data) == 5 and data[-1]["name"] == "MSFT · normalized"
    next(b for b in app.button if b.label == "Remove all comparisons").click().run()
    assert len(chart(app)["data"]) == 4
    next(b for b in app.button if b.label == "Remove chart").click().run()
    assert not any('<section class="mr-priority-readout"' in m.value
                   for m in app.markdown)
    assert not chart_args(app)["figure"]["data"]
    app.run()
    assert not chart_args(app)["figure"]["data"]
    assert not app.exception


def test_bad_replacement_keeps_last_good_chart():
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    app.text_input[0].input("BAD")
    next(b for b in app.button if b.label == "Replace primary").click().run()
    assert not app.exception
    assert app.error
    assert chart(app)["data"][0]["name"] == "SOXL · actual"
    feedback = next(m.value for m in app.markdown if "mr-input-feedback" in m.value)
    assert "Could not load BAD. Still showing SOXL." in feedback


def test_both_ticker_forms_replace_the_same_chart():
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    assert len([b for b in app.button if b.label == "Replace primary"]) == 2
    for input_key, symbol, button_index in [
        ("mr_workspace_top_primary_input", "TQQQ", 0),
        ("mr_workspace_primary_input", "MSFT", 1),
    ]:
        app.text_input(input_key).input(symbol)
        [b for b in app.button if b.label == "Replace primary"][button_index].click().run()
        assert not app.exception
        assert chart(app)["data"][0]["name"] == f"{symbol} · actual"
        assert f"TICKER: {symbol}" in top_facts(app)
        assert app.text_input(input_key).value == ""
        assert len(chart(app)["data"]) == 4


def test_failed_initial_load_retries_and_recovers_existing_blank_sessions():
    flaky = SCRIPT.replace(
        "workspace.render_mean_reversion_workspace()",
        """
original_load = workspace._load_history
def load_with_one_failure(symbol):
    attempts = workspace.st.session_state.get("load_attempts", 0) + 1
    workspace.st.session_state["load_attempts"] = attempts
    if attempts == 1:
        raise RuntimeError("Temporary provider failure")
    return original_load(symbol)
workspace._load_history = load_with_one_failure
workspace.render_mean_reversion_workspace()
workspace._load_history = original_load
""",
    )
    app = AppTest.from_string(flaky, default_timeout=15).run()
    assert not app.exception
    assert not chart(app)["data"]
    assert app.session_state["mr_workspace_auto_initialized"] is False
    # Simulate the stale initialized flag retained by the previous version.
    app.session_state["mr_workspace_auto_initialized"] = True
    app.run()
    assert not app.exception
    assert chart(app)["data"][0]["name"] == "SOXL · actual"
    assert len(chart(app)["data"]) == 4
    assert not app.error


def test_removed_chart_can_restore_the_soxl_example():
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    next(b for b in app.button if b.label == "Remove chart").click().run()
    assert not chart(app)["data"]
    next(b for b in app.button if b.label == "Show SOXL example").click().run()
    assert not app.exception
    assert chart(app)["data"][0]["name"] == "SOXL · actual"
    assert len(chart(app)["data"]) == 4
    assert next(m for m in app.metric if m.label == "Steel hands score · 0–100")


def test_date_changes_all_targets_and_hover_uses_each_hovered_date():
    from datetime import date
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    prior = [metric.value for metric in app.metric if metric.label == "Target stock price"]
    app.date_input("mr_workspace_projection_date").set_value(date(2028, 11, 18)).run()
    assert not app.exception
    assert prior != [metric.value for metric in app.metric if metric.label == "Target stock price"]
    figure = chart(app)
    trend = figure["data"][1]
    assert trend["x"][-1] == "2028-11-18"
    assert trend["customdata"][-1][0] == "2028-11-18"
    assert trend["customdata"][-1][1] != trend["customdata"][-2][1]


def test_reference_outage_does_not_affect_absolute_scores():
    broken = SCRIPT.replace(
        "workspace.render_mean_reversion_workspace()",
        "workspace._cached_reference_analyses = lambda: ({}, ['QQQ'])\n"
        "workspace.render_mean_reversion_workspace()",
    )
    app = AppTest.from_string(broken, default_timeout=15).run()
    assert not app.exception
    assert next(m for m in app.metric if m.label == "Steel hands score · 0–100").value != "Unavailable"
    assert len(chart(app)["data"]) == 4


def test_top_readout_has_identity_individual_facts_scores_and_selected_date():
    from datetime import date
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    app.text_input("mr_workspace_top_primary_input").input("APPL")
    next(b for b in app.button if b.label == "Replace primary").click().run()
    assert not app.exception
    assert "TICKER: AAPL" in top_facts(app)
    assert "Company: Apple Inc." in top_facts(app)
    assert app.text_input[0].label == "Enter stock ticker"
    facts = top_facts(app)
    assert "Mean-reverting: YES — score " in facts
    assert "Mean trend: UP" in facts
    assert "Annualized slope: +" in facts
    assert "Position: 2026-11-18:" in facts
    assert "color: #111" in facts
    assert "font-size: clamp(" in facts
    assert facts.index("TICKER:") < facts.index("Verdict:") < facts.index("Mean-reverting:")
    assert any("Steel hands score:" in caption.value for caption in app.caption)
    app.date_input("mr_workspace_position_date").set_value(date(2025, 11, 15)).run()
    assert not app.exception
    assert "Position: 2025-11-14:" in top_facts(app)
    assert "TICKER: AAPL" in top_facts(app)


def test_nonwinner_verdict_is_the_first_page_fact_and_tracks_replacement():
    script = SCRIPT.replace(
        'values = np.exp(4 + .002*np.arange(3024) + .1*np.sin(np.arange(3024)/10))',
        'values = np.full(3024, 100.) if symbol == "KO" else np.exp(4 + .002*np.arange(3024) + .1*np.sin(np.arange(3024)/10))',
    )
    app = AppTest.from_string(script, default_timeout=15).run()
    assert "Verdict: WINNER" in top_facts(app)
    assert "TICKER: SOXL" in top_facts(app)
    app.text_input("mr_workspace_top_primary_input").input("KO")
    next(b for b in app.button if b.label == "Replace primary").click().run()
    assert not app.exception
    assert "Verdict: NOT A WINNER" in top_facts(app)
    assert "TICKER: KO" in top_facts(app)
    assert "SOXL" not in top_facts(app)
    assert "Mean-reverting: YES" in top_facts(app)
    assert "Mean trend: NOT UP" in top_facts(app)


def test_channel_panel_receives_one_set_of_real_targets_and_readable_hover_data():
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    assert not app.exception
    payload = chart_args(app)
    assert payload["symbol"] == "SOXL"
    assert payload["readout_height"] >= 600
    assert [row["kind"] for row in payload["rows"]] == ["upper", "median", "lower"]
    figure = chart(app)
    assert figure["layout"]["hovermode"] == "closest"
    assert figure["layout"]["dragmode"] == "pan"
    assert figure["layout"]["hoverlabel"]["font"]["size"] >= 18
    for trace in figure["data"][1:]:
        assert trace["hoverinfo"] == "none"
        assert "hovertemplate" not in trace
        assert trace["customdata"][0][2] == "Historical date — not a forecast"
        assert all(value != "Not available" for value in trace["customdata"][-1])
    # Hovered future-date values and initial panel use the same computed targets.
    last_point = figure["data"][1]["customdata"][-1]
    for row, price_index in zip(payload["rows"], (1, 3, 5)):
        assert last_point[price_index] == f"${row['target_price']:,.2f}"
    next(b for b in app.button if b.label == "Remove chart").click().run()
    empty = chart_args(app)
    assert empty["symbol"] == ""
    assert empty["rows"] == []
    assert empty["selected_date"] is None


def test_short_history_replaces_chart_with_fixed_lines_without_inventing_scores():
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    app.text_input("mr_workspace_top_primary_input").input("VWAV")
    [b for b in app.button if b.label == "Replace primary"][0].click().run()
    assert not app.exception
    data = chart(app)["data"]
    assert len(data) == 4
    assert data[0]["name"] == "VWAV · actual"
    assert len(data[0]["x"]) == 342
    facts = top_facts(app)
    assert "TICKER: VWAV" in facts
    assert "SOXL" not in facts
    assert "INSUFFICIENT SCORING HISTORY" in facts
    assert "Annualized slope: +" in facts
    assert len(chart_args(app)["rows"]) == 3


def test_projection_extends_one_hundred_years_with_three_straight_log_lines():
    import numpy as np
    from datetime import date
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    scores = [metric.value for metric in app.metric if "hands score" in metric.label]
    app.date_input("mr_workspace_projection_date").set_value(date(2126, 11, 18)).run()
    assert not app.exception
    figure = chart(app)
    assert figure["layout"]["yaxis"]["type"] == "log"
    for trace in figure["data"][1:]:
        assert trace["x"][-1] == "2126-11-18"
        elapsed = np.array([(date.fromisoformat(d)-date.fromisoformat(trace["x"][0])).days
                            for d in trace["x"]])
        log_prices = np.log(trace["y"])
        slope = (log_prices[-1]-log_prices[0])/elapsed[-1]
        assert np.max(np.abs(log_prices-(log_prices[0]+slope*elapsed))) < 1e-10
    assert [metric.value for metric in app.metric if "hands score" in metric.label] == scores
    assert all(row["target_price"] > 0 for row in chart_args(app)["rows"])


def test_mismatched_price_feed_cannot_silently_show_a_different_stock():
    script = SCRIPT.replace(
        'return {"symbol": symbol, "dates":',
        'return {"symbol": "SOXL" if symbol == "WRONG" else symbol, "dates":',
    )
    app = AppTest.from_string(script, default_timeout=15).run()
    app.text_input("mr_workspace_top_primary_input").input("WRONG")
    [b for b in app.button if b.label == "Replace primary"][0].click().run()
    assert not app.exception
    feedback = next(m.value for m in app.markdown if "mr-input-feedback" in m.value)
    assert "Still showing SOXL" in feedback
    assert "different ticker" in feedback
    assert chart(app)["data"][0]["name"] == "SOXL · actual"

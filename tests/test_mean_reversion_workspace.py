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
    dates = pd.bdate_range(end="2026-11-18", periods=1512)
    values = np.exp(4 + .002*np.arange(1512) + .1*np.sin(np.arange(1512)/10))
    return {"symbol": symbol, "dates": dates.strftime("%Y-%m-%d").tolist(),
            "prices": values.tolist(), "through": "2026-11-18", "source": "test fixture"}
workspace._cached_stock_history = fixture_history
workspace._cached_reference_analyses = lambda: (
    {s: workspace.analyze_winner(fixture_history(s)) for s in workspace.REFERENCE_SYMBOLS}, [])
workspace.render_mean_reversion_workspace()
"""


def chart(app):
    figure = json.loads(app.get("plotly_chart")[0].proto.spec)
    figure["data"] = [t for t in figure["data"]
                      if t["name"] not in ("Buy-zone plot floor", "Below buy zone")]
    return figure


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
    assert app.title[0].value == "Mean Reversion"
    assert len(app.get("plotly_chart")) == 1
    assert len(app.metric) == 11
    figure = chart(app)
    assert len(figure["data"]) == 4
    assert figure["data"][0]["name"] == "SOXL · actual"
    assert [trace["name"] for trace in figure["data"][1:]] == [
        "Upper trend", "Mean line (OLS)", "Lower trend"]
    assert figure["layout"]["height"] >= 500
    assert next(m for m in app.metric if m.label == "Steel hands score · 0–100").value == "100.0"
    app.radio[0].set_value("Paper hands").run()
    assert next(m for m in app.metric if m.label == "Paper hands score · 0–100")
    source = Path("mean_reversion_workspace.py").read_text()
    assert source.index("st.plotly_chart(") < source.index('with st.form(')


def test_replacement_comparisons_and_removal_are_separate():
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    app.text_input[0].input("AAPL")
    next(b for b in app.button if b.label == "Replace primary").click().run()
    assert not app.exception
    data = chart(app)["data"]
    assert len(data) == 4
    assert data[0]["name"] == "AAPL · actual"
    assert not any("SOXL" in trace["name"] for trace in data)
    for symbol in ["MSFT", "KO", "SPY"]:
        app.text_input[1].input(symbol)
        next(b for b in app.button if b.label == "Add comparison").click().run()
    assert len(chart(app)["data"]) == 7
    next(b for b in app.button if b.label == "Remove KO").click().run()
    assert len(chart(app)["data"]) == 6
    next(b for b in app.button if b.label == "Remove last added").click().run()
    data = chart(app)["data"]
    assert len(data) == 5 and data[-1]["name"] == "MSFT · normalized"
    next(b for b in app.button if b.label == "Remove all comparisons").click().run()
    assert len(chart(app)["data"]) == 4
    next(b for b in app.button if b.label == "Remove chart").click().run()
    assert not json.loads(app.get("plotly_chart")[0].proto.spec)["data"]
    app.run()
    assert not json.loads(app.get("plotly_chart")[0].proto.spec)["data"]
    assert not app.exception


def test_bad_replacement_keeps_last_good_chart():
    app = AppTest.from_string(SCRIPT, default_timeout=15).run()
    app.text_input[0].input("BAD")
    next(b for b in app.button if b.label == "Replace primary").click().run()
    assert not app.exception
    assert app.error
    assert chart(app)["data"][0]["name"] == "SOXL · actual"


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
    app.date_input[0].set_value(date(2028, 11, 18)).run()
    assert not app.exception
    assert prior != [metric.value for metric in app.metric if metric.label == "Target stock price"]
    figure = chart(app)
    trend = figure["data"][1]
    assert trend["x"][-1] == "2028-11-18"
    assert trend["customdata"][-1][0] == "2028-11-18"
    assert trend["customdata"][-1][1] != trend["customdata"][-2][1]


def test_missing_reference_withholds_scores_without_losing_chart():
    broken = SCRIPT.replace(
        "workspace.render_mean_reversion_workspace()",
        "workspace._cached_reference_analyses = lambda: ({}, ['QQQ'])\n"
        "workspace.render_mean_reversion_workspace()",
    )
    app = AppTest.from_string(broken, default_timeout=15).run()
    assert not app.exception
    assert next(m for m in app.metric if m.label == "Steel hands score · 0–100").value == "Unavailable"
    assert len(chart(app)["data"]) == 4

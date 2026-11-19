"""Chart-first layout and immediate removal without market requests in tests."""
import ast
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


SCRIPT = """
import mean_reversion_workspace as workspace
def fixture_history(symbol):
    return {"symbol": symbol, "dates": ["2026-11-17", "2026-11-18"],
            "prices": [100, 102], "through": "2026-11-18", "source": "test fixture"}
workspace._cached_stock_history = fixture_history
workspace.render_mean_reversion_workspace()
"""


def test_top_workspace_precedes_all_legacy_content():
    tree = ast.parse(Path("app.py").read_text())
    calls = [node.value.func.id for node in tree.body
             if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
             and isinstance(node.value.func, ast.Name)]
    assert calls.index("render_mean_reversion_workspace") < calls.index("render_account_header")
    assert calls.index("render_mean_reversion_workspace") < calls.index("render_top_soxl_price")
    assert "from trend_reversion_ui import" not in Path("app.py").read_text()


def test_blank_chart_and_scores_exist_before_input():
    app = AppTest.from_string(SCRIPT).run()
    assert not app.exception
    assert app.title[0].value == "Mean Reversion"
    assert len(app.get("plotly_chart")) == 1
    assert len(app.metric) == 3
    figure = json.loads(app.get("plotly_chart")[0].proto.spec)
    assert not figure["data"]
    assert figure["layout"]["height"] >= 500
    source = Path("mean_reversion_workspace.py").read_text()
    assert source.index("st.plotly_chart(") < source.index('with st.form(')


def test_add_and_remove_update_same_chart_immediately():
    app = AppTest.from_string(SCRIPT).run()
    app.text_input[0].input("AAPL")
    app.button[0].click().run()
    assert not app.exception
    assert len(json.loads(app.get("plotly_chart")[0].proto.spec)["data"]) == 1
    app.text_input[0].input("MSFT")
    next(b for b in app.button if b.label == "Add stock").click().run()
    assert len(json.loads(app.get("plotly_chart")[0].proto.spec)["data"]) == 2
    next(b for b in app.button if b.label == "Remove last added").click().run()
    data = json.loads(app.get("plotly_chart")[0].proto.spec)["data"]
    assert [trace["name"] for trace in data] == ["AAPL"]
    next(b for b in app.button if b.label == "Remove AAPL").click().run()
    assert not json.loads(app.get("plotly_chart")[0].proto.spec)["data"]
    app.text_input[0].input("SPY")
    next(b for b in app.button if b.label == "Add stock").click().run()
    next(b for b in app.button if b.label == "Remove all charts").click().run()
    assert not json.loads(app.get("plotly_chart")[0].proto.spec)["data"]
    assert not app.exception

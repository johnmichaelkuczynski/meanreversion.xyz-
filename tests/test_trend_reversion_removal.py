"""Toolbar actions remove only the independent Mean Reversion selections."""
import ast
from pathlib import Path
from types import SimpleNamespace


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


def apply_action(event, overlays=None):
    tree = ast.parse(Path("trend_reversion_ui.py").read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"_select", "_remove", "_chart_action"}]
    state = State(mr_ticker="AAPL", mr_input="AAPL", mr_loaded=True,
                  mr_overlays=list(overlays or []), event=event,
                  unrelated_chart="unchanged")
    namespace = {"st": SimpleNamespace(session_state=state)}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<toolbar>", "exec"), namespace)
    namespace["_chart_action"]("event")
    assert state.unrelated_chart == "unchanged"
    return state


def test_remove_main_chart_leaves_empty_state():
    assert not apply_action({"action": "remove", "symbol": "AAPL"}).mr_loaded


def test_remove_one_comparison_keeps_others():
    state = apply_action({"action": "remove", "symbol": "MSFT"}, ["MSFT", "SPY"])
    assert state.mr_overlays == ["SPY"]
    assert state.mr_loaded and state.mr_ticker == "AAPL"


def test_remove_main_promotes_remaining_stock():
    state = apply_action({"action": "remove", "symbol": "AAPL"}, ["MSFT", "SPY"])
    assert state.mr_ticker == state.mr_input == "SPY"
    assert state.mr_overlays == ["MSFT"]


def test_remove_all_empties_mean_reversion_only():
    state = apply_action({"action": "remove_all"}, ["MSFT", "SPY"])
    assert not state.mr_loaded
    assert state.mr_overlays == []

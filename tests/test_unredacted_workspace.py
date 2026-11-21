from unittest.mock import patch
import json

from streamlit.testing.v1 import AppTest

import access
import mean_reversion_workspace as workspace


SCRIPT = """
import streamlit as st
import numpy as np
import pandas as pd
import mean_reversion_workspace as w
def history(symbol):
    st.session_state.setdefault("fixture_downloads", []).append(symbol)
    dates = pd.bdate_range(end="2026-11-20", periods=1600)
    prices = np.exp(3 + .001*np.arange(1600) + .12*np.sin(np.arange(1600)/30))
    return {"symbol":symbol,"dates":dates.strftime("%Y-%m-%d").tolist(),
            "prices":prices.tolist(),"through":"2026-11-20"}
w._cached_stock_history = history
w._cached_company_name = lambda symbol: "Fixture " + symbol
w._winner_reading = lambda h: (w.analyze_winner(h), {"steel":73.2,"paper":48.1}, [])
w.render_illustrated_rankings = lambda: None
w.render_mean_reversion_workspace()
"""


def test_guest_sees_real_original_scores_prices_probabilities_and_projections(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with patch.object(access, "get_current_user", return_value={"is_logged_in": False}):
        app = AppTest.from_string(SCRIPT, default_timeout=20).run()
        assert not app.exception
        facts = next(x.value for x in app.markdown if 'class="mr-priority-readout"' in x.value)
        assert "Steel hands: 73.2 / 100" in facts
        assert "Paper hands: 48.1 / 100" in facts
        assert "Annualized slope:" in facts and "% per year" in facts
        assert "Position:" in facts and "the mean" in facts
        assert not any("REDACTED" in item.value for item in app.markdown)
        assert not app.get("link_button")
        component = next(x for x in app.get("component_instance")
                         if x.proto.component_name.endswith("mean_reversion_channel_panel"))
        args = json.loads(component.proto.json_args)
        assert args["figure"]["layout"]["yaxis"]["type"] == "log"
        assert len(args["figure"]["data"][0]["x"]) == 1600
        assert args["rows"] and all(isinstance(row["target_price"], (int, float))
                                    for row in args["rows"])
        assert max(args["figure"]["data"][1]["x"]) > "2026-11-20"
        assert not app.date_input(key="mr_workspace_projection_date").disabled
        app.text_input(key="mr_workspace_top_primary_input").set_value("QQQ").run()
        assert not app.exception
        assert app.session_state["mr_workspace_primary"]["symbol"] == "QQQ"

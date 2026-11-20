"""Mean Reversion's readable, expandable channel-comparison chart."""

import json
import hashlib
from pathlib import Path

import streamlit.components.v1 as components


_frontend = Path(__file__).parent / "components" / "mean_reversion_panel"
# A changed iframe URL also invalidates its relative JS/CSS URLs in open tabs.
_revision = hashlib.sha256(
    b"".join((_frontend / name).read_bytes()
             for name in ("index.html", "panel.css", "panel.js"))
).hexdigest()[:12]
_channel_panel = components.declare_component(
    f"{_revision}_mean_reversion_channel_panel", path=str(_frontend),
)


def render_channel_chart(figure, primary, model, rows, selected_date):
    """Pass the existing figure and calculated estimates; never recalculate odds."""
    return _channel_panel(
        figure=json.loads(figure.to_json()),
        symbol=primary["symbol"] if primary else "",
        last_date=model.get("last_date") if model else None,
        selected_date=selected_date.isoformat() if selected_date else None,
        rows=rows,
        config={"displaylogo": False, "scrollZoom": True, "responsive": True},
        readout_height=640,
        key=f"mean_reversion_workspace_chart_{_revision}",
        default=None,
    )

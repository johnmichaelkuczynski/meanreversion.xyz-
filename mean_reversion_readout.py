"""Short, dated stock facts for the top of the Mean Reversion page."""

from bisect import bisect_right
from datetime import date
import math

import streamlit as st

from mean_reversion_winner import CONFIG

POSITION_DATE = "mr_workspace_position_date"


def dated_position(history, analysis, selected):
    """Compare a real close with the fitted mean on that same trading date."""
    index = bisect_right(history["dates"], selected.isoformat()) - 1
    if index < 0:
        raise ValueError("No closing price is available on or before that date.")
    day = history["dates"][index]
    years = (date.fromisoformat(day) - date.fromisoformat(analysis["origin"])).days / CONFIG["calendar_days"]
    trend = math.exp(analysis["intercept"] + analysis["slope"] * years)
    return day, (float(history["prices"][index]) / trend - 1) * 100


def summary_lines(analysis, scores, position):
    """One label and one fact per line; do not change the scoring rules."""
    established = analysis["has_mean"]
    reverting = established and analysis["pull"] >= CONFIG["pull_threshold"]
    lines = [
        ("Mean reverting", f"Yes — {analysis['pull_label'].lower()} pull" if reverting else
         ("No — weak pull" if established else "Not established — insufficient history")),
        ("Mean trends up", ("Yes" if analysis["slope"] > 0 else "No") if established else "Not established"),
        ("Mean trend growth", f"{analysis['slope_pct']:+.2f}% per year" if established else "Not established"),
    ]
    for label, mode in (("Mean reversion + growth score · Steel hands", "steel"),
                        ("Mean reversion + growth score · Paper hands", "paper")):
        lines.append((label, f"{scores[mode]:.1f} / 100" if scores is not None else "Unavailable — reference data missing"))
    if established:
        day, distance = position
        direction = "ABOVE" if distance > 0 else "BELOW" if distance < 0 else "ON"
        text = f"{abs(distance):.1f}% {direction} the mean trend line"
        lines.append((f"Position on {day}", text))
    else:
        lines.append(("Position", "Not established — no established mean"))
    return lines


def render_stock_readout(history, company_name, analysis, scores):
    """Keep the identity and the requested facts above the chart."""
    st.header(f"{history['symbol']} — {company_name}", anchor=False)
    first, last = (date.fromisoformat(history["dates"][i]) for i in (0, -1))
    selected = st.session_state.get(POSITION_DATE, last)
    st.session_state[POSITION_DATE] = min(last, max(first, selected))
    # Reserve this row so the dated fact stays with the other facts.
    facts = st.container()
    selected = st.date_input(
        "Date for above/below-mean position", min_value=first, max_value=last,
        key=POSITION_DATE,
        help="Uses the last available close on or before this date and the full-history fitted mean.",
    )
    position = dated_position(history, analysis, selected) if analysis["has_mean"] else None
    with facts:
        for label, value in summary_lines(analysis, scores, position):
            st.markdown(f"**{label}: {value}**")

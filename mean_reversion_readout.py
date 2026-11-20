"""One-fact-per-line readout for the walk-forward Mean Reversion model."""
from bisect import bisect_right
from datetime import date

import numpy as np
import streamlit as st

from mean_reversion_winner import CONFIG

POSITION_DATE = "mr_workspace_position_date"


def dated_position(history, analysis, selected):
    index = bisect_right(analysis["trend_dates"], selected.isoformat()) - 1
    if index < 0:
        raise ValueError("Five preceding years are required for a dated trend.")
    day = analysis["trend_dates"][index]
    price = history["prices"][bisect_right(history["dates"], day)-1]
    gap = float(price/analysis["trend_prices"][index]-1)
    percentile = float(100*np.mean(np.asarray(analysis["historical_gaps"]) <= gap+1e-12))
    return day, gap*100, percentile


def _score(value):
    return f"{value:.1f} / 100" if value is not None else "Unavailable"


def _percent(value):
    return f"{value:.1%}" if value is not None else "Insufficient year-end history"


def summary_lines(analysis, scores, position):
    if not analysis["has_mean"]:
        return [("Trend", "Insufficient history — five preceding years required"),
                ("Mean Reversion Score", "Unavailable"),
                ("Deep-dip flag", "No — insufficient history")]
    day, gap, percentile = position
    direction = "ABOVE" if gap > 0 else "BELOW" if gap < 0 else "ON"
    return [
        ("Mean Reversion Score", _score(analysis["mean_reversion_score"])),
        ("Closeness", f"{analysis['closeness_score']:.1f}% of eligible closes within 10% of trend"),
        ("Recovery score", _score(analysis["recovery_score"]) if analysis["recovery_score"] is not None else "Insufficient recovery history"),
        ("Latest mean trend growth", f"{analysis['slope_pct']:+.2f}% per year"),
        ("Median annualized trend slope", f"{analysis['median_growth_pct']:+.2f}%"),
        ("Positive year-end slopes", _percent(analysis["positive_year_fraction"])),
        (f"Position on {day}", f"{abs(gap):.1f}% {direction} trend — higher than {percentile:.1f}% of historical gaps"),
        ("Steel hands score", _score(scores["steel"])),
        ("Paper hands score", _score(scores["paper"])),
        ("Deep-dip flag", "YES" if analysis["deep_dip"] else "No"),
    ]


def render_stock_readout(history, company_name, analysis, scores):
    st.header(f"{history['symbol']} — {company_name}", anchor=False)
    position = None
    if analysis["has_mean"]:
        first = date.fromisoformat(analysis["trend_dates"][0])
        last = date.fromisoformat(analysis["trend_dates"][-1])
        chosen = st.session_state.get(POSITION_DATE, last)
        st.session_state[POSITION_DATE] = min(last, max(first, chosen))
        facts = st.container()
        selected = st.date_input(
            "Date for above/below-trend position", min_value=first, max_value=last,
            key=POSITION_DATE,
            help="Uses the last available close on or before this date and that day's preceding-five-year fit, excluding the scored close.",
        )
        position = dated_position(history, analysis, selected)
    else:
        facts = st.container()
    with facts:
        for label, value in summary_lines(analysis, scores, position):
            st.markdown(f"**{label}: {value}**")


def render_score_details(analysis, scores, style_key):
    st.subheader("Mean-reversion components")
    if not analysis["has_mean"]:
        st.write("Five preceding years of adjusted daily closes are required.")
        return
    style = st.radio("Score emphasis", ("Steel hands", "Paper hands"),
                     horizontal=True, key=style_key)
    keys = ("steel", "paper") if style == "Steel hands" else ("paper", "steel")
    cols = st.columns(2)
    for column, key in zip(cols, keys):
        column.metric(f"{key.title()} hands score · 0–100", _score(scores[key]))
    st.write(f"Shared growth verdict: {analysis['verdict']}.")
    st.write(f"Mature recovery events: {analysis['mature_count']}.")
    for year in CONFIG["recovery_years"]:
        fraction = analysis["recovery_fractions"][str(year)]
        st.write(f"{year}-year recovery: {_percent(fraction) if fraction is not None else 'No mature events'}.")
    st.write(f"Newer events, excluded from recovery scoring: {analysis['newer_count']}.")
    st.write(f"Steel Hands downside bonus component: {analysis['depth_bonus']:.4f}.")
    st.write(f"Paper Hands 90th-percentile drawdown: {analysis['drawdown90']:.1%}.")
    st.write(f"Deep-dip qualifying mature downside events: {analysis['matched_dip_count']}.")
    fraction = analysis["matched_dip_recovery_fraction"]
    st.write(f"Deep-dip recovery fraction: {fraction:.1%}." if fraction is not None
             else "Deep-dip recovery fraction: no qualifying events.")
    st.caption("Ranking scores are heuristic scores, not probabilities.")
    for title, events in (("Mature events · five years of follow-up", analysis["mature_events"]),
                          ("Newer events · not used in recovery scoring", analysis["newer_events"])):
        with st.expander(f"{title} ({len(events)})"):
            if events:
                st.dataframe([{
                    "Opened": event["opened"], "Side": event["direction"],
                    "Opening depth": f"{event['opening_depth']:.1%}",
                    "Half-gap recovery": event["recovered_on"] or "Not recovered",
                    "Within 1 year": event["recovered_within"]["1"],
                    "Within 3 years": event["recovered_within"]["3"],
                    "Within 5 years": event["recovered_within"]["5"],
                } for event in events], hide_index=True, use_container_width=True)
            else:
                st.write("No events in this group.")

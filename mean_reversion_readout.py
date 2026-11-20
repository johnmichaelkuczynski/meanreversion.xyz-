"""One-fact-per-line readout for the walk-forward Mean Reversion model."""
from bisect import bisect_right
from datetime import date
from html import escape

import numpy as np
import streamlit as st

from mean_reversion_winner import CONFIG
from mean_reversion_channels import YEAR_DAYS

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


def chart_position(history, channel, selected):
    """Above/below the same fixed straight mean that is actually plotted."""
    index = max(0, bisect_right(history["dates"], selected.isoformat())-1)
    day = history["dates"][index]
    origin = date.fromisoformat(channel["origin"])
    years = (date.fromisoformat(day)-origin).days/YEAR_DAYS
    log_gap = (np.log(history["prices"][index])-channel["intercepts"]["median"]
               -channel["slope"]*years)
    elapsed = np.array([(date.fromisoformat(d)-origin).days/YEAR_DAYS
                        for d in history["dates"]])
    residuals = (np.log(history["prices"])-channel["intercepts"]["median"]
                 -channel["slope"]*elapsed)
    return day, float(np.expm1(log_gap)*100), float(100*np.mean(residuals <= log_gap+1e-12))


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


def render_stock_readout(history, company_name, analysis, scores, channel=None):
    """Render the primary decision facts before any supporting controls."""
    symbol = escape(str(history.get("symbol", "Ticker unavailable")))
    company = escape(str(company_name or "Company name unavailable"))
    position = None
    has_chart_mean = channel is not None and channel.get("has_mean")
    has_scoring_mean = analysis is not None and analysis.get("has_mean")
    if has_chart_mean or has_scoring_mean:
        first = date.fromisoformat(history["dates"][0] if has_chart_mean else analysis["trend_dates"][0])
        last = date.fromisoformat(history["dates"][-1] if has_chart_mean else analysis["trend_dates"][-1])
        chosen = st.session_state.get(POSITION_DATE, last)
        st.session_state[POSITION_DATE] = min(last, max(first, chosen))
        selected = st.session_state[POSITION_DATE]
        position = (chart_position(history, channel, selected) if has_chart_mean
                    else dated_position(history, analysis, selected))

    if analysis is None:
        verdict = "UNAVAILABLE — analysis could not be calculated"
        reversion = "Insufficient — analysis unavailable"
        trend = slope = "Insufficient — analysis unavailable"
        dated = "Unavailable — no dated trend analysis"
    elif not analysis.get("has_mean"):
        verdict = "INSUFFICIENT SCORING HISTORY"
        reversion = (
            f"Insufficient history — five preceding years required "
            f"(minimum score {CONFIG['minimum_mean_reversion']:.0f})"
        )
        trend = slope = "Insufficient five-year trend history"
        dated = "Insufficient five-year trend history"
    else:
        verdict = "WINNER" if analysis["winner"] else "NOT A WINNER"
        is_reverting = analysis["mean_reversion_score"] >= CONFIG["minimum_mean_reversion"]
        reversion = (
            f"{'YES' if is_reverting else 'NO'} — "
            f"score {analysis['mean_reversion_score']:.1f} / 100"
        )
        trend = "UP" if analysis["slope_pct"] > 0 else "NOT UP"
        slope = f"{analysis['slope_pct']:+.2f}% per year"
        day, gap, _percentile = position
        direction = "ABOVE" if gap > 0 else "BELOW" if gap < 0 else "ON"
        dated = (
            f"{day}: {abs(gap):.1f}% {direction} the mean"
        )

    if has_chart_mean:
        trend = "UP" if channel["slope_pct"] > 0 else "NOT UP"
        slope = f"{channel['slope_pct']:+.2f}% per year"
        day, gap, _percentile = position
        direction = "ABOVE" if gap > 0 else "BELOW" if gap < 0 else "ON"
        dated = f"{day}: {abs(gap):.1f}% {direction} the mean"

    st.markdown(
        f"""
        <style>
        .mr-priority-readout {{
            color: #111;
            margin: 0.15rem 0 0.5rem;
            line-height: 1.14;
        }}
        .mr-priority-readout .mr-ticker {{
            color: #111;
            font-size: clamp(2.35rem, 7vw, 4.5rem);
            font-weight: 900;
            letter-spacing: -0.055em;
            line-height: 0.98;
            overflow-wrap: anywhere;
        }}
        .mr-priority-readout .mr-fact {{
            color: #111;
            font-size: clamp(1.2rem, 2.7vw, 1.85rem);
            font-weight: 800;
            letter-spacing: -0.025em;
            line-height: 1.2;
            margin-top: 0.28rem;
            overflow-wrap: anywhere;
        }}
        .mr-priority-readout .mr-company {{
            color: #111;
            font-size: clamp(1.1rem, 2.4vw, 1.55rem);
            font-weight: 750;
            line-height: 1.2;
            margin-top: 0.12rem;
            overflow-wrap: anywhere;
        }}
        </style>
        <section class="mr-priority-readout" aria-label="Selected stock analysis">
          <div class="mr-ticker">TICKER: {symbol}</div>
          <div class="mr-company">Company: {company}</div>
          <div class="mr-fact">Verdict: {escape(verdict)}</div>
          <div class="mr-fact">Mean-reverting: {escape(reversion)}</div>
          <div class="mr-fact">Mean trend: {escape(trend)}</div>
          <div class="mr-fact">Annualized slope: {escape(slope)}</div>
          <div class="mr-fact">Position: {escape(dated)}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if has_chart_mean or has_scoring_mean:
        st.date_input(
            "Date for above/below-mean position",
            min_value=first,
            max_value=last,
            key=POSITION_DATE,
            help=(
                "Uses the last available close on or before this date and that "
                "the fixed straight mean shown on the chart."
            ),
        )


def render_score_details(analysis, scores, style_key, history=None):
    st.subheader("Mean-reversion components")
    if not analysis["has_mean"]:
        st.write("Five preceding years of adjusted daily closes are required.")
        return
    first = date.fromisoformat(analysis["trend_dates"][0])
    last = date.fromisoformat(analysis["trend_dates"][-1])
    chosen = st.session_state.get(POSITION_DATE, last)
    chosen = min(last, max(first, chosen))
    with st.expander("Additional model facts"):
        if history is not None:
            position = dated_position(history, analysis, chosen)
            for label, value in summary_lines(analysis, scores, position):
                st.caption(f"{label}: {value}")
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

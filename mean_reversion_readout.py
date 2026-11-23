"""One-fact-per-line readout for the recency-weighted straight-mean model."""
from bisect import bisect_right
from datetime import date
from html import escape
from math import isfinite

import numpy as np
import streamlit as st

from mean_reversion_winner import CONFIG
from mean_reversion_channels import YEAR_DAYS

POSITION_DATE = "mr_workspace_position_date"


@st.cache_data(ttl=20, show_spinner=False)
def _current_quote(symbol):
    from tiingo_market_data import TiingoError, fetch_quote
    try:
        return fetch_quote(symbol)
    except TiingoError:
        return None


def headline_price(history, quote):
    """Keep an unavailable live quote distinct from an available daily close."""
    if quote:
        price = quote.get("price")
        if isinstance(price, (int, float)) and isfinite(price) and price > 0:
            return (
                f"Current price: ${price:,.2f}",
                " · ".join(str(p) for p in (
                    quote.get("source"), quote.get("observed_label") or quote.get("observed_at")
                ) if p),
            )
    prices, dates = history.get("prices", []), history.get("dates", [])
    if len(prices) and len(dates):
        price = float(prices[-1])
        if isfinite(price) and price > 0:
            return f"Latest close: ${price:,.2f}", f"As of {dates[-1]} · Not a live quote"
    return "Current price: unavailable", ""


def dated_position(history, analysis, selected):
    index = bisect_right(analysis["trend_dates"], selected.isoformat()) - 1
    if index < 0:
        raise ValueError("Five years of history are required for a scored mean.")
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
        return [("Trend", "Insufficient history — five years required"),
                ("Pull", "Unavailable — insufficient history"),
                ("Deep-dip flag", "No — insufficient history")]
    day, gap, percentile = position
    direction = "ABOVE" if gap > 0 else "BELOW" if gap < 0 else "ON"
    return [
        ("Pull", f"{analysis['pull_strength']} — {analysis['pull']:.4f}"),
        ("Weighted excursion size L", f"{analysis['longest_excursion']:.6f} log-years"),
        ("Weighted swing W", f"{analysis['swing']:.6f}"),
        ("Weighted annualized volatility", _percent(analysis["volatility"])),
        ("Mean trend growth", f"{analysis['slope_pct']:+.2f}% per year"),
        (f"Position on {day}", f"{abs(gap):.1f}% {direction} trend — higher than {percentile:.1f}% of historical gaps"),
        ("Steel hands score", _score(scores["steel"])),
        ("Paper hands score", _score(scores["paper"])),
        ("Deep-dip flag", "YES" if analysis["deep_dip"] else "No"),
    ]


def render_stock_readout(history, company_name, analysis, scores, channel=None):
    """Render the primary decision facts before any supporting controls."""
    symbol = escape(str(history.get("symbol", "Ticker unavailable")))
    company = escape(str(company_name or "Company name unavailable"))
    price, price_time = headline_price(
        history, _current_quote(str(history["symbol"])) if history.get("symbol") else None
    )
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
        verdict = analysis["verdict"]
        reversion = "Unavailable — five years of history required"
        trend = slope = "Insufficient five-year trend history"
        dated = "Insufficient five-year trend history"
    else:
        verdict = analysis["verdict"]
        reversion = f"{analysis['pull_strength']} — {analysis['pull']:.4f}"
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
        .mr-priority-readout .mr-current-price {{
            color: #111;
            font-size: clamp(1.6rem, 3.4vw, 2.25rem);
            font-weight: 800;
            line-height: 1.2;
            margin-top: 0.35rem;
            font-variant-numeric: tabular-nums;
        }}
        .mr-priority-readout .mr-price-time {{
            color: #475569;
            font-size: 0.85rem;
            margin: 0.15rem 0 0.3rem;
        }}
        </style>
        <section class="mr-priority-readout" aria-label="Selected stock analysis">
          <div class="mr-ticker">TICKER: {symbol}</div>
          <div class="mr-current-price">{escape(price)}</div>
          <div class="mr-price-time">{escape(price_time)}</div>
          <div class="mr-company">Company: {company}</div>
          <div class="mr-fact">Verdict: {escape(verdict)}</div>
          <div class="mr-fact">Pull: {escape(reversion)}</div>
          <div class="mr-fact">Steel hands: {escape(_score(scores['steel']) if scores else 'Unavailable')}</div>
          <div class="mr-fact">Paper hands: {escape(_score(scores['paper']) if scores else 'Unavailable')}</div>
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
                "Uses the last available close on or before this date and "
                "the fixed recency-weighted straight mean shown on the chart."
            ),
        )


def render_score_details(analysis, scores, style_key, history=None):
    st.subheader("Mean-reversion components")
    if not analysis["has_mean"]:
        st.write("Five years of adjusted daily closes are required for a scored mean.")
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
    st.write(f"Pull to the mean: {analysis['pull_strength']} ({analysis['pull']:.4f}).")
    st.write(f"Mean line rising {analysis['slope_pct']:.2f}% per year."
             if analysis["slope_pct"] >= 0 else
             f"Mean line falling {abs(analysis['slope_pct']):.2f}% per year.")
    st.write(f"Typical swing: {np.expm1(analysis['swing']):.1%} from the mean.")
    longest = analysis["largest_excursion"]
    if longest:
        st.write(f"Largest weighted excursion: {longest['size']:.4f} log-years; "
                 f"{longest['years']:.2f} years, up to {longest['maximum_gap_pct']:.1f}% away.")
    st.write("Clearly below the mean." if analysis["deep_dip"] else "Not currently clearly below the mean.")
    if analysis["range_tradeable"]:
        st.write("Range-tradeable: buy only when clearly below the mean.")
    st.caption("Ranking scores are heuristic scores, not probabilities.")
    with st.expander("Method and weighted excursions"):
        st.write("All available adjusted daily closes. Seven-year recency half-life. "
                 "The straight mean uses weighted least squares; swing and daily-return "
                 "volatility use weighted population standard deviations. "
                 "After 20-session smoothing, excursion areas sum absolute log gaps "
                 "times each day's recency weight, divided by 252. "
                 "Pull = 1 / (1 + L / 8). Growth winners require at least 12% per year.")
        st.write("Steel = growth × Pull × (1 + W). "
                 "Paper = growth × Pull / (1 + 3W)^4. "
                 "Each is normalized to its maximum across SOXL, TQQQ, SOXX, QQQ and SPY, capped at 100.")
        st.dataframe(analysis["excursions"], hide_index=True, use_container_width=True)

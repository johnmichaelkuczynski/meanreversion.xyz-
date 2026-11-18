"""Additive Streamlit surface; all state and chart instances are independent."""
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from trend_reversion_data import load_history
from trend_reversion_model import analyze, simulate_touches, trend_lines


_component = components.declare_component(
    "independent_mean_reversion",
    path=str(Path(__file__).parent / "components" / "mean_reversion"),
)


@st.cache_data(ttl=86400, max_entries=64, show_spinner=False)
def _analyze(prices, dates):
    return analyze(prices, dates)


@st.cache_data(ttl=86400, max_entries=32, show_spinner=False)
def _forecast(model, end_date, today):
    return simulate_touches(model, end_date, today=today)


def _select(symbol):
    st.session_state.mr_ticker = symbol
    st.session_state.mr_input = symbol
    st.session_state.mr_loaded = True


def _remove(symbol):
    st.session_state.mr_overlays = [s for s in st.session_state.mr_overlays if s != symbol]


def compact_verdict(symbol, model):
    if model["status"] == "Not enough history to assess":
        return f"{symbol} — Not enough history to assess"
    if not model["gate_passed"]:
        return f"{symbol} — Random walk"
    return f'{symbol} — {model["grade"]} · {model["position_text"]} · {model["trend_pct"]:+.1f}%/yr'


@st.fragment
def render_mean_reversion():
    st.header("Mean Reversion")
    st.caption("Independent adjusted-price analysis. This section does not change the SOXL chart or signals above.")
    st.session_state.setdefault("mr_ticker", "SOXL")
    st.session_state.setdefault("mr_input", "SOXL")
    st.session_state.setdefault("mr_overlays", [])
    st.session_state.setdefault("mr_loaded", False)
    with st.form("mr_analyze_form"):
        st.text_input("Enter ticker", key="mr_input", max_chars=30)
        submitted = st.form_submit_button("Analyze")
    if submitted:
        from stock_chart_api import normalize_stock_symbol
        try:
            st.session_state.mr_ticker = normalize_stock_symbol(st.session_state.mr_input)
            st.session_state.mr_loaded = True
        except ValueError as exc:
            st.error(str(exc))
            return
    # Do not fetch or simulate until requested: the existing page's initial
    # rendering, saved-market readiness, and background work stay unchanged.
    if not st.session_state.mr_loaded:
        st.caption("Press Analyze to load the full adjusted-close history for SOXL or another ticker.")
        return
    symbol = st.session_state.mr_ticker
    try:
        with st.spinner(f"Analyzing {symbol} adjusted daily history…"):
            history = load_history(symbol)
            model = _analyze(history["prices"], history["dates"])
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("Mean Reversion analysis is temporarily unavailable. Try Analyze again shortly.")
        return
    st.subheader(symbol)
    with st.container(border=True):
        st.write(model["status"])
        if model["gate_passed"]:
            st.write(model["position_sentence"])
            st.write(model["trend_sentence"])
    default_end = (pd.Timestamp(date.today()) + pd.DateOffset(years=5)).date()
    end = st.date_input(
        "Extend model lines through", value=default_end,
        min_value=date.today() + pd.Timedelta(days=1),
        max_value=(pd.Timestamp(date.today()) + pd.DateOffset(years=29)).date(),
        key="mr_end_date", disabled=not model["gate_passed"],
    )
    future = historical = None
    if model["gate_passed"]:
        try:
            with st.spinner("Computing model touch probabilities…"):
                future = _forecast(model, end.isoformat(), date.today().isoformat())
                historical = trend_lines(model, history["dates"])
        except (ValueError, OverflowError):
            st.error("The requested projection could not be computed. Choose an earlier end date.")
            return
    overlays = []
    for index, ticker in enumerate(list(st.session_state.mr_overlays)):
        try:
            comparison = load_history(ticker)
            comparison_model = _analyze(comparison["prices"], comparison["dates"])
            row = st.columns([6, 1, 1])
            row[0].write(compact_verdict(ticker, comparison_model))
            row[1].button("Analyze this", key=f"mr_select_{ticker}",
                          on_click=_select, args=(ticker,))
            row[2].button("Remove", key=f"mr_remove_{ticker}",
                          on_click=_remove, args=(ticker,))
            if ticker != symbol:
                overlays.append({**comparison, "color": ["#9333ea", "#e98e2e", "#0891b2", "#db2777"][index % 4]})
        except ValueError as exc:
            st.warning(f"{ticker}: {exc}")
            st.button("Remove", key=f"mr_remove_bad_{ticker}", on_click=_remove, args=(ticker,))
        except Exception:
            st.warning(f"{ticker}: daily comparison history is temporarily unavailable.")
            st.button("Remove", key=f"mr_remove_unavailable_{ticker}", on_click=_remove, args=(ticker,))
    _component(payload={
        **history, "verdict": model, "forecast": future,
        "historical_trend": historical, "overlays": overlays,
    }, key="mr_chart_" + symbol, default=None)
    with st.form("mr_overlay_form", clear_on_submit=True):
        ticker = st.text_input("Add ticker", max_chars=30, key="mr_overlay_input")
        add = st.form_submit_button("Add")
    if add:
        try:
            comparison = load_history(ticker)
            code = comparison["symbol"]
            if code not in st.session_state.mr_overlays:
                st.session_state.mr_overlays.append(code)
            st.rerun(scope="fragment")
        except ValueError as exc:
            st.error(str(exc))
    st.caption(
        f'{history["source"]} · full available adjusted daily closes · '
        f'{history["dates"][0]} to {history["dates"][-1]} · {len(history["prices"]):,} observations. '
        "The dot is the latest available close, not a live quote."
    )
    if model["gate_passed"]:
        st.caption(
            "20,000 simulated paths. Future steps exclude weekends; exchange holidays are not removed. "
            "Probabilities concern daily-step crossings of moving model lines, not intraday touches, "
            "investment returns, or historically calibrated success rates. Model parameters are held fixed."
        )

"""Chart-first stock research workspace for the Mean Reversion page."""

from datetime import date, timedelta
from html import escape
import math

import plotly.graph_objects as go
import streamlit as st

from mean_reversion_channels import CHANNELS, channel_readout, hit_probability, fit_channel
from mean_reversion_chart import render_channel_chart
from mean_reversion_examples import render_illustrated_rankings
from mean_reversion_readout import POSITION_DATE, render_stock_readout, render_score_details
from mean_reversion_winner import (
    analyze_winner,
    normalize_scores,
)
from stock_chart_api import load_stock_history, load_stock_name, normalize_stock_symbol

_PRIMARY = "mr_workspace_primary"
_COMPARISONS = "mr_workspace_comparisons"
_ERROR = "mr_workspace_error"
_AUTO_INIT = "mr_workspace_auto_initialized"
_REMOVED = "mr_workspace_chart_removed"
_PRIMARY_INPUT = "mr_workspace_primary_input"
_TOP_PRIMARY_INPUT = "mr_workspace_top_primary_input"
_COMPARE_INPUT = "mr_workspace_compare_input"
_DATE_INPUT = "mr_workspace_projection_date"
_SCORE_STYLE = "mr_workspace_score_style"
_COLORS = {kind: color for kind, _, color in CHANNELS}


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_stock_history(symbol):
    """Cache full available adjusted daily history."""
    return load_stock_history(symbol, start_date="1900-01-01", tiingo_only=True)


@st.cache_data(ttl=86400, show_spinner=False)
def _cached_company_name(symbol):
    try:
        return load_stock_name(symbol)
    except Exception:
        return "Company name unavailable"


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_channel(history, end_date):
    return fit_channel(history, end_date=end_date)


def _load_history(symbol):
    symbol = normalize_stock_symbol(symbol)
    symbol = "AAPL" if symbol == "APPL" else symbol
    history = _cached_stock_history(symbol)
    if history.get("symbol") != symbol:
        raise ValueError("The price feed returned a different ticker. Your chart was not replaced.")
    return history


def _replacement_error(input_key, reason):
    requested = str(st.session_state.get(input_key, "")).strip().upper()[:30]
    primary = st.session_state.get(_PRIMARY)
    retained = f"Still showing {primary['symbol']}." if primary else "No stock is currently plotted."
    return f"Could not load {requested or 'the entered ticker'}. {retained} {reason}"


def _replace_primary(input_key=_PRIMARY_INPUT):
    try:
        history = _load_history(st.session_state.get(input_key, ""))
        st.session_state[_PRIMARY] = history
        st.session_state[_REMOVED] = False
        st.session_state[_COMPARISONS] = [
            item for item in st.session_state.get(_COMPARISONS, [])
            if item["symbol"] != history["symbol"]
        ]
        last = date.fromisoformat(history["dates"][-1])
        st.session_state[_DATE_INPUT] = last + timedelta(days=365)
        st.session_state[POSITION_DATE] = last
        st.session_state[_ERROR] = None
        st.session_state[input_key] = ""
    except ValueError as exc:
        st.session_state[_ERROR] = _replacement_error(input_key, str(exc))
    except Exception:
        st.session_state[_ERROR] = _replacement_error(input_key, "Price history is unavailable.")


def _add_comparison():
    try:
        history = _load_history(st.session_state.get(_COMPARE_INPUT, ""))
        primary = st.session_state.get(_PRIMARY)
        symbols = {item["symbol"] for item in st.session_state.get(_COMPARISONS, [])}
        if primary:
            symbols.add(primary["symbol"])
        if history["symbol"] in symbols:
            raise ValueError(f"{history['symbol']} is already on this workspace.")
        st.session_state[_COMPARISONS] = [
            *st.session_state.get(_COMPARISONS, []), history
        ]
        st.session_state[_ERROR] = None
        st.session_state[_COMPARE_INPUT] = ""
    except ValueError as exc:
        st.session_state[_ERROR] = str(exc)
    except Exception:
        st.session_state[_ERROR] = "Could not load that comparison. Existing charts are unchanged."


def _remove_comparison(symbol):
    st.session_state[_COMPARISONS] = [
        item for item in st.session_state.get(_COMPARISONS, [])
        if item["symbol"] != symbol
    ]


def _remove_last_comparison():
    items = list(st.session_state.get(_COMPARISONS, []))
    if items:
        items.pop()
    st.session_state[_COMPARISONS] = items


def _remove_all_comparisons():
    st.session_state[_COMPARISONS] = []


def _remove_chart():
    st.session_state[_PRIMARY] = None
    st.session_state[_REMOVED] = True
    st.session_state[_ERROR] = None


def _restore_default():
    """Load the real SOXL example, including after an intentional removal."""
    try:
        history = _load_history("SOXL")
        st.session_state[_PRIMARY] = history
        st.session_state[_DATE_INPUT] = date.fromisoformat(
            history["dates"][-1]
        ) + timedelta(days=365)
        st.session_state[POSITION_DATE] = date.fromisoformat(history["dates"][-1])
        st.session_state[_AUTO_INIT] = True
        st.session_state[_REMOVED] = False
        st.session_state[_ERROR] = None
    except Exception:
        st.session_state[_ERROR] = "SOXL history is temporarily unavailable. Select Show SOXL example to retry."


def _price(value):
    return "Not available" if value is None else f"${float(value):,.2f}"


def _probability(value):
    if value is None:
        return "Not available"
    if 0 < value < .001:
        return "<0.1%"
    if .999 < value < 1:
        return ">99.9%"
    return f"{float(value):.1%}"


def _comparison_points(primary, comparison):
    p = dict(zip(primary["dates"], primary["prices"]))
    c = dict(zip(comparison["dates"], comparison["prices"]))
    common = next((day for day in primary["dates"] if day in c), None)
    if common is None or not c[common]:
        return [], [], []
    factor = p[common] / c[common]
    days = [day for day in comparison["dates"] if day in p]
    return days, [c[day] * factor for day in days], [c[day] for day in days]


def _make_figure(primary, comparisons, model, readouts):
    fig = go.Figure()
    if primary:
        # Pin the bottom of the log plot so the shaded buy zone has a stable floor.
        buy_zone = model.get("lower_buy_zone", []) if model else []
        positive_values = [
            float(value) for value in primary["prices"] if value and float(value) > 0
        ]
        if model:
            positive_values += [
                float(value)
                for line in model.get("lines", {}).values()
                for value in line if value and float(value) > 0
            ]
        positive_values += [
            float(value) for value in buy_zone if value and float(value) > 0
        ]
        for comparison in comparisons:
            _, scaled, _ = _comparison_points(primary, comparison)
            positive_values += [float(value) for value in scaled if value and value > 0]
        floor = min(positive_values) * .72 if positive_values else None
        if buy_zone and floor:
            fig.add_trace(go.Scatter(
                x=model["line_dates"], y=[floor] * len(model["line_dates"]),
                mode="lines", line={"width": 0}, hoverinfo="skip",
                showlegend=False, name="Buy-zone plot floor",
            ))
            fig.add_trace(go.Scatter(
                x=model["line_dates"], y=buy_zone, mode="lines",
                line={"width": 0}, fill="tonexty",
                fillcolor="rgba(94, 137, 111, .14)",
                hoverinfo="skip", showlegend=False, name="Below buy zone",
            ))
        fig.add_trace(go.Scatter(
            x=primary["dates"], y=primary["prices"], mode="lines",
            name=f"{primary['symbol']} · actual", line={"color": "#283d3a", "width": 2.5},
            hovertemplate="%{x|%b %d, %Y}<br>Actual: $%{y:,.2f}<extra></extra>",
        ))
        custom = []
        for index, day in enumerate(model["line_dates"]):
            bits = [day]
            for kind in ("upper", "median", "lower"):
                target = model["lines"][kind][index]
                probability = (hit_probability(model, target, day)
                               if day >= model["last_date"] else None)
                bits += [
                    _price(target),
                    (_probability(probability) if day >= model["last_date"]
                     else "Historical date — not a forecast"),
                ]
            custom.append(bits)
        for kind in ("upper", "median", "lower"):
            if not model["line_dates"]:
                continue
            fig.add_trace(go.Scatter(
                x=model["line_dates"], y=model["lines"][kind], mode="lines",
                name={"upper": "Upper trend", "median": "Mean trend", "lower": "Lower trend"}[kind],
                line={"color": _COLORS[kind], "width": 2, "dash": "solid"},
                customdata=custom,
                # Plotly still emits hover events; the accessible tricolor panel
                # presents all three bands once, instead of three repeated tooltips.
                hoverinfo="none",
            ))
        palette = ["#b47a48", "#7086a0", "#9a6680", "#7e8e4c"]
        for i, comparison in enumerate(comparisons):
            days, scaled, actual = _comparison_points(primary, comparison)
            if days:
                fig.add_trace(go.Scatter(
                    x=days, y=scaled, mode="lines", name=f"{comparison['symbol']} · normalized",
                    line={"color": palette[i % len(palette)], "width": 1.8},
                    customdata=actual,
                    hovertemplate=(
                        "%{x|%b %d, %Y}<br>Normalized: $%{y:,.2f}"
                        "<br>Actual stock price: $%{customdata:,.2f}<extra></extra>"
                    ),
                ))
    fig.update_layout(
        height=520, margin={"l": 18, "r": 18, "t": 18, "b": 38},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#40504e", "family": "sans-serif", "size": 13},
        showlegend=bool(primary), hovermode="closest",
        hoverlabel={"font": {"size": 18}, "namelength": -1},
        dragmode="pan",
        legend={"orientation": "h", "y": 1.08, "x": 0},
        xaxis={"title": "Date", "showgrid": True, "gridcolor": "rgba(91,111,106,.13)",
               "zeroline": False, "rangeslider": {"visible": False}},
        yaxis={"title": "Price (USD; comparisons rebased)", "type": "log",
                 "automargin": True,
                 "tickprefix": "$", "tickformat": "$,.2~f", "showgrid": True,
                 "showexponent": "none", "minorloglabels": "none",
                "gridcolor": "rgba(91,111,106,.13)", "zeroline": False,
                 **({"range": [math.log10(floor),
                               math.log10(max(positive_values) * 1.08)]}
                   if primary and floor and positive_values else {})},
    )
    if primary and positive_values:
        low, high = math.log10(floor), math.log10(max(positive_values)*1.15)
        ticks = [10**(low+(high-low)*i/5) for i in range(6)]
        labels = [
            f"${value:,.2f}" if value < 1 else
            f"${value:,.1f}".rstrip("0").rstrip(".") if value < 10 else
            f"${value:,.0f}" for value in ticks
        ]
        fig.update_yaxes(tickmode="array", tickvals=ticks, ticktext=labels,
                         minor={"ticks": "", "showgrid": False},
                         minorloglabels="none")
    return fig


def _render_readouts(rows, selected_date):
    colors = _COLORS
    columns = st.columns(3)
    for column, row in zip(columns, rows):
        with column:
            st.markdown(
                f"<div style='border-top:3px solid {colors[row['kind']]};padding:10px 4px 2px'>"
                f"<div style='font-size:12px;letter-spacing:.08em;text-transform:uppercase;"
                f"color:{colors[row['kind']]}'>{row['label']}</div></div>",
                unsafe_allow_html=True,
            )
            st.metric("Target stock price", _price(row["target_price"]))
            st.metric("Probability of hitting by date", _probability(row["hit_probability"]))
            st.caption(f"By {selected_date:%b %d, %Y}")
    st.caption(
        "Historical-model estimates are not empirically calibrated. Probability means a "
        "future touch of the date-specific price target, not a touch of a moving trendline."
    )


def _winner_reading(primary):
    """Share the exact same absolute scores across both readouts."""
    try:
        analysis = analyze_winner(primary)
    except Exception:
        return None, None, []
    return analysis, normalize_scores(analysis), []


def _render_winner_analysis(primary, reading):
    """Expose components and both event cohorts without changing page two."""
    if not primary:
        return
    analysis, scores, unavailable = reading
    if analysis is None:
        st.write("Mean-reversion analysis needs adjusted history that is not currently available.")
        return
    render_score_details(analysis, scores, _SCORE_STYLE, primary)


@st.fragment
def render_mean_reversion_workspace():
    """Render the independent Mean Reversion stock-analysis workspace."""
    st.markdown(
        """
        <style>
        .stApp:has(.mr-workspace-marker) [data-testid="stMainBlockContainer"] {
            padding-top: 2.5rem;
        }
        </style>
        <div class="mr-workspace-marker" aria-hidden="true"></div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("mr_replace_primary_top_form"):
        a, b = st.columns([5, 1])
        a.text_input("Enter stock ticker", key=_TOP_PRIMARY_INPUT,
                     placeholder="SOXL, AAPL, or another ticker")
        b.write("")
        st.form_submit_button("Replace primary", type="primary",
                              use_container_width=True, on_click=_replace_primary,
                              args=(_TOP_PRIMARY_INPUT,))
    for key, initial in ((_COMPARISONS, []), (_ERROR, None), (_AUTO_INIT, False)):
        if key not in st.session_state:
            st.session_state[key] = initial
    # A failed first request must not permanently mark an empty chart initialized.
    # Also recover already-open sessions left empty by the old initialization.
    if not st.session_state.get(_PRIMARY) and not st.session_state.get(_REMOVED):
        with st.spinner("Loading the SOXL example…"):
            _restore_default()

    primary = st.session_state.get(_PRIMARY)
    if st.session_state.get(_ERROR):
        st.markdown(
            "<div class='mr-input-feedback' role='status' "
            "style='font-size:24px;font-weight:800;color:#111'>"
            f"{escape(st.session_state[_ERROR])}</div>",
            unsafe_allow_html=True,
        )
    reading = _winner_reading(primary) if primary else (None, None, [])
    if not primary:
        if st.session_state.get(_ERROR):
            st.error(st.session_state[_ERROR])
        if st.session_state.get(_REMOVED):
            st.info("No stock selected. Enter a ticker above or restore the SOXL example.")
        else:
            st.info("Stock analysis is unavailable until a ticker can be loaded. Enter a ticker above to retry.")
    model, rows, selected = None, [], None
    if primary:
        last = date.fromisoformat(primary["dates"][-1])
        maximum = date.max
        suggested = last + timedelta(days=365)
        value = st.session_state.get(_DATE_INPUT, suggested)
        if value < last:
            value = last
        if value > maximum:
            value = maximum
        st.session_state[_DATE_INPUT] = value
        with st.spinner("Fitting the price channel…"):
            try:
                model = _cached_channel(primary, value.isoformat())
            except ValueError:
                st.write("That projection exceeds the numerical price range. Showing the fitted history; choose an earlier end date.")
                value = last
                st.session_state[_DATE_INPUT] = value
                model = _cached_channel(primary, value.isoformat())
        selected = value
        rows = channel_readout(model, selected) if model.get("has_mean") else []

    if primary:
        render_stock_readout(
            primary, _cached_company_name(primary["symbol"]), reading[0], reading[1],
            channel=model,
        )
        st.date_input(
            "Projection and readout date",
            min_value=date.fromisoformat(primary["dates"][-1]),
            max_value=date.max,
            key=_DATE_INPUT,
            help="Extend all three fixed, straight trend lines to your chosen date, including 100 years ahead.",
        )

    comparisons = st.session_state.get(_COMPARISONS, [])
    render_channel_chart(
        _make_figure(primary, comparisons, model, rows),
        primary, model, rows, selected,
    )

    controls = st.columns([1, 1, 1, 2])
    controls[0].button("Remove chart", on_click=_remove_chart, disabled=not primary,
                       key="mr_remove_primary")
    controls[1].button("Remove last added", on_click=_remove_last_comparison,
                       disabled=not comparisons, key="mr_remove_last_comparison")
    controls[2].button("Remove all comparisons", on_click=_remove_all_comparisons,
                       disabled=not comparisons, key="mr_remove_all_comparisons")
    controls[3].caption(
        f"{primary['symbol']} · adjusted daily close · through {primary.get('through', '—')}"
        if primary else "No primary chart selected."
    )
    if not primary:
        st.button("Show SOXL example", on_click=_restore_default,
                  key="mr_restore_default", type="primary")

    _render_winner_analysis(primary, reading)

    with st.form("mr_replace_primary_form"):
        a, b = st.columns([5, 1])
        a.text_input("Primary ticker · replaces current primary", key=_PRIMARY_INPUT,
                     placeholder="SOXL, AAPL, or another ticker")
        b.write("")
        st.form_submit_button("Replace primary", type="primary",
                              use_container_width=True, on_click=_replace_primary)
    with st.container(border=True):
        st.subheader("Compare stocks")
        with st.form("mr_add_comparison_form"):
            a, b = st.columns([5, 1])
            a.text_input("Add comparison stock", key=_COMPARE_INPUT,
                         placeholder="Add a second, third, or fourth stock")
            b.write("")
            st.form_submit_button("Add comparison", use_container_width=True,
                                  on_click=_add_comparison)

    for history in comparisons:
        left, right = st.columns([1, 5])
        left.button(f"Remove {history['symbol']}", key=f"mr_remove_{history['symbol']}",
                    on_click=_remove_comparison, args=(history["symbol"],))
        right.caption(
            f"{history['symbol']} · normalized to primary price at first common date · "
            f"true adjusted prices remain available on hover"
        )
    if st.session_state.get(_ERROR) and primary:
        st.error(st.session_state[_ERROR])

    if rows:
        _render_readouts(rows, selected)

    render_illustrated_rankings()

    if model:
        with st.expander("Mean-reversion method"):
            st.write(
                "The chart uses three fixed, straight log-price trend lines fitted "
                "to the full available history, matching the SOXL chart. Its "
                "displayed slope and above/below-mean distance refer to that "
                "fixed chart mean. The recovery scores below use the separate "
                "walk-forward calculation described here."
            )
            st.write(
                "Use full adjusted-close history. Starting after five calendar years, "
                "fit each day's trend to the preceding five years, excluding that day's close. "
                "The latest slope is annualized with exp(slope) − 1."
            )
            st.write(
                "Closeness is the percentage of eligible closes within ±10% of their "
                "same-day predicted trend. A departure is counted once until a close "
                "returns to that daily band. Recovery uses the opening day's frozen "
                "straight-line trend projection, not a later refit. Half the opening "
                "log gap must close. Only events with five calendar years of follow-up "
                "enter all three recovery percentages; newer events are separate."
            )
            st.write(
                "Recovery = 0.90 × five-year + 0.075 × three-year + 0.025 × one-year "
                "recovery percentages, using the same mature events. With fewer than "
                "three mature events, use closeness alone. Mean Reversion Score is "
                "the higher of closeness and recovery."
            )
            st.write(
                "Median growth uses all eligible daily annualized slopes. Positive-year "
                "share uses the last eligible slope of each completed calendar year; "
                "the incomplete final year is excluded. Both rankings share a growth "
                "verdict: median slope ≥5%, positive-year share ≥60%, and reversion ≥60. "
                "Base = 100 × sqrt(clipped(median growth / 35%) × reversion / 100)."
            )
            st.write(
                "Steel Hands = base × (0.75 + 0.25 × B). B is the capped median "
                "opening depth of mature recovered downside events / 50%, times "
                "the mature five-year downside recovery fraction; B = 0 below three "
                "mature downside events. Paper Hands = base × (0.70 + 0.30 × U) × "
                "(1 − 0.65 × D), where U is positive-year share and D is the capped "
                "90th-percentile daily drawdown / 50%. Each drawdown uses the preceding "
                "252 closes, excluding its own close. Deep dip is independent of winner "
                "status: gap <−10%, percentile ≤10, at least three mature downside "
                "events ≥75% of today's depth, and at least 60% recovered in five years."
            )
        with st.expander("Channel and probability method"):
            st.write(
                "Chart slope is full-history OLS in log price. Upper, mean, and lower "
                "lines use the maximum, median, and minimum residual intercept, "
                "matching the SOXL automatic channel. All three remain straight "
                "and extend to the selected future date; they are not rolling bands. "
                "Touch probabilities use historical daily log-return drift and volatility "
                "with a directional first-passage model, including downward targets. "
                "They concern the fixed price shown for the selected date, not ending "
                "above that price or touching a moving channel."
            )

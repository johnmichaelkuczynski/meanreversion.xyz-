"""Chart-first stock research workspace for the Mean Reversion page."""

from datetime import date, timedelta
import math

import plotly.graph_objects as go
import streamlit as st

from mean_reversion_channels import CHANNELS, channel_readout, hit_probability
from mean_reversion_examples import render_illustrated_rankings
from mean_reversion_readout import POSITION_DATE, render_stock_readout
from mean_reversion_winner import (
    REFERENCE_SYMBOLS,
    analyze_winner,
    fit_winner_channel,
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
    return fit_winner_channel(history, end_date=end_date)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_reference_analyses():
    """Load the complete reference set; never normalize against a partial set."""
    analyses = {}
    unavailable = []
    for symbol in REFERENCE_SYMBOLS:
        try:
            analyses[symbol] = analyze_winner(_cached_stock_history(symbol))
        except Exception:
            unavailable.append(symbol)
    return analyses, unavailable


def _load_history(symbol):
    symbol = normalize_stock_symbol(symbol)
    return _cached_stock_history("AAPL" if symbol == "APPL" else symbol)


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
        st.session_state[_ERROR] = str(exc)
    except Exception:
        st.session_state[_ERROR] = "Could not load that stock. Your current chart is unchanged."


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
                bits += [_price(target), _probability(probability)]
            custom.append(bits)
        for kind in ("upper", "median", "lower"):
            fig.add_trace(go.Scatter(
                x=model["line_dates"], y=model["lines"][kind], mode="lines",
                name={"upper": "Upper trend", "median": "Mean line (OLS)", "lower": "Lower trend"}[kind],
                line={"color": _COLORS[kind], "width": 2, "dash": "dash" if kind != "median" else "solid"},
                customdata=custom,
                hovertemplate=(
                    "%{customdata[0]} · %{fullData.name}: $%{y:,.2f}"
                    "<br>Same-date targets · hit by or before this date:"
                    "<br>Upper %{customdata[1]} · %{customdata[2]}"
                    "<br>Mean line (OLS) %{customdata[3]} · %{customdata[4]}"
                    "<br>Lower %{customdata[5]} · %{customdata[6]}<extra></extra>"
                ),
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
        showlegend=bool(primary), hovermode="x unified",
        legend={"orientation": "h", "y": 1.08, "x": 0},
        xaxis={"title": "Date", "showgrid": True, "gridcolor": "rgba(91,111,106,.13)",
               "zeroline": False, "rangeslider": {"visible": False}},
        yaxis={"title": "Price (USD; comparisons rebased)", "type": "log",
                 "tickprefix": "$", "tickformat": ",.2f", "showgrid": True,
                 "showexponent": "none", "minorloglabels": "none",
                "gridcolor": "rgba(91,111,106,.13)", "zeroline": False,
                 **({"range": [math.log10(floor),
                               math.log10(max(positive_values) * 1.08)]}
                   if primary and floor and positive_values else {})},
    )
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
    """Share the exact same analysis and normalization across both readouts."""
    try:
        analysis = analyze_winner(primary)
    except Exception:
        return None, None, []
    references, unavailable = _cached_reference_analyses()
    complete_references = not unavailable and all(
        symbol in references for symbol in REFERENCE_SYMBOLS
    )
    try:
        scores = normalize_scores(analysis, references) if complete_references else None
    except ValueError:
        scores = None
    return analysis, scores, unavailable


def _render_winner_analysis(primary, reading):
    """Plain-language mean-reversion analysis and fully-scaled reference scores."""
    if not primary:
        return
    analysis, scores, unavailable = reading
    if analysis is None:
        st.write("Mean-reversion analysis needs adjusted history that is not currently available.")
        return
    complete_references = not unavailable

    st.subheader("Mean-reversion read")
    st.caption(
        "A direct stock screen: how strongly price returns to its long-run mean, "
        "and whether that mean has been growing."
    )
    style = st.radio(
        "Score emphasis", ("Steel hands", "Paper hands"),
        horizontal=True, key=_SCORE_STYLE,
        help="Both scores remain visible; this choice only changes which is emphasized.",
    )
    if unavailable or not complete_references:
        missing = ", ".join(unavailable or REFERENCE_SYMBOLS)
        st.write(
            f"Reference scaling unavailable — missing history for {missing}. "
            "Scores are withheld rather than normalized against a partial set."
        )

    verdict = analysis.get("verdict", "NO MEAN YET")
    winner = bool(analysis.get("winner"))
    verdict_color = "#527b5d" if winner else "#a25e4b"
    with st.container(border=True):
        st.markdown(
            f"<div style='font-size:11px;letter-spacing:.12em;text-transform:uppercase;"
            f"color:{verdict_color};font-weight:700'>Verdict</div>"
            f"<div style='font-size:25px;font-weight:650;color:#293b38;margin:.15rem 0'>"
            f"{'WINNER' if winner else 'NOT A WINNER'}</div>",
            unsafe_allow_html=True,
        )
        if not winner:
            reason = verdict.replace(" — not a winner.", "").replace(" — not a winner", "")
            st.write(reason)
        if analysis.get("range_tradeable"):
            st.caption("Range-tradeable: buy only when clearly below the mean.")

        steel = scores.get("steel") if scores is not None else None
        paper = scores.get("paper") if scores is not None else None
        prominent = steel if style == "Steel hands" else paper
        other = paper if style == "Steel hands" else steel
        other_label = "Paper hands" if style == "Steel hands" else "Steel hands"
        score_cols = st.columns([1.5, 1])
        score_cols[0].metric(
            f"{style} score · 0–100",
            f"{prominent:.1f}" if prominent is not None else "Unavailable",
        )
        score_cols[1].metric(
            other_label,
            f"{other:.1f}" if other is not None else "Unavailable",
        )

        slope_pct = analysis.get("slope_pct")
        growth = analysis.get("growth")
        if slope_pct is None and growth is not None:
            slope_pct = float(growth) * 100
        slope_text = f"{slope_pct:.2f}% per year" if slope_pct is not None else "Unavailable"
        pull = analysis.get("pull")
        pull_label = analysis.get("pull_label")
        pull_text = f"{pull_label} pull" if pull_label else "Unavailable"
        years = analysis.get("longest_years")
        peak_pct = analysis.get("longest_peak_pct")
        distance = (
            f"{years:.2f} years, up to {peak_pct:.1f}% away"
            if years is not None and peak_pct is not None else "Unavailable"
        )
        swing = analysis.get("typical_swing_pct")
        metric_cols = st.columns(3)
        metric_cols[0].metric("Mean line growth", slope_text)
        st.write(
            f"Mean line {'rising' if slope_pct >= 0 else 'declining'} "
            f"{abs(slope_pct):.2f}% per year."
        )
        metric_cols[1].metric("Pull to the mean", pull_text)
        metric_cols[2].metric("Typical swing", f"{swing:.1f}% from mean" if swing is not None else "Unavailable")
        st.caption(f"Longest time away from the mean: {distance}.")

        if analysis.get("has_mean"):
            position = analysis.get("position_pct")
            percentile = analysis.get("percentile")
            side = "above" if position is not None and position >= 0 else "below"
            position_text = (
                f"{abs(position):.1f}% {side} the mean line"
                if position is not None else "Position unavailable"
            )
            percentile_text = (
                f"higher than {percentile:.1f}% of its history"
                if percentile is not None else "historical percentile unavailable"
            )
            st.markdown(f"**Today:** {position_text} — {percentile_text}.")
            if analysis.get("buy_zone"):
                st.write("Clearly below the mean.")
            else:
                st.caption("Not currently in the clearly-below-mean buy zone.")


@st.fragment
def render_mean_reversion_workspace():
    """Render the independent Mean Reversion stock-analysis workspace."""
    st.title("Mean Reversion")
    st.caption("Price history, long-run channel, and date-specific target estimates.")
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
    reading = _winner_reading(primary) if primary else (None, None, [])
    if primary and reading[0] is not None:
        render_stock_readout(primary, _cached_company_name(primary["symbol"]),
                             reading[0], reading[1])
    elif primary:
        st.header(f"{primary['symbol']} — {_cached_company_name(primary['symbol'])}", anchor=False)
        st.write("Mean-reversion analysis unavailable.")
    model, rows, selected = None, [], None
    if primary:
        last = date.fromisoformat(primary["dates"][-1])
        maximum = last + timedelta(days=365 * 10)
        suggested = last + timedelta(days=365)
        value = st.session_state.get(_DATE_INPUT, suggested)
        if value < last:
            value = last
        if value > maximum:
            value = maximum
        st.session_state[_DATE_INPUT] = value
        with st.spinner("Fitting the price channel…"):
            model = _cached_channel(primary, value.isoformat())
        selected = value
        rows = channel_readout(model, selected)

    if primary:
        st.date_input(
            "Projection and readout date",
            min_value=date.fromisoformat(primary["dates"][-1]),
            max_value=date.fromisoformat(primary["dates"][-1]) + timedelta(days=365 * 10),
            key=_DATE_INPUT,
            help="Choose a future target date. The channel extends through this date.",
        )

    comparisons = st.session_state.get(_COMPARISONS, [])
    if primary:
        st.header(f"{primary['symbol']} · Mean Reversion", anchor=False)
    st.plotly_chart(
        _make_figure(primary, comparisons, model, rows),
        use_container_width=True,
        config={"displaylogo": False, "scrollZoom": True},
        key="mean_reversion_workspace_chart",
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
    if st.session_state.get(_ERROR):
        st.error(st.session_state[_ERROR])

    if model:
        _render_readouts(rows, selected)

    render_illustrated_rankings()

    if model:
        with st.expander("Mean-reversion method"):
            st.write(
                "Daily adjusted closes are fitted as a straight OLS line in log-price "
                "over the full history. The mean-line slope is annualized growth. Swing "
                "size is the standard deviation of log-price deviations from that line."
            )
            st.write(
                "Pull smooths deviations with a 20-trading-day moving average, then "
                "measures every excursion from one zero-crossing to the next, including "
                "open excursions at either end of the history. Each excursion is the "
                "area of absolute distance over time; the longest excursion (L) is an "
                "area, not a duration in years. Pull is 1 / (1 + L / 8)."
            )
            st.write(
                "Winner rules: at least five years of history, pull of at least 0.5, "
                "and mean-line growth of at least 5% per year. Winners receive Steel "
                "Hands and Paper Hands heuristic scores; these are not probabilities. "
                "Scores are scaled to the fixed SOXL, TQQQ, SOXX, QQQ, and SPY reference "
                "set, so they are withheld if any reference history is unavailable."
            )
            st.write(
                "Position compares today's deviation with all historical deviations. "
                "The buy zone begins 0.5 swing units below the mean. A stock with a "
                "strong pull and a mean declining no faster than 10% per year may be "
                "range-tradeable, but is not labeled a growth-stock winner."
            )
        with st.expander("Channel and probability method"):
            st.write(
                "The center line is the full-history OLS mean in log-price. The existing "
                "upper and lower channel lines remain historical reference lines, not "
                "confidence bounds. "
                "Touch probabilities use historical daily log-return drift and volatility "
                "with a directional first-passage model, including downward targets. "
                "They concern the fixed price shown for the selected date, not ending "
                "above that price or touching a moving channel."
            )

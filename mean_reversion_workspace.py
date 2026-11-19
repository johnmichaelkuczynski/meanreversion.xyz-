"""Chart-first stock research workspace for the Mean Reversion page."""

from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st

from mean_reversion_channels import CHANNELS, channel_readout, fit_channel, hit_probability
from stock_chart_api import load_stock_history, normalize_stock_symbol

_PRIMARY = "mr_workspace_primary"
_COMPARISONS = "mr_workspace_comparisons"
_ERROR = "mr_workspace_error"
_AUTO_INIT = "mr_workspace_auto_initialized"
_PRIMARY_INPUT = "mr_workspace_primary_input"
_COMPARE_INPUT = "mr_workspace_compare_input"
_DATE_INPUT = "mr_workspace_projection_date"
_COLORS = {kind: color for kind, _, color in CHANNELS}


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_stock_history(symbol):
    """Cache full available adjusted daily history."""
    return load_stock_history(symbol, start_date="1900-01-01")


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_channel(history, end_date):
    return fit_channel(history, end_date=end_date)


def _load_history(symbol):
    return _cached_stock_history(normalize_stock_symbol(symbol))


def _replace_primary():
    try:
        history = _load_history(st.session_state.get(_PRIMARY_INPUT, ""))
        st.session_state[_PRIMARY] = history
        st.session_state[_COMPARISONS] = [
            item for item in st.session_state.get(_COMPARISONS, [])
            if item["symbol"] != history["symbol"]
        ]
        last = date.fromisoformat(history["dates"][-1])
        st.session_state[_DATE_INPUT] = last + timedelta(days=365)
        st.session_state[_ERROR] = None
        st.session_state[_PRIMARY_INPUT] = ""
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
    st.session_state[_ERROR] = None


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
                name={"upper": "Upper trend", "median": "Median trend", "lower": "Lower trend"}[kind],
                line={"color": _COLORS[kind], "width": 2, "dash": "dash" if kind != "median" else "solid"},
                customdata=custom,
                hovertemplate=(
                    "%{customdata[0]} · %{fullData.name}: $%{y:,.2f}"
                    "<br>Same-date targets · hit by or before this date:"
                    "<br>Upper %{customdata[1]} · %{customdata[2]}"
                    "<br>Median %{customdata[3]} · %{customdata[4]}"
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
               "gridcolor": "rgba(91,111,106,.13)", "zeroline": False},
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


@st.fragment
def render_mean_reversion_workspace():
    """Render the independent Mean Reversion stock-analysis workspace."""
    for key, initial in ((_COMPARISONS, []), (_ERROR, None), (_AUTO_INIT, False)):
        if key not in st.session_state:
            st.session_state[key] = initial
    if not st.session_state[_AUTO_INIT]:
        st.session_state[_AUTO_INIT] = True
        try:
            st.session_state[_PRIMARY] = _load_history("SOXL")
            st.session_state[_DATE_INPUT] = date.fromisoformat(
                st.session_state[_PRIMARY]["dates"][-1]
            ) + timedelta(days=365)
        except Exception:
            st.session_state[_PRIMARY] = None
            st.session_state[_ERROR] = "SOXL history could not be loaded. Enter a ticker below to try another."

    primary = st.session_state.get(_PRIMARY)
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

    st.title("Mean Reversion")
    st.caption("Price history, long-run channel, and date-specific target estimates.")
    if primary:
        st.date_input(
            "Projection and readout date",
            min_value=date.fromisoformat(primary["dates"][-1]),
            max_value=date.fromisoformat(primary["dates"][-1]) + timedelta(days=365 * 10),
            key=_DATE_INPUT,
            help="Choose a future target date. The channel extends through this date.",
        )

    comparisons = st.session_state.get(_COMPARISONS, [])
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
        if primary else "No primary chart selected. The default SOXL load runs only once per session."
    )

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

    metrics = st.columns(3)
    metrics[0].metric("Mean reversion score", "Pending new logic")
    metrics[1].metric(
        "Growth / trend · annualized",
        f"{model['slope_pct']:.2f}%" if model else "—",
    )
    metrics[2].metric("Overall score", "Pending new logic")
    if model:
        _render_readouts(rows, selected)
        with st.expander("Channel and probability method"):
            st.write(
                "The three lines use the same log-price channel method as the SOXL page: "
                "a least-squares slope with median, highest and lowest historical intercepts. "
                "The upper and lower lines are historical envelopes, not confidence bounds. "
                "Touch probabilities use historical daily log-return drift and volatility "
                "with a directional first-passage model, including downward targets. "
                "They concern the fixed price shown for the selected date, not ending "
                "above that price or touching a moving channel."
            )

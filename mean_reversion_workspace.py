"""Top-of-page stock research workspace for the Mean Reversion section."""

import streamlit as st
import plotly.graph_objects as go

from stock_chart_api import load_stock_history, normalize_stock_symbol


_SYMBOLS_KEY = "mean_reversion_workspace_symbols"
_ERROR_KEY = "mean_reversion_workspace_error"
_INPUT_KEY = "mean_reversion_workspace_symbol_input"


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_stock_history(symbol):
    """Cache adjusted daily history so a symbol is fetched only on submission."""
    return load_stock_history(symbol)


def _add_submitted_symbol():
    raw_symbol = st.session_state.get(_INPUT_KEY, "")
    try:
        symbol = normalize_stock_symbol(raw_symbol)
        current = st.session_state.get(_SYMBOLS_KEY, [])
        if any(item["symbol"] == symbol for item in current):
            st.session_state[_ERROR_KEY] = f"{symbol} is already on the chart."
            return
        history = _cached_stock_history(symbol)
        st.session_state[_SYMBOLS_KEY] = [*current, history]
        st.session_state[_ERROR_KEY] = None
        st.session_state[_INPUT_KEY] = ""
    except ValueError as exc:
        st.session_state[_ERROR_KEY] = str(exc)
    except Exception:
        st.session_state[_ERROR_KEY] = (
            "Price history could not be loaded right now. Check the symbol and try again."
        )


def _remove_symbol(symbol):
    st.session_state[_SYMBOLS_KEY] = [
        item for item in st.session_state.get(_SYMBOLS_KEY, [])
        if item["symbol"] != symbol
    ]
    st.session_state[_ERROR_KEY] = None


def _remove_last_symbol():
    current = list(st.session_state.get(_SYMBOLS_KEY, []))
    if current:
        current.pop()
    st.session_state[_SYMBOLS_KEY] = current
    st.session_state[_ERROR_KEY] = None


def _remove_all_symbols():
    st.session_state[_SYMBOLS_KEY] = []
    st.session_state[_ERROR_KEY] = None


def _make_figure(symbols):
    figure = go.Figure()
    palette = ["#356b68", "#b46649", "#6977a2", "#a08245", "#8a6384", "#5f7f55"]
    for index, history in enumerate(symbols):
        figure.add_trace(
            go.Scatter(
                x=history["dates"],
                y=history["prices"],
                mode="lines",
                name=history["symbol"],
                line={"color": palette[index % len(palette)], "width": 2},
                hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.2f}<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_layout(
        height=560,
        margin={"l": 20, "r": 20, "t": 16, "b": 42},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#40504e", "family": "sans-serif", "size": 13},
        showlegend=bool(symbols),
        legend={"orientation": "h", "y": 1.08, "x": 0},
        hovermode="x unified" if symbols else False,
        xaxis={
            "title": "Date",
            "showgrid": True,
            "gridcolor": "rgba(91,111,106,0.13)",
            "zeroline": False,
            "showline": True,
            "linecolor": "rgba(91,111,106,0.32)",
            "rangeslider": {"visible": False},
        },
        yaxis={
            "title": "Adjusted close (USD)",
            "type": "log" if symbols else "linear",
            "showgrid": True,
            "gridcolor": "rgba(91,111,106,0.13)",
            "zeroline": False,
            "showline": True,
            "linecolor": "rgba(91,111,106,0.32)",
            "tickprefix": "$",
            "tickformat": ",.2f",
        },
    )
    return figure


@st.fragment
def render_mean_reversion_workspace():
    """Render the standalone, chart-first Mean Reversion workspace."""
    if _SYMBOLS_KEY not in st.session_state:
        st.session_state[_SYMBOLS_KEY] = []
    if _ERROR_KEY not in st.session_state:
        st.session_state[_ERROR_KEY] = None

    symbols = st.session_state[_SYMBOLS_KEY]
    st.title("Mean Reversion")
    st.caption(
        "A focused stock research workspace. Add a ticker to load adjusted daily "
        "price history; no market data is requested before submission."
    )

    chart_slot = st.container()
    with chart_slot:
        st.plotly_chart(
            _make_figure(symbols),
            use_container_width=True,
            config={"displaylogo": False, "scrollZoom": True},
            key="mean_reversion_workspace_chart",
        )

    for column, label in zip(st.columns(3), ("Mean reversion score", "Growth score", "Overall score")):
        column.metric(label, "—")
    st.caption(
        "Scores are not calculated: the previous calculation logic was removed. "
        "The chart displays adjusted prices, not a replacement reversion model."
    )

    if symbols:
        st.caption("Individual adjusted-close series; no rebasing or comparison scaling.")
        for history in symbols:
            symbol = history["symbol"]
            remove_column, detail_column = st.columns([1, 5])
            remove_column.button(
                f"Remove {symbol}",
                key=f"mean_reversion_remove_{symbol}",
                on_click=_remove_symbol,
                args=(symbol,),
            )
            detail_column.caption(
                f"{symbol} · {history.get('price_type', 'Adjusted daily close')} · "
                f"through {history.get('through', 'date unavailable')}"
            )
        action_columns = st.columns([1, 1, 4])
        action_columns[0].button(
            "Remove last added",
            key="mean_reversion_remove_last",
            on_click=_remove_last_symbol,
            disabled=not symbols,
        )
        action_columns[1].button(
            "Remove all charts",
            key="mean_reversion_remove_all",
            on_click=_remove_all_symbols,
            disabled=not symbols,
        )

    if st.session_state.get(_ERROR_KEY):
        st.error(st.session_state[_ERROR_KEY])

    with st.form("mean_reversion_add_symbol_form", clear_on_submit=False):
        input_column, submit_column = st.columns([5, 1])
        with input_column:
            st.text_input(
                "Ticker",
                key=_INPUT_KEY,
                placeholder="Enter a stock symbol, such as AAPL",
                help="History is loaded only after you submit a valid ticker.",
            )
        with submit_column:
            st.write("")
            st.form_submit_button(
                "Add stock",
                type="primary",
                use_container_width=True,
                on_click=_add_submitted_symbol,
            )

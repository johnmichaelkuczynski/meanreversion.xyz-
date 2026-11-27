"""Company-name lookup, separate from stock analysis and access decisions."""

import re

import requests
import streamlit as st

QUERY_KEY = "mr_ticker_lookup_query"
RESULTS_KEY = "mr_ticker_lookup_results"
ERROR_KEY = "mr_ticker_lookup_error"
SEARCHED_KEY = "mr_ticker_lookup_searched"


class TickerLookupUnavailable(RuntimeError):
    pass


@st.cache_data(ttl=900, max_entries=256, show_spinner=False)
def search_stock_tickers(query):
    """Search real Tiingo security names; never request price history."""
    import os

    query = " ".join(str(query or "").split())
    if not 2 <= len(query) <= 80:
        raise ValueError("Enter at least two letters of a company name or ticker.")
    key = os.environ.get("TIINGO_API_KEY", "").strip()
    if not key:
        raise TickerLookupUnavailable("Ticker lookup is not configured.")
    try:
        response = requests.get(
            "https://api.tiingo.com/tiingo/utilities/search",
            params={"query": query},
            headers={"Authorization": "Token " + key},
            timeout=(3, 8),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Unexpected security-search response.")
    except (requests.RequestException, ValueError):
        raise TickerLookupUnavailable("Ticker lookup is temporarily unavailable.") from None
    results, seen = [], set()
    for row in payload:
        if not isinstance(row, dict) or row.get("isActive") is False:
            continue
        symbol = str(row.get("ticker") or "").strip().upper()
        name = " ".join(str(row.get("name") or "").split())
        asset_type = str(row.get("assetType") or "").casefold()
        if asset_type not in {"", "stock", "etf", "mutual fund", "fund"}:
            continue
        if not name or not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,29}", symbol):
            continue
        if symbol not in seen:
            results.append({"symbol": symbol, "name": name})
            seen.add(symbol)
    results.sort(key=lambda item: item["symbol"].casefold() != query.casefold())
    return results[:8]


def _search():
    query = " ".join(st.session_state.get(QUERY_KEY, "").split())
    st.session_state[SEARCHED_KEY] = query
    st.session_state[RESULTS_KEY] = []
    st.session_state.pop(ERROR_KEY, None)
    try:
        st.session_state[RESULTS_KEY] = search_stock_tickers(query.casefold())
    except ValueError as error:
        st.session_state[ERROR_KEY] = str(error)
    except TickerLookupUnavailable:
        st.session_state[ERROR_KEY] = (
            "Ticker lookup is temporarily unavailable. Please try again. "
            "You can still enter a ticker below."
        )


def render_ticker_lookup(on_select):
    """A compact lookup above the existing ticker entry; no work on page load."""
    with st.container(border=True, width=560, key="mr_ticker_lookup_box"):
        with st.form("mr_ticker_lookup_form", border=False):
            name, action = st.columns([4, 1], vertical_alignment="bottom")
            name.text_input(
                "Find a stock ticker by company name",
                placeholder="e.g. Disney",
                key=QUERY_KEY,
                max_chars=80,
            )
            action.form_submit_button("Look up", on_click=_search, use_container_width=True)
        error = st.session_state.get(ERROR_KEY)
        if error:
            st.info(error)
        elif SEARCHED_KEY in st.session_state:
            results = st.session_state.get(RESULTS_KEY, [])
            if not results:
                st.info("No matching stocks found. Try another company name or spelling.")
            else:
                st.caption(f"Matches for “{st.session_state[SEARCHED_KEY]}” — select one to analyze:")
                for row in results:
                    st.button(
                        f"{row['symbol']} — {row['name']}",
                        key=f"mr_lookup_use_{row['symbol']}",
                        on_click=on_select,
                        args=(row["symbol"],),
                        use_container_width=True,
                    )

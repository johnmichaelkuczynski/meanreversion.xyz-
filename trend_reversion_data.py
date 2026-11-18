"""Full adjusted-history adapter using the app's existing owner-key providers.

The existing stock-chart endpoint intentionally starts in 2000. This isolated
adapter copies that request/normalization pattern with an all-history start;
it never changes the endpoint, its defaults, or the existing chart's history.
"""
from datetime import date
import os

import numpy as np
import pandas as pd
import requests
import streamlit as st

from stock_chart_api import normalize_stock_symbol


@st.cache_data(ttl=86400, max_entries=128, show_spinner=False)
def _history(symbol, day):
    if os.environ.get("TIINGO_API_KEY", "").strip():
        code = symbol.removesuffix(".US").replace(".", "-")
        try:
            response = requests.get(
                f"https://api.tiingo.com/tiingo/daily/{code}/prices",
                params={"startDate": "1800-01-01", "endDate": day, "resampleFreq": "daily"},
                headers={"Authorization": "Token " + os.environ["TIINGO_API_KEY"].strip()},
                timeout=45,
            )
        except requests.RequestException:
            raise ValueError("Daily history is temporarily unavailable. Try again shortly.") from None
        if response.status_code == 404:
            raise ValueError(f"Unknown ticker: {symbol}. Check the symbol.")
        if response.status_code in (401, 403):
            raise ValueError("The configured Tiingo account cannot access this daily history.")
        if not response.ok:
            raise ValueError("The daily-history service is temporarily unavailable. Try again shortly.")
        try:
            rows = response.json()
        except ValueError:
            raise ValueError("The daily-history service returned an invalid response.") from None
        frame = pd.DataFrame(rows) if isinstance(rows, list) else pd.DataFrame()
        column = "adjClose"
        source = "Tiingo"
    elif os.environ.get("EODHD_API_KEY", "").strip():
        # Existing provider fallback, explicitly full history and adjusted only.
        from data_providers import get_equity_history, normalize_eodhd_symbol
        code = normalize_eodhd_symbol(symbol)
        base, exchange = code.rsplit(".", 1)
        frame = get_equity_history(base, years=250, suffix=f".{exchange}").reset_index()
        column = "adj_close"
        source = "EODHD"
    else:
        raise ValueError("The existing daily-history provider is not configured.")
    if frame.empty:
        raise ValueError(f"Unknown ticker or no daily history: {symbol}.")
    if column not in frame or "date" not in frame:
        raise ValueError(f"Adjusted daily closes are unavailable for {symbol}.")
    frame = pd.DataFrame({
        "date": pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.tz_localize(None),
        "price": pd.to_numeric(frame[column], errors="coerce"),
    }).dropna().sort_values("date").drop_duplicates("date", keep="last")
    frame = frame[np.isfinite(frame["price"]) & (frame["price"] > 0)]
    if frame.empty:
        raise ValueError(f"No valid adjusted daily closes were found for {symbol}.")
    return {
        "symbol": symbol, "dates": frame["date"].dt.strftime("%Y-%m-%d").tolist(),
        "prices": frame["price"].astype(float).tolist(), "source": source,
    }


def load_history(symbol):
    return _history(normalize_stock_symbol(symbol), date.today().isoformat())

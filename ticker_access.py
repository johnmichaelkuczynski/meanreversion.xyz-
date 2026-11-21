"""Ticker/page access and one-click native Google-to-Stripe continuation."""
import json
import logging
from urllib.parse import urlencode

import streamlit as st

from auth import get_current_user, is_development_preview, is_owner, is_verified_google_user
from account_header import paid_access_for_current_user
from billing import create_checkout, get_plan
from google_oauth import configure_google_auth
from ticker_purchase_routes import departure_url, read_intent

FREE_TICKERS = frozenset({"SOXL", "QQQ", "AAPL"})
logger = logging.getLogger(__name__)


def can_analyze_ticker(symbol):
    return symbol in FREE_TICKERS or has_full_access()


def has_full_access():
    """Full-page access never inherits page one's free-ticker exemption."""
    if is_development_preview():
        return True
    user = get_current_user()
    if is_owner(user):
        return True
    if not is_verified_google_user(user):
        return False
    try:
        return paid_access_for_current_user()
    except Exception as exc:
        logger.warning("Ticker entitlement unavailable (%s)", type(exc).__name__)
        return False


def navigate(destination):
    # Native document navigation, not an iframe popup or a second submit step.
    st.html(
        "<script>window.location.assign(" + json.dumps(destination) + ");</script>",
        unsafe_allow_javascript=True,
    )


def render_ticker_unlock(symbol, error=None):
    _render_unlock(f"Analyzing {symbol} requires full access — $1,500", symbol, error)


def render_soxl_unlock():
    _render_unlock("The SOXL page requires full access — $1,500", "SOXL")


def _render_unlock(message, symbol, error=None):
    with st.container(border=True, key="mr_ticker_unlock"):
        st.write(message)
        if error:
            st.write(error)
        if st.button("Get full access", key="mr_get_full_access", type="primary"):
            navigate("/api/full-access/start?" + urlencode({"ticker": symbol}))


def resume_ticker_purchase():
    """A signed browser cookie survives native OAuth's new Streamlit session."""
    symbol = read_intent(st.context.cookies)
    if not symbol:
        return False
    user = get_current_user()
    try:
        # A stale intent must never send an owner, development user or buyer to pay.
        if is_development_preview() or is_owner(user):
            navigate(departure_url("/"))
        elif not is_verified_google_user(user):
            configure_google_auth()
            st.login("google")
        elif paid_access_for_current_user(force=True):
            navigate(departure_url("/"))
        else:
            plan = get_plan()
            if plan["amount"] != 150000 or plan["currency"].lower() != "usd":
                raise ValueError("Configured price differs from the advertised fee")
            checkout = create_checkout(user)
            navigate(departure_url(checkout["url"]))
    except Exception as exc:
        logger.warning("Ticker checkout unavailable (%s)", type(exc).__name__)
        # Clear the intent through an HTTP response: a provider failure must not
        # trap the browser in an automatic login/checkout loop or block free use.
        destination = "/?" + urlencode({"requested_ticker": symbol, "checkout_error": "1"})
        navigate(departure_url(destination))
    return True

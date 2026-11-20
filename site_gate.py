"""Google-and-payment entry gate, shared by every Streamlit application page."""
import logging
import time

import streamlit as st

from access import PAID_ACCESS_SESSION_KEY, PAID_SUBJECT_SESSION_KEY
from account_header import _handle_checkout_return, paid_access_for_current_user
from auth import admin_emails, get_current_user, is_admin, is_development_preview, is_verified_google_user
from billing import BillingError, create_checkout, get_plan
from site_welcome import render_welcome_readme

logger = logging.getLogger(__name__)


def _record_access(user, allowed, source=""):
    subject = str(user.get("sub", ""))
    if st.session_state.get(PAID_SUBJECT_SESSION_KEY) != subject:
        st.session_state.pop("_billing_access", None)
        st.session_state.pop("_site_checkout_ready", None)
    st.session_state[PAID_ACCESS_SESSION_KEY] = bool(allowed)
    st.session_state[PAID_SUBJECT_SESSION_KEY] = subject
    st.session_state["_paid_access_source"] = source if allowed else ""


def require_site_access():
    """Return True only for development, a verified admin, or a paid Google user."""
    user = get_current_user()
    _record_access(user, False)
    if is_development_preview() and user.get("is_logged_in") is True:
        _record_access(user, True, "development")
        return True
    if not is_verified_google_user(user):
        render_welcome_readme()
        st.info("Sign in with Google above, then pay the access fee to enter the app.")
        return False
    # This must precede plan lookup, checkout returns, database and Stripe calls.
    if is_admin(user):
        _record_access(user, True, "admin")
        return True
    render_setup_error = not admin_emails()
    if render_setup_error:
        render_welcome_readme()
        st.error("Access setup is incomplete. Checkout is disabled until administrator access is configured.")
        return False
    _handle_checkout_return()
    try:
        if paid_access_for_current_user():
            _record_access(user, True, "payment")
            return True
    except Exception as exc:
        logger.warning("Access verification failed (%s)", type(exc).__name__)
        render_welcome_readme()
        st.warning("We could not verify payment. Access remains locked. If you already paid, do not pay again.")
        _refresh_payment()
        return False
    render_welcome_readme()
    st.subheader("Unlock full access")
    try:
        plan = get_plan()
        if not plan.get("livemode"):
            raise BillingError("Live payment configuration is required.")
        amount = f"{plan['currency'].upper()} {plan['amount'] / 100:,.2f}"
        st.write(f"Access fee: {amount} — one-time payment.")
        # A checkout session is only a payment link, not a charge. Creating or
        # reusing it here permits a single click into Stripe, not a second
        # confirmation step. Admins and anonymous visitors never reach here.
        cached = st.session_state.get("_site_checkout_ready")
        if not cached or cached["price_id"] != plan["price_id"] or time.monotonic() >= cached["until"]:
            checkout = create_checkout(user)
            cached = {
                "price_id": plan["price_id"], "url": checkout["url"],
                "until": time.monotonic() + 300,
            }
            st.session_state["_site_checkout_ready"] = cached
        st.link_button(f"Pay {amount} and unlock the app", cached["url"], type="primary", width="stretch")
        st.caption("Stripe handles payment securely. Access opens only after payment is verified.")
    except Exception as exc:
        logger.warning("Checkout unavailable (%s)", type(exc).__name__)
        st.error("Payment is unavailable because the site's Stripe configuration could not be verified. No charge was made.")
    _refresh_payment()
    return False


def _refresh_payment():
    if st.button("Check payment status", key="site_check_payment"):
        st.session_state.pop("_billing_access", None)
        st.session_state.pop("_site_checkout_ready", None)
        st.rerun()

"""Resolve full-result entitlement without blocking the public workspaces."""
import logging
import time

import streamlit as st

from access import PAID_ACCESS_SESSION_KEY, PAID_SUBJECT_SESSION_KEY
from account_header import _handle_checkout_return, paid_access_for_current_user
from auth import admin_emails, get_current_user, is_admin, is_development_preview, is_verified_google_user
from billing import BillingError, create_checkout, get_plan
from access import has_paid_access

logger = logging.getLogger(__name__)


def _record_access(user, allowed, source=""):
    subject = str(user.get("sub", ""))
    if st.session_state.get(PAID_SUBJECT_SESSION_KEY) != subject:
        st.session_state.pop("_billing_access", None)
        st.session_state.pop("_site_checkout_ready", None)
    st.session_state[PAID_ACCESS_SESSION_KEY] = bool(allowed)
    st.session_state[PAID_SUBJECT_SESSION_KEY] = subject
    st.session_state["_paid_access_source"] = source if allowed else ""


def refresh_site_access():
    """Resolve paid results; guests and unpaid users can still use the preview."""
    user = get_current_user()
    _record_access(user, False)
    st.session_state.pop("_result_access_check_failed", None)
    if is_development_preview() and user.get("is_logged_in") is True:
        _record_access(user, True, "development")
        return True
    if not is_verified_google_user(user):
        return False
    # This must precede plan lookup, checkout returns, database and Stripe calls.
    if is_admin(user):
        _record_access(user, True, "admin")
        return True
    _handle_checkout_return()
    try:
        if paid_access_for_current_user():
            _record_access(user, True, "payment")
            return True
    except Exception as exc:
        logger.warning("Access verification failed (%s)", type(exc).__name__)
        st.session_state["_result_access_check_failed"] = True
    return False


def require_site_access():
    """Compatibility helper: whether full results (not app entry) are unlocked."""
    return refresh_site_access()


def render_unlock_prompt(key="results"):
    """Offer the existing Google/Stripe path inline, never as an entry wall."""
    if has_paid_access():
        return
    st.info(
        "You are using a redacted preview. Sign in with Google and pay to unlock "
        "the full graphs, detailed scores, projections, and results."
    )
    user = get_current_user()
    if not is_verified_google_user(user):
        st.caption("Use Sign in with Google at the top of the screen. You can keep trying tickers without signing in.")
        return
    if st.session_state.get("_result_access_check_failed"):
        st.warning("Payment could not be verified. If you already paid, do not pay again; check payment status below.")
        _refresh_payment(key)
        return
    if not admin_emails():
        st.warning("Full-access checkout is not configured yet. You can continue using the preview.")
        return
    st.subheader("Unlock full results")
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
    _refresh_payment(key)


def _refresh_payment(key="results"):
    if st.button("Check payment status", key=f"site_check_payment_{key}"):
        st.session_state.pop("_billing_access", None)
        st.session_state.pop("_site_checkout_ready", None)
        st.rerun()

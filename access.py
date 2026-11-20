"""Server-backed access policy shared by both protected application pages."""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping

import streamlit as st

from auth import get_current_user, is_development_preview, is_owner, is_verified_google_user


PAID_ACCESS_SESSION_KEY = "_paid_access_verified"
PAID_SUBJECT_SESSION_KEY = "_paid_access_subject"

GUEST = "guest"
SIGNED_IN = "signed_in"
PAID = "paid"
OWNER = "owner"


def has_unlimited_credits(user=None) -> bool:
    """Permanent exemption from application credit quotas, not provider billing."""
    return is_owner(user)

# Named feature gates within the globally protected application.
PAID_FEATURES = frozenset(
    {
        "Vol Surface",
        "Call Risk/Reward",
        "Dislocation",
        "Backtest",
        "Strategy Builder",
    }
)


def _logged_in(user: Mapping[str, Any] | None) -> bool:
    """Return the server-authenticated login state without guessing identity."""
    return bool(user and user.get("is_logged_in"))


def access_tier(
    user: Mapping[str, Any] | None = None,
    *,
    paid_verified: bool | None = None,
    preview: bool | None = None,
) -> str:
    """Use trusted identity plus an account-bound, server-verified entitlement."""
    if user is None:
        user = get_current_user()

    if not _logged_in(user):
        return GUEST

    if preview is None:
        preview = is_development_preview()
    if preview:
        return PAID

    if not is_verified_google_user(user):
        return GUEST
    if is_owner(user):
        return OWNER

    if paid_verified is None:
        paid_verified = (
            st.session_state.get(PAID_ACCESS_SESSION_KEY, False) is True
            and st.session_state.get(PAID_SUBJECT_SESSION_KEY) == str(user["sub"])
            and st.session_state.get("_paid_access_source") == "payment"
        )
    return PAID if paid_verified is True else SIGNED_IN


def has_paid_access(
    user: Mapping[str, Any] | None = None,
    *,
    paid_verified: bool | None = None,
    preview: bool | None = None,
) -> bool:
    """Require verified payment or an administrator exemption in production."""
    return access_tier(user, paid_verified=paid_verified, preview=preview) in {PAID, OWNER}


def can_use_market_chat(
    user: Mapping[str, Any] | None = None,
    *,
    paid_verified: bool | None = None,
    preview: bool | None = None,
) -> bool:
    return has_paid_access(user, paid_verified=paid_verified, preview=preview)


def can_access(
    feature: str,
    user: Mapping[str, Any] | None = None,
    *,
    paid_verified: bool | None = None,
    preview: bool | None = None,
) -> bool:
    """All app features follow the same server-side entitlement policy."""
    return has_paid_access(user, paid_verified=paid_verified, preview=preview)


def _button_key(feature: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", feature.lower()).strip("_")
    return f"buy_full_access_{slug or 'feature'}"


def render_paid_gate(
    feature: str,
    purchase_dialog: Callable[[], Any],
) -> None:
    """Render a friendly paid-feature invitation and open real checkout.

    The callback is supplied by ``app.py`` so this module does not duplicate
    checkout logic or create a second purchase path.
    """
    st.markdown(f"### {feature}")
    st.info(
        f"{feature} is part of SOXL Pro full access. "
        "Buy full access to unlock it."
    )
    if st.button(
        "Buy full access",
        key=_button_key(feature),
        type="primary",
        width="stretch",
    ):
        purchase_dialog()


def require_paid_access(
    feature: str,
    user: Mapping[str, Any] | None,
    purchase_dialog: Callable[[], Any],
    *,
    paid_verified: bool | None = None,
    preview: bool | None = None,
) -> bool:
    """Render a gate when needed and return whether feature code may run."""
    if has_paid_access(
        user, paid_verified=paid_verified, preview=preview
    ):
        return True
    render_paid_gate(feature, purchase_dialog)
    return False
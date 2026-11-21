"""Unrestricted application features, separate from optional billing status."""
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
    """Application usage is unrestricted; provider billing is unchanged."""
    return True

# Legacy feature names retained for compatibility; none restrict access.
PAID_FEATURES = frozenset(
    {
        "Vol Surface",
        "Call Risk/Reward",
        "Dislocation",
        "Backtest",
        "Strategy Builder",
    }
)
PUBLIC_FEATURES = frozenset({"Workspace", "Stock lookup", "Price preview", "Chart & Probabilities", "Snapshot"})


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
    """Report optional billing status; this never controls app feature access."""
    return access_tier(user, paid_verified=paid_verified, preview=preview) in {PAID, OWNER}


def can_use_market_chat(
    user: Mapping[str, Any] | None = None,
    *,
    paid_verified: bool | None = None,
    preview: bool | None = None,
) -> bool:
    return True


def can_access(
    feature: str,
    user: Mapping[str, Any] | None = None,
    *,
    paid_verified: bool | None = None,
    preview: bool | None = None,
) -> bool:
    """Every feature is public, independently of identity or purchase status."""
    return True


def _button_key(feature: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", feature.lower()).strip("_")
    return f"buy_full_access_{slug or 'feature'}"


def render_paid_gate(
    feature: str,
    purchase_dialog: Callable[[], Any],
) -> None:
    """Legacy compatibility: never render a gate or initiate a purchase."""
    return None


def require_paid_access(
    feature: str,
    user: Mapping[str, Any] | None,
    purchase_dialog: Callable[[], Any],
    *,
    paid_verified: bool | None = None,
    preview: bool | None = None,
) -> bool:
    """Legacy compatibility: all visitors may execute every feature."""
    return True
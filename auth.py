"""Public app identity and automatic, workspace-only development access."""
import os

import streamlit as st


def is_development_preview(environ=None):
    """Only a server-marked workspace may receive the automatic local identity."""
    env = os.environ if environ is None else environ
    if env.get("REPLIT_DEPLOYMENT", "").strip().lower() in {"1", "true", "yes"}:
        return False
    if env.get("APP_ENV", "").strip().lower() in {"production", "prod"}:
        return False
    return bool(env.get("REPLIT_DEV_DOMAIN", "").strip())


def get_current_user():
    if is_development_preview():
        return {
            "is_logged_in": True,
            "sub": "development-preview",
            "name": "Development session",
            "auth_provider": "development",
        }
    # Login was removed. Old identity cookies must not sign visitors back in.
    return {"is_logged_in": False}


def is_owner(user=None):
    """Only trusted, verified authentication claims can grant owner access.

    Callers must pass the server's authenticated identity, never form/query data.
    Re-evaluate on every request so sign-out/account switching removes the grant.
    """
    user = get_current_user() if user is None else user
    return bool(
        user
        and user.get("is_logged_in") is True
        and user.get("email_verified") is True
        and user.get("sub")
        and user.get("auth_provider") != "development"
        and str(user.get("email", "")).strip().casefold()
        == "johnmichaelkuczynski@gmail.com"
    )


def render_development_status():
    if is_development_preview():
        st.caption("Development: automatically signed in")
"""Direct Google identity and automatic, workspace-only development access."""
import os

import streamlit as st
from google_oauth import configure_google_auth


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
    return dict(st.user)


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


def render_google_login():
    if is_development_preview():
        render_development_status()
        return
    try:
        configure_google_auth()
    except Exception:
        st.button("Sign in with Google", disabled=True, width="stretch")
        st.caption("Google sign-in is not configured. You can still use the app.")
        return
    if st.user.is_logged_in:
        st.caption(f"Signed in as {st.user.get('name') or 'Google user'}")
        if st.button("Sign out", key="google_logout", width="stretch"):
            st.session_state.clear()
            st.logout()
    elif st.button("Sign in with Google", key="google_login", width="stretch"):
        try:
            st.login("google")
        except Exception:
            st.info("Google sign-in could not start. Your current app access remains available.")
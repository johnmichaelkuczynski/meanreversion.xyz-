"""Google OIDC using Streamlit's server-verified identity and signed cookies."""
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

import streamlit as st
import toml

GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"


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


def redirect_uri(environ=None, *, origin=None):
    env = os.environ if environ is None else environ
    origin = origin or env.get("PUBLIC_APP_URL", "")
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise ValueError("A valid HTTPS app origin is required for Google sign-in.")
    return origin.rstrip("/") + "/oauth2callback"


def auth_settings(environ=None, *, origin=None):
    env = os.environ if environ is None else environ
    required = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "SESSION_SECRET")
    if any(not env.get(key) for key in required):
        raise ValueError("Google sign-in configuration is incomplete.")
    return {
        "redirect_uri": redirect_uri(env, origin=origin),
        "cookie_secret": env["SESSION_SECRET"],
        "google": {
            "client_id": env["GOOGLE_CLIENT_ID"],
            "client_secret": env["GOOGLE_CLIENT_SECRET"],
            "server_metadata_url": GOOGLE_METADATA,
            "client_kwargs": {"prompt": "select_account", "scope": "openid email profile"},
        },
    }


def configure_google_auth():
    """Use the configured origin, or the current HTTPS site's actual origin."""
    origin = os.environ.get("PUBLIC_APP_URL", "").strip()
    if not origin:
        parsed = urlsplit(st.context.url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    # Validate before using the origin as a cache key or writing configuration.
    redirect_uri(origin=origin)
    return _configure_google_auth_for_origin(origin)


@st.cache_resource(show_spinner=False)
def _configure_google_auth_for_origin(origin):
    """Create Streamlit's ignored config at runtime, never expose credentials."""
    settings = auth_settings(origin=origin)
    path = Path(".streamlit/secrets.toml")
    path.parent.mkdir(exist_ok=True)
    existing = toml.loads(path.read_text()) if path.exists() else {}
    existing["auth"] = settings
    # Atomically replace a private file, preserving any unrelated settings.
    fd, temporary = tempfile.mkstemp(prefix=".auth-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(toml.dumps(existing))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    # Streamlit may have loaded the previously empty config before app startup.
    st.secrets._reset()
    return settings["redirect_uri"]


def render_google_login():
    if is_development_preview():
        # This identity is local development access, not a fabricated Google
        # session. It survives reruns, stale logout flags, and fresh browser tabs.
        st.caption("Development: automatically signed in")
        return
    try:
        configure_google_auth()
    except Exception:
        st.button("Sign in with Google", disabled=True, width="stretch")
        st.caption("Google sign-in is not configured for this site. App access remains available.")
        return
    if st.user.is_logged_in:
        st.caption(f"Signed in as {st.user.get('name') or st.user.get('email') or 'Google user'}")
        if st.button("Sign out", key="google_logout", width="stretch"):
            st.session_state.clear()
            st.logout()
    elif st.button("Sign in with Google", key="google_login", width="stretch"):
        try:
            st.login("google")
        except Exception:
            st.info("Please try signing in again. Your current app access remains available.")
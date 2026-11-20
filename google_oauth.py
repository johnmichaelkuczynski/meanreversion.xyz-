"""Direct Google OpenID Connect configuration for Streamlit's native login."""
import os
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlsplit

import streamlit as st
import toml

GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"
_configuration_lock = threading.Lock()


def redirect_uri(environ=None, *, origin=None):
    env = os.environ if environ is None else environ
    origin = (origin or env.get("PUBLIC_APP_URL", "")).strip()
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise ValueError("Google login requires an HTTPS app origin without a path.")
    return origin.rstrip("/") + "/oauth2callback"


def auth_settings(environ=None, *, origin=None):
    env = os.environ if environ is None else environ
    required = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "SESSION_SECRET")
    if any(not env.get(key, "").strip() for key in required):
        raise ValueError("Google login requires GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and SESSION_SECRET.")
    return {
        "redirect_uri": redirect_uri(env, origin=origin),
        "cookie_secret": env["SESSION_SECRET"],
        "google": {
            "client_id": env["GOOGLE_CLIENT_ID"].strip(),
            "client_secret": env["GOOGLE_CLIENT_SECRET"].strip(),
            "server_metadata_url": GOOGLE_METADATA,
            "client_kwargs": {"scope": "openid email profile", "prompt": "select_account"},
        },
    }


def write_auth_configuration(settings, path):
    """Update private runtime settings only when they change; never cache keys."""
    path = Path(path)
    with _configuration_lock:
        existing = toml.loads(path.read_text()) if path.exists() else {}
        if existing.get("auth") == settings:
            if path.stat().st_mode & 0o777 != 0o600:
                path.chmod(0o600)
            return False
        existing["auth"] = settings
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".auth-", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(toml.dumps(existing))
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True


def configure_google_auth():
    origin = os.environ.get("PUBLIC_APP_URL", "").strip()
    if not origin:
        current = urlsplit(st.context.url)
        origin = f"{current.scheme}://{current.netloc}"
    settings = auth_settings(origin=origin)
    # Unlike a cached initializer, this notices credential changes on reruns.
    # Nothing is written into the repository or exposed to the browser.
    if write_auth_configuration(settings, Path(".streamlit/secrets.toml")):
        st.secrets._reset()
    return settings["redirect_uri"]

from pathlib import Path
from unittest.mock import patch

import pytest
import toml

from auth import render_google_login
from google_oauth import auth_settings, configure_google_auth, redirect_uri, write_auth_configuration


def sample_settings(client="test-client"):
    return auth_settings({
        "GOOGLE_CLIENT_ID": client, "GOOGLE_CLIENT_SECRET": "test-only-secret",
        "SESSION_SECRET": "test-only-cookie-key",
    }, origin="https://app.example.com")


def test_configuration_uses_only_google_oidc_and_minimum_scopes():
    settings = sample_settings(" test-client ")
    assert settings["google"]["client_id"] == "test-client"
    assert settings["google"]["server_metadata_url"] == "https://accounts.google.com/.well-known/openid-configuration"
    assert settings["google"]["client_kwargs"]["scope"] == "openid email profile"
    assert settings["redirect_uri"] == "https://app.example.com/oauth2callback"


@pytest.mark.parametrize("origin", [
    "http://app.example.com", "https://u:p@app.example.com",
    "https://app.example.com/path", "https://app.example.com?next=other",
    "https://app.example.com/#fragment", "",
])
def test_unsafe_or_missing_origins_rejected(origin):
    with pytest.raises(ValueError):
        redirect_uri({}, origin=origin)


def test_missing_secrets_fail_without_echoing_values():
    with pytest.raises(ValueError):
        auth_settings({}, origin="https://app.example.com")


def test_private_configuration_not_cached_and_unrelated_settings_preserved(tmp_path):
    path = tmp_path / "secrets.toml"
    path.write_text('[unrelated]\nvalue = "keep"\n')
    assert write_auth_configuration(sample_settings(), path)
    assert path.stat().st_mode & 0o777 == 0o600
    path.chmod(0o644)
    assert not write_auth_configuration(sample_settings(), path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert write_auth_configuration(sample_settings("rotated-test-client"), path)
    parsed = toml.loads(path.read_text())
    assert parsed["unrelated"]["value"] == "keep"
    assert parsed["auth"]["google"]["client_id"] == "rotated-test-client"
    assert not list(tmp_path.glob(".auth-*"))


@patch.dict("os.environ", {}, clear=True)
@patch("google_oauth.auth_settings")
@patch("google_oauth.write_auth_configuration", return_value=False)
@patch("google_oauth.st")
def test_current_origin_keeps_callback_on_same_host(st, write, settings):
    st.context.url = "https://app.example.com/soxl?view=chart"
    settings.return_value = sample_settings()
    assert configure_google_auth() == "https://app.example.com/oauth2callback"
    settings.assert_called_with(origin="https://app.example.com")
    st.secrets._reset.assert_not_called()


@patch.dict("os.environ", {"APP_ENV": "production"}, clear=True)
@patch("auth.configure_google_auth")
@patch("auth.st")
def test_google_button_invokes_real_native_provider(st, configure):
    st.user.is_logged_in = False
    st.button.return_value = True
    render_google_login()
    configure.assert_called_once()
    st.login.assert_called_once_with("google")


@patch.dict("os.environ", {"REPLIT_DEV_DOMAIN": "workspace.replit.dev"}, clear=True)
@patch("auth.configure_google_auth")
@patch("auth.st")
def test_workspace_never_needs_google_even_without_credentials(st, configure):
    render_google_login()
    configure.assert_not_called()
    st.login.assert_not_called()
    st.button.assert_not_called()
    st.caption.assert_called_with("Development: automatically signed in")


@patch.dict("os.environ", {"APP_ENV": "production"}, clear=True)
@patch("auth.configure_google_auth")
@patch("auth.st")
def test_logout_clears_session_and_native_signed_cookie(st, configure):
    st.user.is_logged_in = True
    st.button.return_value = True
    render_google_login()
    st.session_state.clear.assert_called_once()
    st.logout.assert_called_once()


@patch.dict("os.environ", {"APP_ENV": "production"}, clear=True)
@patch("auth.configure_google_auth", side_effect=RuntimeError("DO_NOT_DISPLAY"))
@patch("auth.st")
def test_configuration_errors_do_not_expose_secrets(st, configure):
    render_google_login()
    st.login.assert_not_called()
    assert "DO_NOT_DISPLAY" not in str(st.caption.call_args)

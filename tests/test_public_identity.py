"""Google login is removed; public access and local development remain."""
from unittest.mock import patch

import auth
from auth import get_current_user, is_development_preview, render_development_status


def test_workspace_identity_survives_old_logout_state():
    with patch.dict("os.environ", {"REPLIT_DEV_DOMAIN": "workspace.replit.dev"}, clear=True), \
         patch("auth.st") as st:
        st.session_state = {"preview_signed_out": True}
        for _ in range(2):
            assert get_current_user()["is_logged_in"] is True
            assert get_current_user()["auth_provider"] == "development"
            render_development_status()
            st.session_state.clear()
        st.caption.assert_called_with("Development: automatically signed in")
        st.login.assert_not_called()
        st.logout.assert_not_called()
        st.button.assert_not_called()


def test_production_and_unknown_environments_ignore_old_google_identity():
    environments = [
        {},
        {"APP_ENV": "development"},
        {"APP_ENV": "production", "REPLIT_DEV_DOMAIN": "workspace.replit.dev"},
        {"REPLIT_DEPLOYMENT": "1", "REPLIT_DEV_DOMAIN": "workspace.replit.dev"},
    ]
    for environ in environments:
        with patch.dict("os.environ", environ, clear=True), patch("auth.st") as st:
            st.user = {"is_logged_in": True, "provider": "google"}
            assert not is_development_preview()
            assert get_current_user() == {"is_logged_in": False}
            render_development_status()
            st.caption.assert_not_called()
            st.login.assert_not_called()
            st.logout.assert_not_called()
            st.button.assert_not_called()


def test_google_configuration_and_login_functions_are_removed():
    for name in ("render_google_login", "configure_google_auth", "auth_settings",
                 "GOOGLE_METADATA", "redirect_uri"):
        assert not hasattr(auth, name)

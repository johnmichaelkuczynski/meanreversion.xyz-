import unittest
from unittest.mock import patch

from auth import auth_settings, get_current_user, is_development_preview, redirect_uri, render_google_login


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict("os.environ", {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_auto_login_only_in_development_mode(self):
        self.assertTrue(is_development_preview({"REPLIT_DEV_DOMAIN": "workspace.replit.dev"}))
        self.assertTrue(is_development_preview({
            "APP_ENV": "development", "REPLIT_DEV_DOMAIN": "workspace.replit.dev"}))
        self.assertFalse(is_development_preview({"APP_ENV": "development"}))
        self.assertFalse(is_development_preview({}))
        self.assertFalse(is_development_preview({"APP_ENV": "production"}))
        for marker in ("1", "true", "yes"):
            self.assertFalse(is_development_preview({
                "REPLIT_DEPLOYMENT": marker, "APP_ENV": "development",
                "REPLIT_DEV_DOMAIN": "workspace.replit.dev", "REPLIT_CONTAINER": "repl",
            }))
        self.assertFalse(is_development_preview({
            "APP_ENV": "production", "REPLIT_DEV_DOMAIN": "workspace.replit.dev",
        }))

    @patch.dict("os.environ", {"REPLIT_DEV_DOMAIN": "workspace.replit.dev"})
    @patch("auth.configure_google_auth")
    @patch("auth.st")
    def test_preview_stays_signed_in_without_google(self, st, configure):
        st.session_state.get.return_value = False
        st.button.return_value = False
        for _ in range(2):
            self.assertTrue(get_current_user()["is_logged_in"])
            self.assertEqual(get_current_user()["auth_provider"], "development")
            render_google_login()
        configure.assert_not_called()
        st.login.assert_not_called()
        st.logout.assert_not_called()
        st.button.assert_not_called()
        st.caption.assert_called_with("Development: automatically signed in")

    @patch.dict("os.environ", {"REPLIT_DEV_DOMAIN": "workspace.replit.dev"})
    @patch("auth.st")
    def test_preview_cannot_be_stranded_signed_out_by_old_session_state(self, st):
        st.session_state = {"preview_signed_out": True}
        st.button.return_value = True
        render_google_login()
        self.assertTrue(get_current_user()["is_logged_in"])
        st.session_state.clear()
        render_google_login()
        self.assertTrue(get_current_user()["is_logged_in"])
        st.button.assert_not_called()
        st.login.assert_not_called()
        st.logout.assert_not_called()

    @patch.dict("os.environ", {
        "REPLIT_DEPLOYMENT": "1", "APP_ENV": "development",
        "REPLIT_DEV_DOMAIN": "workspace.replit.dev",
    })
    @patch("auth.st")
    def test_published_app_uses_only_verified_streamlit_identity_even_with_workspace_markers(self, st):
        st.user = {"is_logged_in": False}
        st.session_state = {"preview_signed_out": False}
        self.assertEqual(get_current_user(), {"is_logged_in": False})

    @patch.dict("os.environ", {"APP_ENV": "production", "PUBLIC_APP_URL": "https://app.example.com"})
    @patch("auth.configure_google_auth")
    @patch("auth.st")
    def test_published_app_never_auto_logs_in(self, st, configure):
        st.user.is_logged_in = False
        st.button.return_value = True
        render_google_login()
        configure.assert_called_once()
        st.login.assert_called_once_with("google")
        st.caption.assert_not_called()

    def test_production_uses_standard_public_origin(self):
        self.assertEqual(redirect_uri({
            "PUBLIC_APP_URL": "https://app.example.com/",
        }), "https://app.example.com/oauth2callback")

    def test_development_redirect_uses_public_origin(self):
        self.assertEqual(redirect_uri({
            "APP_ENV": "development",
            "PUBLIC_APP_URL": "https://app.example.com",
        }), "https://app.example.com/oauth2callback")

    def test_request_origin_can_supply_callback_without_a_hardcoded_hostname(self):
        self.assertEqual(redirect_uri({}, origin="https://stocks.example.com"),
                         "https://stocks.example.com/oauth2callback")

    @patch("auth._configure_google_auth_for_origin", return_value="configured")
    @patch("auth.st")
    def test_configuration_uses_current_site_origin_without_page_or_query(self, st, configure):
        from auth import configure_google_auth
        st.context.url = "https://stocks.example.com/soxl?view=chart"
        self.assertEqual(configure_google_auth(), "configured")
        configure.assert_called_once_with("https://stocks.example.com")

    @patch.dict("os.environ", {"PUBLIC_APP_URL": "https://canonical.example.com"})
    @patch("auth._configure_google_auth_for_origin", return_value="configured")
    @patch("auth.st")
    def test_explicit_public_origin_takes_priority(self, st, configure):
        from auth import configure_google_auth
        st.context.url = "https://other.example.com"
        configure_google_auth()
        configure.assert_called_once_with("https://canonical.example.com")

    def test_missing_configuration_fails_explicitly(self):
        with self.assertRaises(ValueError):
            auth_settings({})
        with self.assertRaises(ValueError):
            redirect_uri({"APP_ENV": "production"})

    def test_unsafe_origins_rejected(self):
        for origin in ("http://app.example.com", "https://u:p@app.example.com",
                       "https://app.example.com/other", "https://app.example.com?redirect=x"):
            with self.assertRaises(ValueError):
                redirect_uri({"PUBLIC_APP_URL": origin})

    def test_google_oidc_minimum_identity_scopes(self):
        settings = auth_settings({
            "PUBLIC_APP_URL": "https://app.example.com",
            "GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "test-only",
            "SESSION_SECRET": "test-cookie",
        })
        self.assertEqual(settings["google"]["client_kwargs"]["scope"], "openid email profile")
        self.assertEqual(settings["cookie_secret"], "test-cookie")

    @patch("auth.configure_google_auth")
    @patch("auth.st")
    def test_login_invokes_google_provider(self, st, configure):
        st.user.is_logged_in = False
        st.button.return_value = True
        render_google_login()
        st.login.assert_called_once_with("google")
        st.logout.assert_not_called()

    @patch("auth.configure_google_auth")
    @patch("auth.st")
    def test_logout_clears_session_and_uses_native_logout(self, st, configure):
        st.user.is_logged_in = True
        st.button.return_value = True
        render_google_login()
        st.session_state.clear.assert_called_once()
        st.logout.assert_called_once()

    @patch("auth.configure_google_auth", side_effect=ValueError("private configuration"))
    @patch("auth.st")
    def test_errors_never_echo_configuration(self, st, configure):
        render_google_login()
        st.login.assert_not_called()
        self.assertNotIn("private configuration", str(st.info.call_args))


if __name__ == "__main__":
    unittest.main()
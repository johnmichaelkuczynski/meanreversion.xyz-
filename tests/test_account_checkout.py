"""Checkout-return verification used by the shared, fail-closed access gate."""
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

import account_header as header

USER = {"is_logged_in": True, "sub": "return-test-user",
        "email": "return@example.test", "email_verified": True}
SCRIPT = """
import account_header
account_header._handle_checkout_return()
"""


@pytest.fixture
def dependencies(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.test")
    with patch.object(header, "get_current_user", return_value=USER), \
         patch.object(header, "is_development_preview", return_value=False), \
         patch.object(header, "verify_checkout") as verify, \
         patch.object(header, "track_event") as track:
        verify.return_value = False
        yield verify, track


def test_success_query_is_not_payment(dependencies):
    verify, track = dependencies
    app = AppTest.from_string(SCRIPT)
    app.query_params["checkout"] = "success"
    app.query_params["session_id"] = "cs_unverified"
    app.run()
    assert not app.exception and not app.success
    verify.assert_called_once_with(USER, "cs_unverified")
    track.assert_not_called()
    assert app.query_params["checkout"] == ["success"]


def test_verified_return_clears_query_and_forces_entitlement_refresh(dependencies):
    verify, track = dependencies
    verify.return_value = True
    app = AppTest.from_string(SCRIPT)
    app.session_state["_billing_access"] = {"paid": False}
    app.query_params["checkout"] = "success"
    app.query_params["session_id"] = "cs_verified"
    app.run()
    assert not app.exception and app.success
    assert "checkout" not in app.query_params
    assert "session_id" not in app.query_params
    assert "_billing_access" not in app.session_state
    track.assert_called_once_with("payment_confirmed", {"plan": "full_access"}, once_key="cs_verified")


def test_invalid_session_id_never_calls_stripe(dependencies):
    verify, track = dependencies
    app = AppTest.from_string(SCRIPT)
    app.query_params["checkout"] = "success"
    app.query_params["session_id"] = "not-a-session"
    app.run()
    assert not app.exception and app.info
    verify.assert_not_called()
    track.assert_not_called()


def test_cancellation_does_not_confirm_payment(dependencies):
    verify, track = dependencies
    app = AppTest.from_string(SCRIPT)
    app.query_params["checkout"] = "cancelled"
    app.run()
    assert not app.exception and not app.success
    assert "checkout" not in app.query_params
    verify.assert_not_called()
    track.assert_called_once_with("checkout_cancelled", {"location": "return"})


def test_admin_return_never_verifies_or_emits_payment_event(dependencies):
    verify, track = dependencies
    with patch.object(header, "get_current_user", return_value=dict(USER, email="ADMIN@example.test")):
        app = AppTest.from_string(SCRIPT)
        app.query_params["checkout"] = "success"
        app.query_params["session_id"] = "cs_unused"
        app.run()
    assert not app.exception
    verify.assert_not_called()
    track.assert_not_called()

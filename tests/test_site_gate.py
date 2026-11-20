from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

import site_gate as gate

USER = {"is_logged_in": True, "email_verified": True, "sub": "test-subject",
        "email": "member@example.test", "provider": "google"}
SCRIPT = """
import streamlit as st
from site_gate import require_site_access
if require_site_access():
    st.write("PROTECTED_APP_EXECUTED")
"""


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.test,SECOND@example.test")


def protected(app):
    return any(x.value == "PROTECTED_APP_EXECUTED" for x in app.markdown)


def test_anonymous_gets_readme_and_no_stripe_calls(environment):
    with patch.object(gate, "get_current_user", return_value={"is_logged_in": False}), \
         patch.object(gate, "paid_access_for_current_user") as paid, \
         patch.object(gate, "get_plan") as plan, \
         patch.object(gate, "create_checkout") as checkout:
        app = AppTest.from_string(SCRIPT).run()
    assert not app.exception
    assert not protected(app)
    assert any("mean reversion" in x.value.lower() for x in app.markdown)
    paid.assert_not_called()
    plan.assert_not_called()
    checkout.assert_not_called()


@pytest.mark.parametrize("email", ["admin@example.test", " ADMIN@EXAMPLE.TEST ", "second@example.test"])
def test_admin_enters_without_paywall_or_any_billing_call(environment, email):
    with patch.object(gate, "get_current_user", return_value=dict(USER, email=email)), \
         patch.object(gate, "_handle_checkout_return") as returned, \
         patch.object(gate, "paid_access_for_current_user") as paid, \
         patch.object(gate, "get_plan") as plan, \
         patch.object(gate, "create_checkout") as checkout, \
         patch.object(gate, "render_welcome_readme") as welcome:
        app = AppTest.from_string(SCRIPT).run()
    assert not app.exception and protected(app)
    assert app.session_state["_paid_access_verified"] is True
    for call in (returned, paid, plan, checkout, welcome):
        call.assert_not_called()


def test_paid_google_user_enters(environment):
    with patch.object(gate, "get_current_user", return_value=USER), \
         patch.object(gate, "_handle_checkout_return"), \
         patch.object(gate, "paid_access_for_current_user", return_value=True), \
         patch.object(gate, "create_checkout") as checkout:
        app = AppTest.from_string(SCRIPT).run()
    assert not app.exception and protected(app)
    assert app.session_state["_paid_access_subject"] == USER["sub"]
    checkout.assert_not_called()


def test_unpaid_user_gets_real_checkout_link_contract_but_not_app(environment):
    plan = {"livemode": True, "currency": "usd", "amount": 999, "price_id": "price_test"}
    with patch.object(gate, "get_current_user", return_value=USER), \
         patch.object(gate, "_handle_checkout_return"), \
         patch.object(gate, "paid_access_for_current_user", return_value=False), \
         patch.object(gate, "get_plan", return_value=plan), \
         patch.object(gate, "create_checkout", return_value={"url": "https://checkout.stripe.com/c/pay/test-only"}) as checkout:
        app = AppTest.from_string(SCRIPT).run()
        app.run()
    assert not app.exception and not protected(app)
    assert app.session_state["_paid_access_verified"] is False
    assert any("Pay USD 9.99" in x.label for x in app.get("link_button"))
    checkout.assert_called_once()


def test_provider_failure_does_not_unlock_or_start_checkout(environment):
    with patch.object(gate, "get_current_user", return_value=USER), \
         patch.object(gate, "_handle_checkout_return"), \
         patch.object(gate, "paid_access_for_current_user", side_effect=RuntimeError("private")), \
         patch.object(gate, "create_checkout") as checkout:
        app = AppTest.from_string(SCRIPT).run()
    assert not app.exception and not protected(app)
    assert app.warning
    assert not any("private" in x.value for x in app.warning)
    checkout.assert_not_called()


def test_missing_admin_configuration_disables_checkout(environment, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "")
    with patch.object(gate, "get_current_user", return_value=USER), \
         patch.object(gate, "paid_access_for_current_user") as paid, \
         patch.object(gate, "create_checkout") as checkout:
        app = AppTest.from_string(SCRIPT).run()
    assert not app.exception and not protected(app)
    assert app.error
    paid.assert_not_called()
    checkout.assert_not_called()


def test_gate_precedes_workspace_import_and_every_page_execution():
    source = Path("main.py").read_text()
    assert source.index("if not require_site_access():") < source.index("from mean_reversion_workspace import")
    assert source.index("if not require_site_access():") < source.index("page.run()")


def test_subject_bound_payment_cannot_leak_to_another_account(environment):
    import access
    state = {"_paid_access_verified": True, "_paid_access_subject": "old-user",
             "_paid_access_source": "payment"}
    with patch.object(access, "st") as st:
        st.session_state = state
        assert not access.has_paid_access(USER, preview=False)
        state["_paid_access_subject"] = USER["sub"]
        assert access.has_paid_access(USER, preview=False)
        state["_paid_access_source"] = "admin"
        assert not access.has_paid_access(USER, preview=False)

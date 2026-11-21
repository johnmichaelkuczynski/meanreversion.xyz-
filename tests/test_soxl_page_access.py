"""Exercise the actual SOXL entry guard without running market-data work."""
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

import ticker_access as policy

MEMBER = {
    "is_logged_in": True, "email_verified": True, "provider": "google",
    "sub": "fixture-member", "email": "member@example.test",
}
MESSAGE = "The SOXL page requires full access — $1,500"


@pytest.fixture(autouse=True)
def production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.test")


@pytest.mark.parametrize("user", [
    {"is_logged_in": False},
    MEMBER,
    dict(MEMBER, email_verified=False),
])
def test_denied_soxl_page_shows_only_one_panel_before_any_page_content(user):
    with patch.object(policy, "get_current_user", return_value=user), \
         patch.object(policy, "paid_access_for_current_user", return_value=False), \
         patch.object(policy, "create_checkout") as checkout:
        app = AppTest.from_file("app.py", default_timeout=10).run()
    assert not app.exception
    assert [item.value for item in app.markdown] == [MESSAGE]
    assert [button.label for button in app.button] == ["Get full access"]
    assert not app.get("component_instance")
    assert not app.get("plotly_chart")
    assert not app.text_input
    checkout.assert_not_called()


def test_page_two_does_not_inherit_free_SOXL_analysis():
    with patch.object(policy, "get_current_user", return_value={"is_logged_in": False}), \
         patch.object(policy, "paid_access_for_current_user") as paid:
        assert policy.can_analyze_ticker("SOXL")
        assert not policy.has_full_access()
    paid.assert_not_called()


@pytest.mark.parametrize("kind", ["paid", "owner", "development"])
def test_entitled_users_reach_the_unchanged_soxl_page_body(kind):
    # Execute the real source up to its first page-content dependency.
    prefix = Path("app.py").read_text().split("import streamlit.components.v1", 1)[0]
    script = prefix + "\nst.write('SOXL body reached')\n"
    user = dict(MEMBER, email=" OWNER@EXAMPLE.TEST ") if kind == "owner" else MEMBER
    with patch.object(policy, "get_current_user", return_value=user), \
         patch.object(policy, "is_development_preview", return_value=kind == "development"), \
         patch.object(policy, "paid_access_for_current_user", return_value=kind == "paid") as paid, \
         patch.object(policy, "create_checkout") as checkout:
        app = AppTest.from_string(script).run()
    assert not app.exception
    assert [item.value for item in app.markdown] == ["SOXL body reached"]
    assert not app.button
    checkout.assert_not_called()
    if kind != "paid":
        paid.assert_not_called()


def test_payment_provider_failure_cannot_expose_the_soxl_page():
    with patch.object(policy, "get_current_user", return_value=MEMBER), \
         patch.object(policy, "paid_access_for_current_user", side_effect=RuntimeError("offline")):
        app = AppTest.from_file("app.py").run()
    assert not app.exception
    assert [item.value for item in app.markdown] == [MESSAGE]


def test_soxl_button_uses_the_existing_single_click_purchase_continuation():
    with patch.object(policy, "get_current_user", return_value={"is_logged_in": False}), \
         patch.object(policy, "navigate") as navigate:
        app = AppTest.from_file("app.py").run()
        app.button(key="mr_get_full_access").click().run()
    assert not app.exception
    navigate.assert_called_once_with("/api/full-access/start?ticker=SOXL")

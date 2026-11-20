from unittest.mock import patch

import pytest

import access
import account_header
import auth
import billing

ADMIN = {
    "is_logged_in": True, "email_verified": True,
    "sub": "verified-test-subject", "email": "admin@example.test",
}


@pytest.fixture(autouse=True)
def admin_configuration(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", " first@example.test, ADMIN@example.test , ")


@pytest.mark.parametrize("change", [
    {"is_logged_in": False}, {"is_logged_in": "true"},
    {"email_verified": False}, {"email_verified": "true"}, {"sub": ""},
    {"email": "admin+alias@example.test"}, {"email": "admin@example.test.evil"},
    {"auth_provider": "development"}, {"provider": "other"},
])
def test_admin_requires_exact_verified_authenticated_email(change):
    assert not auth.is_admin(dict(ADMIN, **change))
    assert not access.has_unlimited_credits(dict(ADMIN, **change))


def test_case_insensitive_allowlist_and_environment_changes(monkeypatch):
    assert auth.is_admin(dict(ADMIN, email=" ADMIN@EXAMPLE.TEST "))
    assert access.access_tier(ADMIN, paid_verified=False, preview=False) == access.OWNER
    monkeypatch.setenv("ADMIN_EMAILS", "")
    assert not auth.is_admin(ADMIN)


def test_admin_never_calls_stripe_or_purchase_storage():
    with patch.object(billing, "stripe_client", side_effect=AssertionError("Stripe called")), \
         patch.object(billing, "get_plan", side_effect=AssertionError("Price checked")), \
         patch.object(billing, "user_identity", side_effect=AssertionError("Billing identity checked")):
        assert billing.get_paid_access(ADMIN)
        assert billing.verify_checkout(ADMIN, "unused")
        with pytest.raises(billing.BillingError, match="No payment"):
            billing.create_checkout(ADMIN)


def test_admin_header_and_checkout_return_skip_billing():
    with patch.object(account_header, "get_current_user", return_value=ADMIN), \
         patch.object(account_header, "get_paid_access", side_effect=AssertionError("Billing checked")), \
         patch.object(account_header, "verify_checkout", side_effect=AssertionError("Checkout checked")):
        assert account_header.paid_access_for_current_user(force=True)
        account_header._handle_checkout_return()


def test_admin_does_not_grant_access_to_next_user():
    other = dict(ADMIN, email="other@example.test", sub="other-subject")
    assert not auth.is_admin(other)
    assert not access.has_paid_access(other, paid_verified=False, preview=False)
    assert access.has_paid_access(other, paid_verified=True, preview=False)

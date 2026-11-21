"""Legacy named features stay public; page one separately checks ticker access."""
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

import access
import account_header


@pytest.mark.parametrize("user", [
    None,
    {"is_logged_in": False},
    {"is_logged_in": True, "sub": "fixture", "email": "member@example.test",
     "email_verified": True},
])
@pytest.mark.parametrize("paid", [False, True])
def test_every_feature_is_open_without_identity_or_payment_checks(user, paid):
    purchase = Mock(side_effect=AssertionError("A purchase was requested"))
    with patch.object(access, "has_paid_access", side_effect=AssertionError("Payment checked")), \
         patch.object(access, "get_current_user", side_effect=AssertionError("Login checked")):
        for feature in (*access.PAID_FEATURES, "Chart & Probabilities", "Snapshot",
                        "Options Projection", "Detailed scores", "Any future feature"):
            assert access.can_access(feature, user, paid_verified=paid, preview=False)
            assert access.require_paid_access(
                feature, user, purchase, paid_verified=paid, preview=False,
            )
        assert access.can_use_market_chat(user, paid_verified=paid, preview=False)
        assert access.has_unlimited_credits(user)
    purchase.assert_not_called()


def test_legacy_gate_never_renders_a_wall_or_checkout():
    purchase = Mock()
    with patch.object(access, "st") as ui:
        access.render_paid_gate("Backtest", purchase)
    assert not ui.mock_calls
    purchase.assert_not_called()


def test_pages_have_no_partial_redaction_or_legacy_payment_prompts():
    main = Path("main.py").read_text()
    assert "render_google_login()" in main
    assert "st.stop()" not in main
    assert "site_gate" not in main
    assert "_handle_checkout_return()" in main
    for filename in ("app.py", "mean_reversion_workspace.py", "mean_reversion_readout.py"):
        text = Path(filename).read_text()
        for forbidden in ("REDACTED", "redacted", "blur(", "require_paid_access(",
                          "has_paid_access(", "can_use_market_chat(",
                          "render_unlock_prompt", "Payment could not be verified",
                          "Check payment status"):
            assert forbidden not in text, (filename, forbidden)
    assert not Path("site_gate.py").exists()
    assert not Path("public_results.py").exists()


def test_public_header_never_calls_login_billing_or_checkout():
    with patch.object(account_header, "st") as st, \
         patch.object(account_header, "flush_analytics"), \
         patch.object(account_header, "paid_access_for_current_user") as billing, \
         patch.object(st, "login") as login, \
         patch.object(account_header, "_handle_checkout_return") as checkout_return, \
         patch.object(account_header, "show_purchase_options") as purchase, \
         patch.object(account_header, "render_visitor_counter"):
        st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        st.button.return_value = False
        st.query_params = {"checkout": "buy"}
        account_header.render_account_header()
    for call in (billing, login, checkout_return, purchase):
        call.assert_not_called()

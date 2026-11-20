from unittest.mock import Mock, patch
import access
import account_header


def test_all_features_require_identity_and_verified_payment():
    guest = {"is_logged_in": False}
    for feature in (*access.PAID_FEATURES, "Talk with SOXL Pro"):
        assert not access.can_access(feature, guest, paid_verified=False, preview=False)
    dialog = Mock()
    with patch.object(access, "render_paid_gate") as gate:
        for feature in access.PAID_FEATURES:
            assert not access.require_paid_access(
                feature, guest, dialog, paid_verified=False, preview=False)
        assert gate.call_count == len(access.PAID_FEATURES)


def test_public_header_never_calls_login_billing_or_checkout():
    from unittest.mock import MagicMock
    with patch.object(account_header, "st") as st, \
         patch.object(account_header, "flush_analytics"), \
         patch.object(account_header, "paid_access_for_current_user") as billing, \
         patch.object(st, "login") as login, \
         patch.object(account_header, "_handle_checkout_return") as checkout_return, \
         patch.object(account_header, "show_purchase_options") as purchase, \
         patch.object(account_header, "render_visitor_counter") as visitor_counter:
        st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        st.button.return_value = False
        st.query_params = {"checkout": "buy"}
        account_header.render_account_header()
        for mock in (billing, login, checkout_return, purchase):
            mock.assert_not_called()
        visitor_counter.assert_called_once()

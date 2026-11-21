from unittest.mock import Mock, patch
import pytest
from streamlit.testing.v1 import AppTest

import ticker_access as policy
from test_unredacted_workspace import SCRIPT

MEMBER = {"is_logged_in": True, "email_verified": True, "sub": "member-sub",
          "email": "member@example.test", "provider": "google"}


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.test")


@pytest.mark.parametrize("symbol", ["SOXL", "QQQ", "AAPL"])
def test_free_tickers_never_check_identity_or_payment(production, symbol):
    with patch.object(policy, "get_current_user", side_effect=AssertionError("Identity queried")), \
         patch.object(policy, "paid_access_for_current_user") as paid:
        assert policy.can_analyze_ticker(symbol)
    paid.assert_not_called()


def test_anonymous_and_unpaid_cannot_analyze_other_tickers(production):
    with patch.object(policy, "get_current_user", return_value={"is_logged_in": False}), \
         patch.object(policy, "paid_access_for_current_user") as paid:
        assert not policy.can_analyze_ticker("MSFT")
        paid.assert_not_called()
    with patch.object(policy, "get_current_user", return_value=MEMBER), \
         patch.object(policy, "paid_access_for_current_user", return_value=False):
        assert not policy.can_analyze_ticker("MSFT")


def test_paid_owner_and_development_have_unrestricted_tickers(production):
    with patch.object(policy, "get_current_user", return_value=MEMBER), \
         patch.object(policy, "paid_access_for_current_user", return_value=True):
        assert policy.can_analyze_ticker("MSFT")
    with patch.object(policy, "get_current_user", return_value=dict(MEMBER, email=" OWNER@EXAMPLE.TEST ")), \
         patch.object(policy, "paid_access_for_current_user", side_effect=AssertionError("Owner billed")):
        assert policy.can_analyze_ticker("MSFT")
    with patch.object(policy, "is_development_preview", return_value=True), \
         patch.object(policy, "get_current_user", side_effect=AssertionError("Preview gated")):
        assert policy.can_analyze_ticker("MSFT")


def test_denied_primary_has_one_panel_and_never_downloads_or_renders_results(production):
    with patch.object(policy, "get_current_user", return_value={"is_logged_in": False}):
        app = AppTest.from_string(SCRIPT, default_timeout=20).run()
        app.text_input(key="mr_workspace_top_primary_input").set_value("MSFT").run()
        assert not app.exception
        assert "MSFT" not in app.session_state["fixture_downloads"]
        assert any(x.value == "Analyzing MSFT requires full access — $1,500" for x in app.markdown)
        assert len([b for b in app.button if b.label == "Get full access"]) == 1
        assert not app.get("component_instance")
        assert not any("mr-priority-readout" in x.value for x in app.markdown)
        app.text_input(key="mr_workspace_top_primary_input").set_value("QQQ").run()
        assert not app.exception
        assert app.session_state["mr_workspace_primary"]["symbol"] == "QQQ"
        assert not any(b.label == "Get full access" for b in app.button)


def test_denied_comparison_never_downloads_or_leaks_the_previous_chart(production):
    with patch.object(policy, "get_current_user", return_value={"is_logged_in": False}):
        app = AppTest.from_string(SCRIPT, default_timeout=20).run()
        app.text_input(key="mr_workspace_compare_input").set_value("MSFT")
        next(b for b in app.button if b.label == "Add comparison").click().run()
        assert not app.exception
        assert "MSFT" not in app.session_state["fixture_downloads"]
        assert not app.get("component_instance")
        assert any("Analyzing MSFT requires full access" in x.value for x in app.markdown)
        app.text_input(key="mr_workspace_top_primary_input").set_value("SOXL").run()
        assert not app.exception
        assert app.get("component_instance")


def test_retained_paid_results_disappear_before_analysis_after_signout(production):
    user = Mock(return_value=MEMBER)
    with patch.object(policy, "get_current_user", user), \
         patch.object(policy, "paid_access_for_current_user", return_value=True):
        app = AppTest.from_string(SCRIPT, default_timeout=20).run()
        app.text_input(key="mr_workspace_top_primary_input").set_value("MSFT").run()
        assert not app.exception
        assert app.session_state["mr_workspace_primary"]["symbol"] == "MSFT"
        user.return_value = {"is_logged_in": False}
        app.run()
        assert not app.exception
        assert not app.get("component_instance")
        assert any("Analyzing MSFT requires full access" in x.value for x in app.markdown)


@pytest.mark.parametrize("kind", ["anonymous", "unpaid", "paid", "owner"])
def test_purchase_continuation_uses_google_then_stripe_without_owner_charges(production, kind):
    user = ({"is_logged_in": False} if kind == "anonymous" else
            dict(MEMBER, email="owner@example.test") if kind == "owner" else MEMBER)
    with patch.object(policy, "st") as ui, \
         patch.object(policy, "read_intent", return_value="MSFT"), \
         patch.object(policy, "get_current_user", return_value=user), \
         patch.object(policy, "configure_google_auth") as google, \
         patch.object(policy, "paid_access_for_current_user", return_value=kind == "paid") as paid, \
         patch.object(policy, "get_plan", return_value={"amount":150000,"currency":"usd"}) as plan, \
         patch.object(policy, "create_checkout", return_value={"url":"https://checkout.stripe.com/c/pay/fixture"}) as checkout, \
         patch.object(policy, "departure_url", side_effect=lambda url: url), \
         patch.object(policy, "navigate") as navigate:
        assert policy.resume_ticker_purchase()
    if kind == "anonymous":
        google.assert_called_once()
        ui.login.assert_called_once_with("google")
        checkout.assert_not_called()
    elif kind == "unpaid":
        checkout.assert_called_once_with(MEMBER)
        navigate.assert_called_once_with("https://checkout.stripe.com/c/pay/fixture")
    else:
        checkout.assert_not_called()
        plan.assert_not_called()
        navigate.assert_called_once_with("/")
    if kind == "owner":
        paid.assert_not_called()


def test_unlock_button_navigates_immediately_without_another_submit(production):
    script = "from ticker_access import render_ticker_unlock\nrender_ticker_unlock('MSFT')"
    app = AppTest.from_string(script).run()
    app.button(key="mr_get_full_access").click().run()
    assert not app.exception


def test_checkout_failure_clears_intent_instead_of_trapping_free_visitors(production):
    with patch.object(policy, "st"), \
         patch.object(policy, "read_intent", return_value="MSFT"), \
         patch.object(policy, "get_current_user", return_value=MEMBER), \
         patch.object(policy, "paid_access_for_current_user", return_value=False), \
         patch.object(policy, "get_plan", side_effect=RuntimeError("fixture failure")), \
         patch.object(policy, "departure_url", side_effect=lambda url: url), \
         patch.object(policy, "navigate") as navigate, \
         patch.object(policy, "create_checkout") as checkout:
        assert policy.resume_ticker_purchase()
    assert "requested_ticker=MSFT" in navigate.call_args.args[0]
    assert "checkout_error=1" in navigate.call_args.args[0]
    checkout.assert_not_called()


def test_failed_checkout_returns_to_one_panel_and_free_tickers_remain_usable(production):
    with patch.object(policy, "get_current_user", return_value={"is_logged_in": False}):
        app = AppTest.from_string(SCRIPT, default_timeout=20)
        app.query_params["requested_ticker"] = "MSFT"
        app.query_params["checkout_error"] = "1"
        app.run()
        assert not app.exception
        downloads = (app.session_state["fixture_downloads"]
                     if "fixture_downloads" in app.session_state else [])
        assert "MSFT" not in downloads
        assert any("Analyzing MSFT requires full access" in item.value for item in app.markdown)
        assert "requested_ticker" not in app.query_params
        app.text_input(key="mr_workspace_top_primary_input").set_value("AAPL").run()
        assert not app.exception
        assert app.session_state["mr_workspace_primary"]["symbol"] == "AAPL"
        assert not any(button.label == "Get full access" for button in app.button)

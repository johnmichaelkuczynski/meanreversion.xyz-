"""Synthetic payment verification; optional isolated PostgreSQL integration."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
from unittest.mock import Mock, patch
import uuid

import pytest
from streamlit.testing.v1 import AppTest

import account_header
import billing
import db
import purchase_store
import stripe_webhook as webhook
import ticker_access

PRICE = "price_email_fulfillment_test"
USER = {"is_logged_in": True, "email_verified": True, "auth_provider": "google",
        "sub": "email-fulfillment-test", "email": "BUYER@EXAMPLE.TEST"}
IDENTITY = hashlib.sha256(b"google:email-fulfillment-test").hexdigest()


@pytest.fixture(autouse=True)
def production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.test")
    monkeypatch.setenv("STRIPE_PRICE_ID", PRICE)


def payment():
    return {
        "id": "cs_email_fulfillment_test", "livemode": True,
        "mode": "payment", "status": "complete", "payment_status": "paid",
        "client_reference_id": IDENTITY,
        "metadata": {"app": "soxlpro", "user_identity": IDENTITY,
                     "price_id": PRICE, "attempt_id": "receipt-test"},
        "currency": "usd", "amount_subtotal": 150000, "amount_total": 150000,
        "total_details": {"amount_tax": 0, "amount_discount": 0, "amount_shipping": 0},
        "line_items": {"data": [{"price": {"id": PRICE}, "quantity": 1}]},
        # The payer's billing email must never replace the verified Google email.
        "customer_details": {"email": "different-billing@example.test"},
        "payment_intent": {
            "status": "succeeded", "livemode": True, "amount": 150000, "currency": "usd",
            "latest_charge": {"paid": True, "livemode": True, "amount": 150000,
                              "currency": "usd", "refunded": False,
                              "disputed": False, "amount_refunded": 0},
        },
    }


def event(session):
    return {"id": "evt_" + uuid.uuid4().hex, "type": "checkout.session.completed",
            "created": 100, "livemode": True, "data": {"object": deepcopy(session)}}


def provider(session):
    client = Mock()
    client.v1.checkout.sessions.retrieve.return_value = session
    return client


@pytest.mark.parametrize("invalid", [
    "price", "identity", "unpaid", "test", "amount", "charge", "intent", "missing-receipt",
])
def test_invalid_checkout_never_records_verified_payment(invalid):
    session = payment()
    delivery = event(session)
    if invalid == "price":
        session["line_items"]["data"][0]["price"]["id"] = "price_wrong"
    elif invalid == "identity":
        session["client_reference_id"] = "wrong"
    elif invalid == "unpaid":
        session["payment_status"] = "unpaid"
    elif invalid == "test":
        delivery["livemode"] = False
    elif invalid == "amount":
        session["amount_total"] = 1
    elif invalid == "charge":
        session["payment_intent"]["latest_charge"]["refunded"] = True
    elif invalid == "intent":
        session["payment_intent"]["status"] = "processing"
    cur = Mock()
    cur.fetchone.return_value = None if invalid == "missing-receipt" else {
        "id": 1, "price_id": PRICE, "expected_amount": 150000,
        "expected_currency": "usd", "status": "open",
    }
    if invalid in {"test", "missing-receipt"}:
        webhook.process_event(cur, delivery, provider(session))
    else:
        with pytest.raises(ValueError):
            webhook.process_event(cur, delivery, provider(session))
    assert not any("SET status='paid'" in call.args[0] for call in cur.execute.call_args_list)


def test_database_paid_email_bypasses_stripe_and_subscription_requests():
    with patch.object(purchase_store, "email_has_paid_access", return_value=True) as paid, \
         patch.object(billing, "stripe_client", side_effect=AssertionError("Stripe called")), \
         patch.object(webhook, "subscription_access", side_effect=AssertionError("Wrong path")):
        assert billing.get_paid_access(USER)
    paid.assert_called_once_with(USER["email"], PRICE, fresh_only=True)


def test_stale_paid_receipt_survives_provider_outage_but_not_confirmed_revocation():
    state = {"paid": True}
    record = {"user_identity_hash": IDENTITY, "price_id": PRICE, "status": "paid",
              "stripe_session_id": "cs_paid"}
    def recorded(email, price, *, fresh_only=False):
        return not fresh_only and state["paid"]
    with patch.object(purchase_store, "email_has_paid_access", side_effect=recorded), \
         patch.object(webhook, "subscription_access", return_value=False), \
         patch.object(billing, "get_plan", side_effect=billing.BillingError("unavailable")):
        assert billing.get_paid_access(USER)
    def revoke(*args):
        state["paid"] = False
        return False
    with patch.object(purchase_store, "email_has_paid_access", side_effect=recorded), \
         patch.object(webhook, "subscription_access", return_value=False), \
         patch.object(billing, "get_plan", return_value={"price_id": PRICE, "livemode": True}), \
         patch.object(purchase_store, "list_checkouts", return_value=[record]), \
         patch.object(billing, "verify_checkout", side_effect=revoke):
        assert not billing.get_paid_access(USER)


def test_unpaid_cache_cannot_hide_a_newly_committed_webhook():
    with patch.object(account_header, "get_current_user", return_value=USER), \
         patch.object(account_header, "get_paid_access", side_effect=[False, True]) as paid:
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from account_header import paid_access_for_current_user\n"
            "st.write(paid_access_for_current_user())"
        ).run()
        assert [item.value for item in app.markdown] == ["`False`"]
        app.run()
        assert not app.exception
        assert [item.value for item in app.markdown] == ["`True`"]
    assert paid.call_count == 2


def test_known_paid_checkout_return_is_silent_and_never_rechecks_stripe():
    with patch.object(account_header, "get_current_user", return_value=USER), \
         patch.object(account_header, "paid_access_for_current_user", return_value=True), \
         patch.object(account_header, "verify_checkout") as verify:
        app = AppTest.from_string(
            "from account_header import _handle_checkout_return\n_handle_checkout_return()"
        )
        app.query_params["checkout"] = "success"
        app.query_params["session_id"] = "cs_paid"
        app.run()
    assert not app.exception and not app.success and not app.info and not app.error
    assert "checkout" not in app.query_params
    verify.assert_not_called()


@pytest.fixture
def isolated_database(monkeypatch):
    if os.environ.get("PAID_EMAIL_DB_TEST") != "1":
        pytest.skip("explicit isolated PostgreSQL integration only")
    from psycopg2 import sql
    connect = db.get_conn
    admin = connect()
    schema = "paid_email_test_" + uuid.uuid4().hex
    with admin, admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    class IsolatedConnection:
        def __init__(self):
            self.conn = connect()

        def __enter__(self):
            self.conn.__enter__()
            return self

        def __exit__(self, *args):
            return self.conn.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def cursor(self, *args, **kwargs):
            cur = self.conn.cursor(*args, **kwargs)
            # Neon transaction pooling can switch backends at each commit.
            # Apply isolation inside every transaction, never session-wide.
            cur.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
            return cur

        def close(self):
            self.conn.rollback()
            with self.conn, self.conn.cursor() as cur:
                cur.execute("RESET search_path")
            self.conn.close()

    def isolated_connection():
        return IsolatedConnection()

    monkeypatch.setattr(db, "get_conn", isolated_connection)
    monkeypatch.setattr(purchase_store, "_initialized", False)
    try:
        purchase_store.initialize_store()
        conn = isolated_connection()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(webhook.SCHEMA)
        finally:
            conn.close()
        yield
    finally:
        # Only this test's random schema is removed; app tables are never touched.
        with admin, admin.cursor() as cur:
            cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        admin.close()


def test_webhook_commit_unlocks_both_pages_from_database(isolated_database, monkeypatch):
    session = payment()
    receipt = purchase_store.reserve_checkout(IDENTITY, PRICE, 150000, "usd", USER["email"])
    session["metadata"]["attempt_id"] = receipt["attempt_id"]
    # Deliberately omit attach_session: fulfillment must recover this crash window.
    client = provider(session)
    delivery = event(session)
    webhook.persist_event(delivery)
    webhook.persist_event(delivery)
    assert webhook.process_one(client)
    assert not webhook.process_one(client)
    stored = purchase_store.find_checkout(IDENTITY, session["id"])
    assert stored["status"] == "paid"
    assert stored["google_email"] == "buyer@example.test"
    assert stored["verified_paid_at"] is not None
    assert purchase_store.email_has_paid_access(" BUYER@example.test ", PRICE)
    assert not purchase_store.email_has_paid_access("different-billing@example.test", PRICE)
    assert not purchase_store.email_has_paid_access(USER["email"], "price_wrong")
    monkeypatch.setattr(billing, "stripe_client", Mock(side_effect=AssertionError("Stripe called")))
    monkeypatch.setattr(billing, "get_plan", Mock(side_effect=AssertionError("Stripe price requested")))
    assert billing.get_paid_access(USER)
    with patch.object(ticker_access, "get_current_user", return_value=USER), \
         patch.object(account_header, "get_current_user", return_value=USER):
        from test_unredacted_workspace import SCRIPT
        app = AppTest.from_string(SCRIPT, default_timeout=20).run()
        app.text_input(key="mr_workspace_top_primary_input").set_value("MSFT").run()
        assert not app.exception
        assert app.get("component_instance")
        assert not any(button.label == "Get full access" for button in app.button)
        prefix = Path("app.py").read_text().split("import streamlit.components.v1", 1)[0]
        soxl = AppTest.from_string(prefix + "\nst.write('SOXL body reached')\n").run()
        assert not soxl.exception
        assert [item.value for item in soxl.markdown] == ["SOXL body reached"]
        assert not soxl.button
    conn = db.get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE purchase_checkouts SET verified_paid_at=now()-interval '2 minutes'"
            )
    finally:
        conn.close()
    assert not purchase_store.email_has_paid_access(USER["email"], PRICE, fresh_only=True)
    monkeypatch.setattr(
        billing, "get_plan", Mock(side_effect=billing.BillingError("provider unavailable")),
    )
    assert billing.get_paid_access(USER)
    # A different-price event must roll back and remain retryable, not grant access.
    other_identity = hashlib.sha256(b"other-google-user").hexdigest()
    other = purchase_store.reserve_checkout(
        other_identity, PRICE, 150000, "usd", "other@example.test",
    )
    bad = deepcopy(session)
    bad["id"] += "_wrong_price"
    bad["metadata"].update(user_identity=other_identity, attempt_id=other["attempt_id"])
    bad["client_reference_id"] = other_identity
    bad["line_items"]["data"][0]["price"]["id"] = "price_wrong"
    webhook.persist_event(event(bad))
    assert not webhook.process_one(provider(bad))
    assert not purchase_store.email_has_paid_access("other@example.test", PRICE)

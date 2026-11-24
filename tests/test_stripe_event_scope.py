"""Ownership filtering uses synthetic events; no requests to Stripe."""
from copy import deepcopy
import hashlib
import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest

import stripe_event_scope as scope
import stripe_webhook as wh
from test_stripe_webhook import ReceiverTests
from test_paid_email_fulfillment import isolated_database

PRICE = "price_scope_test"
IDENTITY = hashlib.sha256(b"scope-unit-user").hexdigest()


@pytest.fixture(autouse=True)
def configured_price(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_ID", PRICE)


def delivery(kind="checkout.session.completed"):
    if kind == "checkout.session.completed":
        obj = {"id": "cs_scope", "customer": "cus_new",
               "metadata": {"app": "soxlpro", "user_identity": IDENTITY,
                            "price_id": PRICE, "attempt_id": "attempt_scope"}}
    elif kind.startswith("customer.subscription."):
        obj = {"id": "sub_scope", "customer": "cus_scope", "status": "active"}
    else:
        obj = {"id": "in_scope", "customer": "cus_scope", "subscription": "sub_scope"}
    return {"id": "evt_scope", "created": 100, "livemode": True,
            "type": kind, "data": {"object": obj}}


@pytest.mark.parametrize("kind", [
    "charge.succeeded", "customer.created", "invoice.paid", "payment_intent.succeeded",
])
def test_unused_types_need_no_database(kind):
    with patch.object(wh.db, "get_conn", side_effect=AssertionError("DB called")):
        assert wh.persist_event(delivery(kind)) is False


@pytest.mark.parametrize("change", [
    "foreign-app", "foreign-price", "unknown-user", "no-app", "test-mode", "no-object",
])
def test_obviously_foreign_checkouts_are_ignored_before_database(change):
    event = delivery()
    meta = event["data"]["object"]["metadata"]
    if change == "foreign-app":
        meta["app"] = "another-app"
    elif change == "foreign-price":
        meta["price_id"] = "price_other"
    elif change == "unknown-user":
        meta["user_identity"] = ""
    elif change == "no-app":
        meta.clear()
    elif change == "test-mode":
        event["livemode"] = False
    else:
        event["data"] = {}
    with patch.object(wh.db, "get_conn", side_effect=AssertionError("DB called")):
        assert wh.persist_event(event) is False


@pytest.mark.parametrize("kind", sorted(scope.EVENTS))
def test_unknown_checkout_or_subscription_is_not_queued_or_processed(kind):
    event = delivery(kind)
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = None
    with patch.object(wh.db, "get_conn", return_value=conn):
        assert wh.persist_event(event) is False
    assert not any("INSERT" in c.args[0] for c in cur.execute.call_args_list)
    client = Mock()
    wh.process_event(cur, event, client)
    assert not client.mock_calls
    assert not any("INSERT" in c.args[0] or "UPDATE" in c.args[0]
                   for c in cur.execute.call_args_list)


def test_first_checkout_uses_reserved_attempt_even_before_customer_is_linked():
    cur = Mock()
    cur.fetchone.return_value = (1,)
    assert scope.belongs_to_app(cur, delivery())
    query, params = cur.execute.call_args.args
    assert "purchase_checkouts" in query and "stripe_session_id IS NULL" in query
    assert params == (IDENTITY, PRICE, "cs_scope", "attempt_scope")


def test_invoice_links_new_stripe_parent_shape_to_verified_subscription():
    event = delivery("invoice.payment_failed")
    obj = event["data"]["object"]
    obj.pop("subscription")
    obj["parent"] = {"subscription_details": {"subscription": {"id": "sub_scope"}}}
    cur = Mock()
    cur.fetchone.return_value = (1,)
    assert scope.belongs_to_app(cur, event)
    query, params = cur.execute.call_args.args
    assert params == ("sub_scope", "cus_scope", None)
    assert "checkout_verified" in query and "user_identity_hash" in query


def test_non_subscription_invoice_is_unused_without_database():
    event = delivery("invoice.payment_failed")
    event["data"]["object"].pop("subscription")
    with patch.object(wh.db, "get_conn", side_effect=AssertionError("DB called")):
        assert wh.persist_event(event) is False


def test_ownership_database_outage_is_not_misreported_as_an_unknown_purchase():
    with patch.object(wh.db, "get_conn", side_effect=RuntimeError("DB unavailable")):
        with pytest.raises(RuntimeError):
            wh.persist_event(delivery())


def test_missing_price_configuration_does_not_discard_a_potential_purchase(monkeypatch):
    monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
    with pytest.raises(RuntimeError, match="STRIPE_PRICE_ID"):
        scope.belongs_to_app(Mock(), delivery())


class ScopeReceiverTests(ReceiverTests):
    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_unit_test",
                             "STRIPE_PRICE_ID": PRICE})
    def test_foreign_event_returns_200_even_when_storage_is_unavailable(self):
        event = delivery()
        event["data"]["object"]["metadata"]["app"] = "another-app"
        body = json.dumps(event).encode()
        with patch.object(wh, "persist_event", side_effect=AssertionError("Storage called")):
            response = self.send(body, self.signature(body))
        assert response.code == 200 and json.loads(response.body)["ignored"]

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_unit_test",
                             "STRIPE_PRICE_ID": PRICE})
    def test_unknown_objects_return_200_without_queuing(self):
        for kind in sorted(scope.EVENTS):
            body = json.dumps(delivery(kind)).encode()
            conn = MagicMock()
            cur = conn.cursor.return_value.__enter__.return_value
            cur.fetchone.return_value = None
            with patch.object(wh.db, "get_conn", return_value=conn):
                response = self.send(body, self.signature(body))
            assert response.code == 200
            assert json.loads(response.body)["ignored"]
            assert not any("INSERT" in c.args[0] for c in cur.execute.call_args_list)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_unit_test",
                             "STRIPE_PRICE_ID": PRICE})
    def test_real_purchase_storage_failure_still_returns_503(self):
        body = json.dumps(delivery()).encode()
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = (1,)
        def execute(query, *args):
            if "INSERT INTO billing_webhook_events" in query:
                raise RuntimeError("Queue unavailable")
        cur.execute.side_effect = execute
        with patch.object(wh.db, "get_conn", return_value=conn):
            response = self.send(body, self.signature(body))
        assert response.code == 503
        assert json.loads(response.body)["error"] == "Please retry delivery"


def test_isolated_database_filters_unknown_customers_subscriptions_and_users(isolated_database):
    import purchase_store
    import db
    # A real first purchase is recognized before any Stripe customer record exists.
    attempt = purchase_store.reserve_checkout(IDENTITY, PRICE, 150000, "usd", "buyer@example.test")
    checkout = delivery()
    checkout["data"]["object"]["metadata"]["attempt_id"] = attempt["attempt_id"]
    assert wh.persist_event(checkout) is True
    foreign_checkout = deepcopy(checkout)
    foreign_checkout["id"] = "evt_other_user"
    foreign_checkout["data"]["object"]["metadata"]["user_identity"] = "f" * 64
    assert wh.persist_event(foreign_checkout) is False

    event = delivery("customer.subscription.updated")
    event["id"] = "evt_sub_scope"
    conn = db.get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO billing_webhook_accounts(customer_id) VALUES ('cus_scope')"
            )
            cur.execute(
                """INSERT INTO billing_webhook_subscriptions
                (subscription_id,customer_id,status,event_created,checkout_verified)
                VALUES ('sub_scope','cus_scope','active',100,true)"""
            )
        # Customer/subscription with no linked local user is ignored.
        assert wh.persist_event(event) is False
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE billing_webhook_accounts SET user_identity_hash=%s "
                "WHERE customer_id='cus_scope'", (IDENTITY,)
            )
        assert wh.persist_event(event) is True
        event["data"]["object"]["metadata"] = {"user_identity": "f" * 64}
        assert wh.persist_event(event) is False
        event["data"]["object"].pop("metadata")
        event["data"]["object"]["customer"] = "cus_unknown"
        assert wh.persist_event(event) is False
        event["data"]["object"]["customer"] = "cus_scope"
        event["data"]["object"]["id"] = "sub_unknown"
        assert wh.persist_event(event) is False
        with conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM billing_webhook_events")
            assert cur.fetchone()[0] == 2
    finally:
        conn.close()


def test_isolated_subscription_fulfillment_and_legacy_foreign_queue(isolated_database):
    import db
    import purchase_store
    attempt = purchase_store.reserve_checkout(IDENTITY, PRICE, 150000, "usd")
    checkout = delivery()
    checkout["id"] = "evt_sub_checkout"
    session = checkout["data"]["object"]
    session.update(mode="subscription", livemode=True, status="complete",
                   client_reference_id=IDENTITY,
                   line_items={"data": [{"price": {"id": PRICE}}]},
                   subscription={"id": "sub_owned", "customer": "cus_new", "status": "active"})
    session["metadata"]["attempt_id"] = attempt["attempt_id"]
    client = Mock()
    client.v1.checkout.sessions.retrieve.return_value = session
    assert wh.persist_event(checkout)
    assert wh.process_one(client)
    assert wh.subscription_access(IDENTITY)

    update = delivery("customer.subscription.updated")
    update["id"] = "evt_owned_update"
    update["created"] = 110
    update["data"]["object"].update(id="sub_owned", customer="cus_new", status="past_due")
    client.v1.subscriptions.retrieve.return_value = update["data"]["object"]
    assert wh.persist_event(update)
    assert wh.process_one(client)
    assert not wh.subscription_access(IDENTITY)

    # An unrelated event already queued by an older build is acknowledged
    # internally without calling Stripe or creating a foreign subscription.
    foreign = delivery("customer.subscription.updated")
    client.reset_mock()
    conn = db.get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO billing_webhook_events(id,payload) VALUES (%s,%s::jsonb)",
                (foreign["id"], json.dumps(foreign)),
            )
        assert wh.process_one(client)
        assert not client.mock_calls
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT processed_at,attempts FROM billing_webhook_events WHERE id=%s",
                (foreign["id"],),
            )
            processed, attempts = cur.fetchone()
            assert processed is not None and attempts == 0
            cur.execute(
                "SELECT count(*) FROM billing_webhook_subscriptions WHERE subscription_id='sub_scope'"
            )
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()

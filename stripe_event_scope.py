"""Recognize this app's purchases before queuing or applying Stripe events.

An unknown ID is ignored. A failed ownership lookup is not proof that an ID is
unknown: allow that failure to propagate so a real purchase is not lost.
"""
from collections.abc import Mapping
import os
import re

EVENTS = {
    "checkout.session.completed", "customer.subscription.updated",
    "customer.subscription.deleted", "invoice.payment_failed",
}


def _id(value):
    value = value.get("id") if isinstance(value, Mapping) else value
    return value if isinstance(value, str) and value else None


def _subscription_id(kind, obj):
    if kind.startswith("customer.subscription."):
        return _id(obj.get("id"))
    parent = obj.get("parent")
    details = parent.get("subscription_details") if isinstance(parent, Mapping) else None
    return _id(obj.get("subscription") or (
        details.get("subscription") if isinstance(details, Mapping) else None
    ))


def event_object(event):
    data = event.get("data") or {}
    obj = data.get("object") if isinstance(data, Mapping) else None
    return obj if isinstance(obj, Mapping) else {}


def potential_app_event(event):
    """Reject irrelevant types, test events and explicit foreign metadata without I/O."""
    if event.get("type") not in EVENTS or event.get("livemode") is not True:
        return False
    obj = event_object(event)
    meta = obj.get("metadata") or {}
    if not isinstance(meta, Mapping):
        return False
    if meta.get("app") not in (None, "", "soxlpro"):
        return False
    identity = meta.get("user_identity")
    if identity is not None and (
        not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{64}", identity)
    ):
        return False
    if event["type"] == "checkout.session.completed":
        if (meta.get("app") != "soxlpro" or not _id(obj.get("id"))
                or not isinstance(identity, str)
                or not re.fullmatch(r"[a-f0-9]{64}", identity)):
            return False
        declared_price = meta.get("price_id")
        configured_price = os.environ.get("STRIPE_PRICE_ID")
        if declared_price and configured_price and declared_price != configured_price:
            return False
    elif not _id(obj.get("customer")) or not _subscription_id(event["type"], obj):
        return False
    return True


def belongs_to_app(cur, event):
    """Use reserved checkouts or verified subscription/account links, never email alone."""
    if not potential_app_event(event):
        return False
    obj = event_object(event)
    kind = event["type"]
    if kind == "checkout.session.completed":
        if not os.environ.get("STRIPE_PRICE_ID"):
            raise RuntimeError("STRIPE_PRICE_ID is not configured")
        meta = obj["metadata"]
        # A first purchase may introduce a new Stripe customer. The existing,
        # server-bound attempt is its ownership proof, including the attach race.
        cur.execute(
            """SELECT 1 FROM purchase_checkouts
            WHERE user_identity_hash=%s AND price_id=%s
            AND (stripe_session_id=%s OR
                 (stripe_session_id IS NULL AND attempt_id=%s))
            LIMIT 1""",
            (meta["user_identity"], os.environ.get("STRIPE_PRICE_ID"),
             obj["id"], meta.get("attempt_id")),
        )
    else:
        subscription = _subscription_id(kind, obj)
        if not subscription:
            return False
        cur.execute(
            """SELECT 1 FROM billing_webhook_subscriptions s
            JOIN billing_webhook_accounts a ON a.customer_id=s.customer_id
            WHERE s.subscription_id=%s AND a.customer_id=%s
            AND s.checkout_verified
            AND a.user_identity_hash IS NOT NULL AND a.user_identity_hash<>''
            AND a.user_identity_hash=COALESCE(%s,a.user_identity_hash)
            LIMIT 1""",
            (subscription, _id(obj["customer"]), (obj.get("metadata") or {}).get("user_identity")),
        )
    return cur.fetchone() is not None

"""Validate a one-time payment before granting its server-bound Google email."""
from collections.abc import Mapping
import os

from billing import _charge_is_valid, _line_item_matches, _session_total


def _plain(value):
    return value.to_dict() if hasattr(value, "to_dict") else value


def record_paid_checkout(cur, session, identity, client):
    meta = session.get("metadata") or {}
    cur.execute(
        "SELECT id,price_id,expected_amount,expected_currency,status "
        "FROM purchase_checkouts WHERE user_identity_hash=%s AND price_id=%s "
        "AND (stripe_session_id=%s OR "
        "(stripe_session_id IS NULL AND attempt_id=%s)) FOR UPDATE",
        (identity, os.environ.get("STRIPE_PRICE_ID"),
         session["id"], meta.get("attempt_id")),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("Checkout has no server-bound purchase")
    record = row if isinstance(row, Mapping) else dict(zip(
        ("id", "price_id", "expected_amount", "expected_currency", "status"), row,
    ))
    if record["status"] in {"cancelled", "failed", "revoked", "expired"}:
        raise ValueError("Checkout purchase is not valid")
    plan = {
        "price_id": record["price_id"], "amount": record["expected_amount"],
        "currency": record["expected_currency"],
    }
    items = (session.get("line_items") or {}).get("data", [])
    total = _session_total(session, items, plan)
    if (session.get("payment_status") != "paid"
            or session.get("currency") != plan["currency"]
            or not _line_item_matches(items, plan) or total is None):
        raise ValueError("Checkout payment does not match the purchase")
    intent = _plain(session.get("payment_intent"))
    if isinstance(intent, str):
        intent = _plain(client.v1.payment_intents.retrieve(intent, {"expand": ["latest_charge"]}))
    if (not isinstance(intent, Mapping) or intent.get("status") != "succeeded"
            or intent.get("livemode") is not True or intent.get("amount") != total
            or intent.get("currency") != plan["currency"]):
        raise ValueError("Checkout payment intent is not confirmed")
    charge = _plain(intent.get("latest_charge"))
    if isinstance(charge, str):
        charge = _plain(client.v1.charges.retrieve(charge))
    if not isinstance(charge, Mapping) or not _charge_is_valid(charge, total, plan["currency"]):
        raise ValueError("Checkout charge is not valid")
    cur.execute(
        "UPDATE purchase_checkouts SET status='paid', "
        "stripe_session_id=COALESCE(stripe_session_id,%s), "
        "paid_at=COALESCE(paid_at,now()),updated_at=now(), "
        "verified_paid_at=COALESCE(verified_paid_at,now()) WHERE id=%s",
        (session["id"], record["id"]),
    )

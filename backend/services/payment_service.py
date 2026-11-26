"""
Demo payment validation. NOTHING here touches a real payment gateway and
NOTHING sensitive is stored or logged: card/PIN/CVV exist only in memory for
the duration of one comparison.
"""
import hmac
import re
import uuid
from datetime import datetime, timedelta

from flask import current_app

from utils.db import db
from models.payment import DemoPaymentSession


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def validate_demo_card(payment: dict) -> bool:
    """Compares against the fixed test values in config (spaces/dashes ignored)."""
    if not isinstance(payment, dict):
        return False
    cfg = current_app.config
    ok_card = _eq(_digits(payment.get("card_number")), _digits(cfg["DEMO_CARD_NUMBER"]))
    ok_pin = _eq(_digits(payment.get("pin")), _digits(cfg["DEMO_PIN"]))
    ok_cvv = _eq(_digits(payment.get("cvv")), _digits(cfg["DEMO_CVV"]))
    return ok_card and ok_pin and ok_cvv


def start_demo_qr_session(customer_id, amount, cart_hash_value) -> DemoPaymentSession:
    now = datetime.utcnow()
    sess = DemoPaymentSession(
        token=str(uuid.uuid4()),
        customer_id=customer_id,
        amount=amount,
        cart_hash=cart_hash_value,
        started_at=now,
        expires_at=now + timedelta(seconds=current_app.config["DEMO_QR_TOKEN_TTL_SECONDS"]),
    )
    db.session.add(sess)
    db.session.commit()
    return sess


def verify_demo_qr_session(token, customer_id, cart_hash_value):
    """
    Returns (session, error_message). The demo confirmation is only valid if:
    the token exists, belongs to this customer, was not used before, has not
    expired, covers exactly this cart, and the required wait has really elapsed
    on the SERVER clock.
    """
    if not token or not isinstance(token, str):
        return None, "Demo payment was not confirmed."
    sess = DemoPaymentSession.query.filter_by(token=token).with_for_update().first()
    if not sess or sess.customer_id != customer_id:
        return None, "Demo payment was not confirmed."
    if sess.consumed_at is not None:
        return None, "This demo payment has already been used."
    now = datetime.utcnow()
    if now > sess.expires_at:
        return None, "Demo payment session expired. Please start again."
    if sess.cart_hash != cart_hash_value:
        return None, "Your cart changed after the demo payment started. Please start again."
    elapsed = (now - sess.started_at).total_seconds()
    if elapsed < current_app.config["DEMO_QR_WAIT_SECONDS"]:
        return None, "Demo payment is still waiting for confirmation."
    return sess, None

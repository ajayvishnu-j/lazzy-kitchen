"""Common helper utilities: JSON responses, validation, auth, order numbers."""
import re
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo

from flask import jsonify, session, current_app

MOBILE_REGEX = re.compile(r"^[6-9]\d{9}$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TABLE_REGEX = re.compile(r"^[0-9A-Za-z\-]{1,10}$")
IDEMPOTENCY_REGEX = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


def success_response(message="Success", data=None, status_code=200):
    payload = {"success": True, "message": message}
    if data:
        payload.update(data)
    return jsonify(payload), status_code


def error_response(message="An error occurred", status_code=400):
    return jsonify({"success": False, "message": message}), status_code


def is_valid_mobile(mobile: str) -> bool:
    return bool(mobile) and bool(MOBILE_REGEX.match(mobile.strip()))


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(EMAIL_REGEX.match(email.strip()))


def is_valid_password(password: str) -> bool:
    """Minimum security requirement: at least 6 chars, 1 letter, 1 number."""
    if not password or len(password) < 6:
        return False
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_letter and has_digit


def is_valid_table(table: str) -> bool:
    return bool(table) and bool(TABLE_REGEX.match(table))


# ---------------------------------------------------------------------
# Customer session helpers
# ---------------------------------------------------------------------
def login_session(customer):
    session.clear()
    session["customer_id"] = customer.id
    session.permanent = True


def current_customer():
    from models.customer import Customer
    from utils.db import db
    cid = session.get("customer_id")
    return db.session.get(Customer, cid) if cid else None


def login_required(fn):
    """Rejects the request unless a valid customer session cookie is present."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        customer = current_customer()
        if not customer:
            session.clear()
            return error_response("Please log in to continue.", 401)
        return fn(customer, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------
# Order numbers:  LZK-YYYYMMDD-0001  (sequential per restaurant-local day)
# ---------------------------------------------------------------------
def restaurant_now() -> datetime:
    return datetime.now(ZoneInfo(current_app.config["RESTAURANT_TIMEZONE"]))


def next_order_number(order_model, db_session) -> str:
    prefix = f"LZK-{restaurant_now().strftime('%Y%m%d')}-"
    last = (
        db_session.query(order_model.order_number)
        .filter(order_model.order_number.like(f"{prefix}%"))
        .order_by(order_model.order_number.desc())
        .first()
    )
    seq = int(last[0].rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"

"""Customer registration, login, logout and session endpoints."""
import logging
from datetime import datetime

from flask import Blueprint, request, session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from utils.db import db
from utils.helpers import (
    success_response,
    error_response,
    is_valid_mobile,
    is_valid_email,
    is_valid_password,
    is_valid_table,
    login_session,
    login_required,
)
from models.customer import Customer

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger("lazzy_kitchen")

# Constant-time dummy hash so "unknown user" and "wrong password" take the same time.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    full_name = (data.get("full_name") or "").strip()
    mobile = (data.get("mobile") or "").strip()
    email = (data.get("email") or "").strip().lower()
    table_number = (data.get("table_number") or "").strip()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    # --- Backend validation (never trust frontend alone) ---
    if not full_name or len(full_name) > 120:
        return error_response("Full name is required.")
    if not is_valid_mobile(mobile):
        return error_response("Enter a valid 10-digit mobile number.")
    if not is_valid_email(email) or len(email) > 150:
        return error_response("Enter a valid email address.")
    if not is_valid_table(table_number):
        return error_response("Table number is required.")
    if not is_valid_password(password):
        return error_response(
            "Password must be at least 6 characters and include a letter and a number."
        )
    if password != confirm_password:
        return error_response("Passwords do not match.")

    if Customer.query.filter_by(email=email).first():
        return error_response("An account with this email already exists. Please log in.", 409)
    if Customer.query.filter_by(mobile=mobile).first():
        return error_response("An account with this mobile number already exists. Please log in.", 409)

    try:
        customer = Customer(
            full_name=full_name,
            mobile=mobile,
            email=email,
            table_number=table_number,
            password_hash=generate_password_hash(password),
            last_login_at=datetime.utcnow(),
        )
        db.session.add(customer)
        db.session.commit()
        login_session(customer)
        logger.info(f"New customer registered: id={customer.id}")
        return success_response(
            "Customer account created successfully.",
            {"customer": customer.to_dict()},
            status_code=201,
        )
    except IntegrityError:
        # Race: two requests passed the pre-check at the same time; the UNIQUE keys caught it.
        db.session.rollback()
        return error_response("An account with this email or mobile number already exists.", 409)
    except Exception:
        db.session.rollback()
        logger.exception("Registration failed due to a server error.")
        return error_response("Unable to create account. Please try again.", 500)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Log in with registered email OR 10-digit mobile number plus password."""
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or data.get("email") or data.get("mobile") or "").strip().lower()
    password = data.get("password") or ""

    if not identifier or not password:
        return error_response("Email or mobile number and password are required.")

    customer = Customer.query.filter(
        or_(Customer.email == identifier, Customer.mobile == identifier)
    ).first()

    stored_hash = customer.password_hash if customer else _DUMMY_HASH
    password_ok = check_password_hash(stored_hash, password)
    if not customer or not password_ok:
        return error_response("Invalid email/mobile or password.", 401)

    try:
        customer.last_login_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning("Could not update last_login_at.")

    login_session(customer)
    return success_response("Login successful.", {"customer": customer.to_dict()})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return success_response("Logged out.")


@auth_bp.route("/me", methods=["GET"])
@login_required
def me(customer):
    return success_response("Session active.", {"customer": customer.to_dict()})


@auth_bp.route("/me/table", methods=["PATCH"])
@login_required
def update_table(customer):
    """Lets a returning customer who sits at a different table today update it."""
    table = ((request.get_json(silent=True) or {}).get("table_number") or "").strip()
    if not is_valid_table(table):
        return error_response("Enter a valid table number.")
    customer.table_number = table
    db.session.commit()
    return success_response("Table updated.", {"customer": customer.to_dict()})

"""
Order placement and retrieval endpoints.

Payment notes (demo only):
  * DEMO_CARD : card/PIN/CVV are compared in memory with the fixed demo values
                and are NEVER persisted or logged.
  * DEMO_QR   : the order is accepted only with a server-issued token whose
                simulated wait really elapsed (see services/payment_service.py).
  * CASH      : stored as PENDING_CASH — never marked paid by this endpoint.
"""
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request
from sqlalchemy.exc import IntegrityError

from utils.db import db
from utils.helpers import (
    success_response,
    error_response,
    login_required,
    is_valid_table,
    next_order_number,
    IDEMPOTENCY_REGEX,
)
from models.order import Order, OrderItem, PAYMENT_METHODS
from services import pricing, payment_service
from services.slack_service import send_order_notification

orders_bp = Blueprint("orders", __name__)
logger = logging.getLogger("lazzy_kitchen")


def _order_payload(order, duplicate=False):
    return {
        "order": order.to_dict(),
        "estimated_preparation": order.estimated_preparation,
        "duplicate": duplicate,
    }


@orders_bp.route("/orders", methods=["POST"])
@login_required
def create_order(customer):
    data = request.get_json(silent=True) or {}

    # The customer is ALWAYS taken from the session, never from the request body.
    table_number = (data.get("table_number") or customer.table_number or "").strip()
    if not is_valid_table(table_number):
        return error_response("A valid table number is required.")

    payment = data.get("payment") if isinstance(data.get("payment"), dict) else {}
    method = (data.get("payment_method") or "").strip().upper()
    if not method and payment.get("card_number"):
        method = "DEMO_CARD"  # backwards compatibility with the original API
    if method not in PAYMENT_METHODS:
        return error_response("Please choose a payment method.")

    key = data.get("idempotency_key")
    if key is not None and not (isinstance(key, str) and IDEMPOTENCY_REGEX.match(key)):
        return error_response("Invalid request key.")

    # --- Rebuild the cart server-side from trusted menu prices ---
    try:
        lines = pricing.resolve_cart(data.get("items"))
    except pricing.CartError as exc:
        return error_response(str(exc), 400)

    unavailable = [l["item_name"] for l in lines if not l["available"]]
    if unavailable:
        return error_response(
            "Currently unavailable: " + ", ".join(unavailable) + ". Please remove it from your cart.", 409
        )

    config = pricing.get_config()
    if config and not config.is_open:
        return error_response("Ordering is currently unavailable. Restaurant is closed.", 403)

    totals = pricing.compute_totals(lines, pricing.tax_percent(config))

    # --- Duplicate-submission guard (double click / retry / refresh) ---
    if key:
        existing = Order.query.filter_by(customer_id=customer.id, idempotency_key=key).first()
        if existing:
            if pricing.money(existing.total) != totals["total"]:
                return error_response("This request key was already used for a different order.", 409)
            return success_response("Order already placed.", _order_payload(existing, True), 200)

    # --- Payment validation (demo only, nothing stored) ---
    qr_session = None
    if method == "DEMO_CARD":
        if not payment_service.validate_demo_card(payment):
            return error_response("Demo payment details are incorrect.", 402)
        payment_status = "PAID"
    elif method == "DEMO_QR":
        qr_session, err = payment_service.verify_demo_qr_session(
            data.get("demo_payment_token"), customer.id, pricing.cart_hash(lines, totals["total"])
        )
        if err:
            return error_response(err, 402)
        payment_status = "PAID"
    else:  # CASH
        payment_status = "PENDING_CASH"

    pmin, pmax = pricing.estimate_prep(lines, pricing.prep_buffer(config))
    now = datetime.utcnow()

    order = None
    for _attempt in range(3):
        try:
            order = Order(
                order_number=next_order_number(Order, db.session),
                customer_id=customer.id,
                customer_name=customer.full_name,
                table_number=table_number,
                subtotal=totals["subtotal"],
                tax=totals["tax"],
                total=totals["total"],
                status="PLACED",
                payment_method=method,
                payment_status=payment_status,
                est_prep_min_minutes=pmin,
                est_prep_max_minutes=pmax,
                est_ready_at=now + timedelta(minutes=pmax),
                idempotency_key=key,
                created_at=now,
            )
            db.session.add(order)
            db.session.flush()
            for l in lines:
                db.session.add(OrderItem(
                    order_id=order.id,
                    menu_item_id=l["menu_item_id"],
                    item_name=l["item_name"],
                    quantity=l["quantity"],
                    unit_price=l["unit_price"],
                    total_price=l["total_price"],
                ))
            if qr_session is not None:
                qr_session.consumed_at = now
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
            order = None
            if key:  # a parallel request with the same key won the race
                existing = Order.query.filter_by(customer_id=customer.id, idempotency_key=key).first()
                if existing:
                    return success_response("Order already placed.", _order_payload(existing, True), 200)
            # otherwise: order-number collision -> loop and take the next number
        except Exception:
            db.session.rollback()
            logger.exception("Order creation failed due to a server error.")
            return error_response("Unable to place your order. Please try again.", 500)

    if order is None:
        logger.error("Order creation failed after retries.")
        return error_response("Unable to place your order. Please try again.", 500)

    logger.info(f"Order created: {order.order_number} ({method})")

    # Slack notification failure must never block the response
    try:
        send_order_notification(order.to_dict())
    except Exception:
        logger.exception("Slack notification raised unexpectedly.")

    return success_response("Order placed successfully.", _order_payload(order), 201)


@orders_bp.route("/orders", methods=["GET"])
@login_required
def my_orders(customer):
    orders = (
        Order.query.filter_by(customer_id=customer.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .all()
    )
    return success_response("Orders loaded.", {"orders": [o.to_dict() for o in orders]})


@orders_bp.route("/orders/<order_number>", methods=["GET"])
@login_required
def get_order(customer, order_number):
    order = Order.query.filter_by(order_number=order_number, customer_id=customer.id).first()
    if not order:
        return error_response("Order not found.", 404)
    return success_response("Order found.", {"order": order.to_dict()})


@orders_bp.route("/orders/<order_number>/status", methods=["GET"])
@login_required
def get_order_status(customer, order_number):
    order = Order.query.filter_by(order_number=order_number, customer_id=customer.id).first()
    if not order:
        return error_response("Order not found.", 404)
    return success_response(
        "Status loaded.",
        {
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "status_updated_at": order.to_dict(False)["status_updated_at"],
            "est_ready_at": order.to_dict(False)["est_ready_at"],
        },
    )


@orders_bp.route("/customer/<int:customer_id>/orders", methods=["GET"])
@login_required
def get_customer_orders(customer, customer_id):
    if customer_id != customer.id:
        return error_response("You can only view your own orders.", 403)
    orders = (
        Order.query.filter_by(customer_id=customer.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .all()
    )
    return success_response("Orders loaded.", {"orders": [o.to_dict() for o in orders]})

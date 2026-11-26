"""
Minimal staff endpoints so the kitchen can move orders through the serving
flow (the status is NEVER advanced automatically, e.g. when the estimate
expires). Protected by a shared key in the X-Staff-Key header.

If STAFF_API_KEY is not set in the environment these endpoints are disabled.
"""
import hmac
import logging
from datetime import datetime
from functools import wraps

from flask import Blueprint, request, current_app

from utils.db import db
from utils.helpers import success_response, error_response
from models.order import Order, ORDER_STATUSES

staff_bp = Blueprint("staff", __name__)
logger = logging.getLogger("lazzy_kitchen")

NEXT_STATUS = {
    "PLACED": "CONFIRMED",
    "CONFIRMED": "PREPARING",
    "PREPARING": "READY",
    "READY": "SERVED",
}
CANCELLABLE = {"PLACED", "CONFIRMED", "PREPARING", "READY"}


def staff_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("STAFF_API_KEY") or ""
        if not expected:
            return error_response("Staff access is not enabled.", 403)
        supplied = request.headers.get("X-Staff-Key", "")
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            return error_response("Invalid staff key.", 401)
        return fn(*args, **kwargs)
    return wrapper


@staff_bp.route("/staff/orders", methods=["GET"])
@staff_required
def staff_orders():
    scope = request.args.get("scope", "active")
    query = Order.query
    if scope == "active":
        query = query.filter(Order.status.notin_(["SERVED", "CANCELLED"]))
    orders = query.order_by(Order.created_at.asc(), Order.id.asc()).limit(200).all()
    return success_response("Orders loaded.", {"orders": [o.to_dict() for o in orders]})


@staff_bp.route("/staff/orders/<order_number>/status", methods=["PATCH"])
@staff_required
def staff_update_status(order_number):
    new_status = ((request.get_json(silent=True) or {}).get("status") or "").upper()
    if new_status not in ORDER_STATUSES:
        return error_response("Unknown status.")
    order = Order.query.filter_by(order_number=order_number).with_for_update().first()
    if not order:
        return error_response("Order not found.", 404)

    allowed = (new_status == "CANCELLED" and order.status in CANCELLABLE) or \
              NEXT_STATUS.get(order.status) == new_status
    if not allowed:
        return error_response(f"Cannot move an order from {order.status} to {new_status}.", 409)

    order.status = new_status
    order.status_updated_at = datetime.utcnow()
    db.session.commit()
    logger.info(f"Order {order.order_number} -> {new_status}")
    return success_response("Status updated.", {"order": order.to_dict()})


@staff_bp.route("/staff/orders/<order_number>/payment", methods=["PATCH"])
@staff_required
def staff_mark_cash_paid(order_number):
    """Counter staff confirm the cash was actually collected."""
    order = Order.query.filter_by(order_number=order_number).with_for_update().first()
    if not order:
        return error_response("Order not found.", 404)
    if order.payment_method != "CASH":
        return error_response("Only cash orders can be marked as paid here.", 409)
    if order.status == "CANCELLED":
        return error_response("This order was cancelled.", 409)
    order.payment_status = "PAID"
    db.session.commit()
    return success_response("Cash payment recorded.", {"order": order.to_dict()})

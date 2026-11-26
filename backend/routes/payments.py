"""Demo payment helper endpoints (no real gateway, nothing sensitive stored)."""
import logging
from flask import Blueprint, request, current_app

from utils.helpers import success_response, error_response, login_required
from services import pricing, payment_service

payments_bp = Blueprint("payments", __name__)
logger = logging.getLogger("lazzy_kitchen")


@payments_bp.route("/payments/demo-qr/start", methods=["POST"])
@login_required
def start_demo_qr(customer):
    """
    Called when the customer selects the Google Pay *demo* option. The server
    prices the cart, records when the simulation started, and returns a random
    token. An order can only be created with this token after the wait elapsed.
    """
    data = request.get_json(silent=True) or {}
    try:
        lines = pricing.resolve_cart(data.get("items"))
    except pricing.CartError as exc:
        return error_response(str(exc), 400)

    if any(not l["available"] for l in lines):
        return error_response("Some items in your cart are unavailable.", 409)

    config = pricing.get_config()
    if config and not config.is_open:
        return error_response("Ordering is currently unavailable. Restaurant is closed.", 403)

    totals = pricing.compute_totals(lines, pricing.tax_percent(config))
    sess = payment_service.start_demo_qr_session(
        customer.id, totals["total"], pricing.cart_hash(lines, totals["total"])
    )
    return success_response(
        "Demo payment started.",
        {
            "token": sess.token,
            "amount": float(totals["total"]),
            "wait_seconds": current_app.config["DEMO_QR_WAIT_SECONDS"],
            "demo": True,
        },
    )

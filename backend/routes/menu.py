"""Menu browsing and cart validation endpoints."""
import logging
from flask import Blueprint, request

from utils.helpers import success_response, error_response, login_required
from models.menu import MenuItem, MAIN_CATEGORIES
from services import pricing

menu_bp = Blueprint("menu", __name__)
logger = logging.getLogger("lazzy_kitchen")

CATEGORY_ALIASES = {
    "food": "FOOD",
    "snacks": "SNACKS_BEVERAGES",
    "snacks_beverages": "SNACKS_BEVERAGES",
    "snacks-beverages": "SNACKS_BEVERAGES",
}


@menu_bp.route("/menu", methods=["GET"])
def get_menu():
    """
    GET /api/menu                      -> everything
    GET /api/menu?category=FOOD        -> FOOD only
    GET /api/menu?category=SNACKS_BEVERAGES (alias: snacks)
    Items are ordered for display; 'groups' lists the sub-categories in order.
    """
    raw = (request.args.get("category") or "").strip()
    category = None
    if raw:
        category = CATEGORY_ALIASES.get(raw.lower(), raw.upper())
        if category not in MAIN_CATEGORIES:
            return error_response("Unknown menu category.", 400)
    try:
        query = MenuItem.query
        if category:
            query = query.filter_by(main_category=category)
        items = query.order_by(MenuItem.sort_order, MenuItem.id).all()
        config = pricing.get_config()

        groups = []
        for it in items:
            key = (it.main_category, it.category)
            if key not in groups:
                groups.append(key)

        return success_response(
            "Menu loaded.",
            {
                "items": [item.to_dict() for item in items],
                "groups": [{"main_category": m, "name": g} for m, g in groups],
                "restaurant_status": config.to_dict() if config else None,
            },
        )
    except Exception:
        logger.exception("Failed to load menu.")
        return error_response("Unable to load menu. Please try again.", 500)


@menu_bp.route("/menu/<int:item_id>", methods=["GET"])
def get_menu_item(item_id):
    item = MenuItem.query.get(item_id)
    if not item:
        return error_response("Menu item not found.", 404)
    return success_response("Menu item found.", {"item": item.to_dict()})


@menu_bp.route("/status", methods=["GET"])
def restaurant_status():
    config = pricing.get_config()
    if not config:
        return error_response("Restaurant configuration not found.", 500)
    return success_response("Status loaded.", {"restaurant_status": config.to_dict()})


@menu_bp.route("/cart/validate", methods=["POST"])
@login_required
def validate_cart(_customer):
    """
    Authoritative re-pricing of the browser cart: current prices, availability,
    subtotal / tax / total and the prep-time estimate. The UI uses this to
    refresh the cart and block checkout when an item became unavailable.
    """
    data = request.get_json(silent=True) or {}
    try:
        lines = pricing.resolve_cart(data.get("items"))
    except pricing.CartError as exc:
        return error_response(str(exc), 400)

    config = pricing.get_config()
    pct = pricing.tax_percent(config)
    totals = pricing.compute_totals([l for l in lines if l["available"]], pct)
    unavailable = [l["item_name"] for l in lines if not l["available"]]
    pmin, pmax = pricing.estimate_prep([l for l in lines if l["available"]], pricing.prep_buffer(config))

    return success_response(
        "Cart validated.",
        {
            "valid": not unavailable,
            "restaurant_open": bool(config.is_open) if config else True,
            "unavailable_items": unavailable,
            "items": pricing.serialise_lines(lines),
            "tax_percent": float(pct),
            "subtotal": float(totals["subtotal"]),
            "tax": float(totals["tax"]),
            "total": float(totals["total"]),
            "est_prep_min_minutes": pmin,
            "est_prep_max_minutes": pmax,
        },
    )

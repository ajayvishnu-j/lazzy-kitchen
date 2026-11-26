"""
Server-side cart validation, price/total calculation and prep-time estimation.
The browser's prices are NEVER trusted: everything is rebuilt from MySQL.
"""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from flask import current_app

from utils.db import db
from models.menu import MenuItem, RestaurantConfig

TWO_PLACES = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class CartError(Exception):
    """Raised for malformed carts. Message is safe to show to the customer."""


def get_config():
    return db.session.get(RestaurantConfig, 1)


def tax_percent(config) -> Decimal:
    if config and config.tax_percent is not None:
        return Decimal(str(config.tax_percent))
    return Decimal(str(current_app.config["TAX_PERCENT_DEFAULT"]))


def prep_buffer(config) -> int:
    if config and config.prep_buffer_minutes is not None:
        return int(config.prep_buffer_minutes)
    return int(current_app.config["PREP_BUFFER_DEFAULT"])


def resolve_cart(raw_items):
    """
    Turns the client cart [{menu_item_id, quantity}] into trusted lines.
    Duplicate ids are merged. Returns a list of dicts; unavailable items are
    returned with available=False so the caller decides how to react.
    Raises CartError for malformed input.
    """
    cfg = current_app.config
    if not isinstance(raw_items, list) or not raw_items:
        raise CartError("Your cart is empty.")

    wanted = {}
    for entry in raw_items:
        if not isinstance(entry, dict):
            raise CartError("Invalid cart item.")
        try:
            item_id = int(entry.get("menu_item_id"))
            qty = int(entry.get("quantity"))
        except (TypeError, ValueError):
            raise CartError("Invalid item or quantity in cart.")
        if qty < 1:
            raise CartError("Quantity must be at least 1 for every item.")
        wanted[item_id] = wanted.get(item_id, 0) + qty

    if len(wanted) > cfg["MAX_DISTINCT_ITEMS"]:
        raise CartError("Too many different items in one order.")
    for qty in wanted.values():
        if qty > cfg["MAX_QTY_PER_ITEM"]:
            raise CartError(f"You can order at most {cfg['MAX_QTY_PER_ITEM']} of one item.")

    rows = MenuItem.query.filter(MenuItem.id.in_(list(wanted))).all()
    by_id = {r.id: r for r in rows}
    missing = [i for i in wanted if i not in by_id]
    if missing:
        raise CartError("Some items in your cart are no longer on the menu.")

    lines = []
    for item_id in sorted(wanted):
        m = by_id[item_id]
        unit = money(m.price)
        qty = wanted[item_id]
        lines.append({
            "menu_item_id": m.id,
            "item_name": m.name,
            "image_path": m.image_path,
            "quantity": qty,
            "unit_price": unit,
            "total_price": money(unit * qty),
            "available": bool(m.is_available),
            "prep_time_min": m.prep_time_min,
            "prep_time_max": m.prep_time_max,
        })
    return lines


def compute_totals(lines, tax_pct) -> dict:
    subtotal = money(sum((l["total_price"] for l in lines), Decimal("0")))
    tax = money(subtotal * Decimal(tax_pct) / Decimal(100))
    return {"subtotal": subtotal, "tax": tax, "total": money(subtotal + tax)}


def estimate_prep(lines, buffer_minutes: int):
    """
    Longest item prep time drives the order; a configurable buffer is added
    to both ends (kitchen load, plating, walking to the table).
    Returns (min_minutes, max_minutes).
    """
    if not lines:
        return 0, 0
    longest_min = max(l["prep_time_min"] for l in lines)
    longest_max = max(l["prep_time_max"] for l in lines)
    return longest_min + buffer_minutes, longest_max + buffer_minutes


def cart_hash(lines, total) -> str:
    """Stable fingerprint of (items, quantities, total) used to bind a demo-QR token to one cart."""
    payload = json.dumps(
        {"items": [[l["menu_item_id"], l["quantity"]] for l in lines], "total": str(total)},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def serialise_lines(lines):
    out = []
    for l in lines:
        d = dict(l)
        d["unit_price"] = float(l["unit_price"])
        d["total_price"] = float(l["total_price"])
        out.append(d)
    return out

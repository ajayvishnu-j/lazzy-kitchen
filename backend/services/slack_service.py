"""
Sends order notifications to Slack via an Incoming Webhook.
The webhook URL is read from environment variables only — never exposed
to the frontend and never logged. Passwords, card numbers, PINs and CVVs are
never part of the payload (the order dict simply does not contain them).
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import current_app

logger = logging.getLogger("lazzy_kitchen")

PAYMENT_LABELS = {"DEMO_CARD": "DEMO CARD", "DEMO_QR": "DEMO GOOGLE PAY QR", "CASH": "CASH"}


def _esc(text) -> str:
    """Slack mrkdwn control characters must be escaped in user-supplied text."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_money(value) -> str:
    value = float(value)
    return f"₹{value:,.0f}" if value == int(value) else f"₹{value:,.2f}"


def _order_time(order: dict) -> str:
    raw = order.get("created_at")
    try:
        dt = datetime.fromisoformat(raw.rstrip("Z")).replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo(current_app.config["RESTAURANT_TIMEZONE"])).strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return str(raw)


def build_message(order: dict) -> str:
    lines = "\n".join(
        f"• {_esc(i['item_name'])} x{i['quantity']} @ {_fmt_money(i['unit_price'])} = {_fmt_money(i['total_price'])}"
        for i in order["items"]
    )
    pay = PAYMENT_LABELS.get(order["payment_method"], order["payment_method"])
    prep = f"{order['est_prep_min_minutes']}–{order['est_prep_max_minutes']} Minutes"
    cash_note = "\n:warning: *Cash NOT yet collected — collect at the counter.*" if order["payment_status"] == "PENDING_CASH" else ""
    return (
        ":fork_and_knife: *NEW ORDER – HOTEL LAZZY-KITCHEN*\n\n"
        f"*Customer:* {_esc(order['customer_name'])}\n"
        f"*Table:* {_esc(order['table_number'])}\n"
        f"*Order ID:* {order['order_number']}\n\n"
        f"*Items:*\n{lines}\n\n"
        f"*Subtotal:* {_fmt_money(order['subtotal'])}   *Tax:* {_fmt_money(order['tax'])}\n"
        f"*Total:* {_fmt_money(order['total'])}\n"
        f"*Payment:* {pay}\n"
        f"*Payment Status:* {order['payment_status']}\n"
        f"*Status:* {order['status']}\n"
        f"*Order Time:* {_order_time(order)}\n"
        f"*Preparation:* {prep} (estimate)"
        f"{cash_note}"
    )


def send_order_notification(order: dict) -> bool:
    """
    Returns True on success, False otherwise. Never raises — a Slack failure
    must not block order placement.
    """
    webhook_url = current_app.config.get("SLACK_WEBHOOK_URL")
    if not webhook_url or "CHANGE/THIS" in webhook_url:
        logger.info("Slack webhook not configured — skipping notification.")
        return False

    try:
        response = requests.post(webhook_url, json={"text": build_message(order)}, timeout=5)
        if response.status_code == 200:
            logger.info(f"Slack notification sent for order {order['order_number']}.")
            return True
        logger.warning(f"Slack notification failed with status {response.status_code}.")
        return False
    except Exception as exc:  # noqa: BLE001 - must never break order flow
        logger.warning(f"Slack notification error: {type(exc).__name__}")
        return False

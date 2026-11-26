"""
Backend test suite for Hotel Lazzy-Kitchen.
Runs against in-memory SQLite so no MySQL server is needed
(MySQL-specific behaviour is covered by the migration check in docs/ENHANCEMENTS.md).
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from utils.db import db  # noqa: E402
from menu_catalog import CATALOG  # noqa: E402
from models.menu import MenuItem, RestaurantConfig  # noqa: E402
from models.order import Order  # noqa: E402
from models.payment import DemoPaymentSession  # noqa: E402
from models.customer import Customer  # noqa: E402

DEMO_CARD = {"card_number": "1234 4321 5678 8765", "pin": "4321", "cvv": "123"}


@pytest.fixture
def app():
    flask_app = create_app({
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "STAFF_API_KEY": "staff-test-key",
        "SLACK_WEBHOOK_URL": "",
    })
    with flask_app.app_context():
        db.create_all()
        db.session.add(RestaurantConfig(id=1, is_open=True, prep_time_min_minutes=15,
                                        prep_time_max_minutes=25, tax_percent=5.0, prep_buffer_minutes=5))
        for n, it in enumerate(CATALOG, start=1):
            db.session.add(MenuItem(
                slug=it["slug"], name=it["name"], description=it["description"], price=it["price"],
                category=it["category"], main_category=it["main_category"], flavour=it["flavour"],
                is_vegetarian=bool(it["is_vegetarian"]), is_available=True, sort_order=n * 10,
                image_path=f"assets/images/menu/{it['slug']}.jpg",
                prep_time_min=it["prep_time_min"], prep_time_max=it["prep_time_max"]))
        db.session.commit()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def item_id(slug):
    return MenuItem.query.filter_by(slug=slug).first().id


def register(client, name="Ajay Vishnu", mobile="9876543210", email="ajay@example.com",
             table="12", password="ajay123"):
    return client.post("/api/register", json={
        "full_name": name, "mobile": mobile, "email": email, "table_number": table,
        "password": password, "confirm_password": password})


def order_body(app, slugs_qty, method="DEMO_CARD", **extra):
    with app.app_context():
        items = [{"menu_item_id": item_id(s), "quantity": q} for s, q in slugs_qty]
    body = {"table_number": "12", "items": items, "payment_method": method}
    if method == "DEMO_CARD":
        body["payment"] = dict(DEMO_CARD)
    body.update(extra)
    return body


# ---------------------------------------------------------------------
# 1-3. Authentication
# ---------------------------------------------------------------------
def test_health(client):
    assert client.get("/api/health").get_json()["status"] == "healthy"


def test_register_success_logs_in_and_hashes_password(app, client):
    r = register(client)
    assert r.status_code == 201
    assert "password" not in str(r.get_json()).lower().replace("password_hash", "")
    assert client.get("/api/me").status_code == 200
    with app.app_context():
        c = Customer.query.filter_by(email="ajay@example.com").first()
        assert c.password_hash != "ajay123" and c.password_hash.startswith(("scrypt:", "pbkdf2:"))


@pytest.mark.parametrize("patch,msg", [
    ({"mobile": "12345"}, "mobile"),
    ({"email": "bad"}, "email"),
    ({"password": "abc"}, "Password"),
])
def test_register_validation(client, patch, msg):
    body = {"full_name": "A", "mobile": "9876543210", "email": "a@b.co", "table_number": "1",
            "password": "pass123", "confirm_password": "pass123"}
    body.update(patch)
    body["confirm_password"] = body["password"]
    r = client.post("/api/register", json=body)
    assert r.status_code == 400 and msg.lower() in r.get_json()["message"].lower()


def test_register_password_mismatch(client):
    r = client.post("/api/register", json={"full_name": "A", "mobile": "9876543210", "email": "a@b.co",
                                           "table_number": "1", "password": "pass123", "confirm_password": "x"})
    assert r.status_code == 400


def test_duplicate_email_and_mobile_prevented(app, client):
    register(client)
    assert register(client, mobile="9111111111").status_code == 409            # same email
    assert register(client, email="other@example.com").status_code == 409      # same mobile
    with app.app_context():
        assert Customer.query.count() == 1


def test_login_with_email_and_with_mobile(client):
    register(client)
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401
    r = client.post("/api/login", json={"identifier": "AJAY@example.com", "password": "ajay123"})
    assert r.status_code == 200 and r.get_json()["customer"]["full_name"] == "Ajay Vishnu"
    client.post("/api/logout")
    r = client.post("/api/login", json={"identifier": "9876543210", "password": "ajay123"})
    assert r.status_code == 200
    assert client.get("/api/me").get_json()["customer"]["email"] == "ajay@example.com"


def test_login_legacy_email_field_still_works(client):
    register(client)
    client.post("/api/logout")
    assert client.post("/api/login", json={"email": "ajay@example.com", "password": "ajay123"}).status_code == 200


def test_login_wrong_password_and_unknown_user(client):
    register(client)
    client.post("/api/logout")
    assert client.post("/api/login", json={"identifier": "ajay@example.com", "password": "nope123"}).status_code == 401
    assert client.post("/api/login", json={"identifier": "ghost@example.com", "password": "ajay123"}).status_code == 401
    assert client.get("/api/me").status_code == 401


def test_login_does_not_create_duplicate_accounts(app, client):
    register(client)
    for _ in range(3):
        client.post("/api/login", json={"identifier": "ajay@example.com", "password": "ajay123"})
    with app.app_context():
        assert Customer.query.count() == 1


def test_logout_ends_session(client):
    register(client)
    client.post("/api/logout")
    assert client.post("/api/orders", json={}).status_code == 401


# ---------------------------------------------------------------------
# 4-5. Menu
# ---------------------------------------------------------------------
def test_menu_all_items_present_and_unique(client):
    items = client.get("/api/menu").get_json()["items"]
    assert len(items) == 45
    assert len({i["name"] for i in items}) == 45
    assert len({i["image_path"] for i in items}) == 45          # no image reused across dishes
    assert all(i["image_path"].startswith("assets/images/menu/") for i in items)


def test_menu_by_category(client):
    food = client.get("/api/menu?category=FOOD").get_json()
    snacks = client.get("/api/menu?category=snacks").get_json()
    assert len(food["items"]) == 23 and len(snacks["items"]) == 22
    assert {i["main_category"] for i in food["items"]} == {"FOOD"}
    assert [g["name"] for g in food["groups"]] == ["South Indian", "Rice & Main Course"]
    assert [g["name"] for g in snacks["groups"]] == ["Tea", "Coffee", "Donuts", "Pizza", "Burger", "Shawarma", "Additional Snacks"]
    assert client.get("/api/menu?category=bogus").status_code == 400


def test_requested_items_and_flavour_counts(client):
    items = client.get("/api/menu").get_json()["items"]
    by_group = {}
    for i in items:
        by_group.setdefault(i["category"], []).append(i["name"])
    assert len(by_group["South Indian"]) == 11 and len(by_group["Rice & Main Course"]) == 12
    assert len(by_group["Tea"]) == 3 and len(by_group["Coffee"]) == 5 and len(by_group["Donuts"]) == 3
    assert len(by_group["Pizza"]) == 3 and len(by_group["Burger"]) == 4 and len(by_group["Shawarma"]) == 2
    assert by_group["Additional Snacks"] == ["French Fries", "Peri Peri Fries"]
    for expected in ["Mutton Mandi", "Chicken Kothu Parotta", "Paneer Butter Masala", "Double Chicken Burger",
                     "Peri Peri Fries", "Mocha", "Ghee Roast", "Medu Vadai"]:
        assert any(i["name"] == expected for i in items), expected


def test_prices_come_from_database_and_are_configurable(app, client):
    with app.app_context():
        MenuItem.query.filter_by(slug="idly").first().price = 99
        db.session.commit()
    idly = next(i for i in client.get("/api/menu").get_json()["items"] if i["slug"] == "idly")
    assert idly["price"] == 99.0


# ---------------------------------------------------------------------
# 6. Cart validation & totals
# ---------------------------------------------------------------------
def test_cart_validate_totals_and_prep(app, client):
    register(client)
    with app.app_context():
        items = [{"menu_item_id": item_id("chicken-biryani"), "quantity": 2},
                 {"menu_item_id": item_id("filter-coffee"), "quantity": 2}]
    r = client.post("/api/cart/validate", json={"items": items}).get_json()
    assert r["valid"] and r["subtotal"] == 500.0 and r["tax"] == 25.0 and r["total"] == 525.0
    # longest = biryani 20-30, + 5 min buffer
    assert (r["est_prep_min_minutes"], r["est_prep_max_minutes"]) == (25, 35)


def test_cart_validate_flags_unavailable_and_ignores_client_prices(app, client):
    register(client)
    with app.app_context():
        MenuItem.query.filter_by(slug="poori").first().is_available = False
        db.session.commit()
        pid, iid = item_id("poori"), item_id("idly")
    r = client.post("/api/cart/validate", json={"items": [
        {"menu_item_id": pid, "quantity": 1, "unit_price": 1},
        {"menu_item_id": iid, "quantity": 1, "unit_price": 1}]}).get_json()
    assert r["valid"] is False and r["unavailable_items"] == ["Poori"]
    assert r["subtotal"] == 50.0  # unavailable excluded; client-sent price ignored


@pytest.mark.parametrize("items", [[], None, "x", [{"menu_item_id": 1, "quantity": 0}],
                                   [{"menu_item_id": 1, "quantity": -2}], [{"menu_item_id": 1, "quantity": 21}],
                                   [{"menu_item_id": 9999, "quantity": 1}], [{"menu_item_id": "a", "quantity": 1}]])
def test_cart_rejects_malformed(client, items):
    register(client)
    assert client.post("/api/cart/validate", json={"items": items}).status_code == 400


def test_decimal_rounding(app, client):
    register(client)
    with app.app_context():
        MenuItem.query.filter_by(slug="idly").first().price = 33.33
        db.session.commit()
    r = client.post("/api/orders", json=order_body(app, [("idly", 3)])).get_json()["order"]
    assert (r["subtotal"], r["tax"], r["total"]) == (99.99, 5.0, 104.99)


# ---------------------------------------------------------------------
# 9. Demo card
# ---------------------------------------------------------------------
def test_card_accepts_demo_values_with_or_without_spaces(app, client):
    register(client)
    b = order_body(app, [("idly", 1)])
    assert client.post("/api/orders", json=b).status_code == 201
    b = order_body(app, [("idly", 1)])
    b["payment"]["card_number"] = "1234432156788765"
    assert client.post("/api/orders", json=b).status_code == 201


@pytest.mark.parametrize("field,value", [("card_number", "1234 4321 5678 8766"), ("pin", "0000"),
                                         ("cvv", "999"), ("card_number", ""), ("pin", None)])
def test_card_rejects_wrong_values(app, client, field, value):
    register(client)
    b = order_body(app, [("idly", 1)])
    b["payment"][field] = value
    r = client.post("/api/orders", json=b)
    assert r.status_code == 402
    with app.app_context():
        assert Order.query.count() == 0


# ---------------------------------------------------------------------
# 10. Demo QR (server-enforced 10 s)
# ---------------------------------------------------------------------
def _start_qr(client, app, slugs):
    body = order_body(app, slugs, "DEMO_QR")
    r = client.post("/api/payments/demo-qr/start", json={"items": body["items"]})
    return body, r


def test_qr_rejected_before_wait_elapsed(app, client):
    register(client)
    body, r = _start_qr(client, app, [("idly", 1)])
    assert r.status_code == 200 and r.get_json()["wait_seconds"] == 10 and r.get_json()["demo"] is True
    body["demo_payment_token"] = r.get_json()["token"]
    assert client.post("/api/orders", json=body).status_code == 402


def _age(app, token, seconds):
    with app.app_context():
        s = DemoPaymentSession.query.filter_by(token=token).first()
        s.started_at = datetime.utcnow() - timedelta(seconds=seconds)
        db.session.commit()


def test_qr_accepted_after_wait_and_token_single_use(app, client):
    register(client)
    body, r = _start_qr(client, app, [("idly", 2)])
    token = r.get_json()["token"]
    body["demo_payment_token"] = token
    _age(app, token, 11)
    ok = client.post("/api/orders", json=body)
    assert ok.status_code == 201
    o = ok.get_json()["order"]
    assert o["payment_method"] == "DEMO_QR" and o["payment_status"] == "PAID"
    # same token, no idempotency key -> must NOT create a second order
    assert client.post("/api/orders", json=body).status_code == 402
    with app.app_context():
        assert Order.query.count() == 1


def test_qr_token_bound_to_cart_customer_and_existence(app, client):
    register(client)
    body, r = _start_qr(client, app, [("idly", 1)])
    token = r.get_json()["token"]
    _age(app, token, 11)
    other_cart = order_body(app, [("chicken-biryani", 1)], "DEMO_QR", demo_payment_token=token)
    assert client.post("/api/orders", json=other_cart).status_code == 402        # cart changed
    assert client.post("/api/orders", json=order_body(app, [("idly", 1)], "DEMO_QR")).status_code == 402  # no token
    assert client.post("/api/orders", json=order_body(app, [("idly", 1)], "DEMO_QR", demo_payment_token="x" * 36)).status_code == 402
    # another customer cannot reuse it
    c2 = client.application.test_client()
    register(c2, mobile="9000000001", email="b@example.com")
    assert c2.post("/api/orders", json=order_body(app, [("idly", 1)], "DEMO_QR", demo_payment_token=token)).status_code == 402


def test_qr_expired_token(app, client):
    register(client)
    body, r = _start_qr(client, app, [("idly", 1)])
    token = r.get_json()["token"]
    with app.app_context():
        s = DemoPaymentSession.query.filter_by(token=token).first()
        s.started_at = datetime.utcnow() - timedelta(hours=1)
        s.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
    body["demo_payment_token"] = token
    assert client.post("/api/orders", json=body).status_code == 402


# ---------------------------------------------------------------------
# 11. Cash
# ---------------------------------------------------------------------
def test_cash_order_is_pending_cash_not_paid(app, client):
    register(client)
    r = client.post("/api/orders", json=order_body(app, [("idly", 1)], "CASH"))
    o = r.get_json()["order"]
    assert r.status_code == 201 and o["payment_status"] == "PENDING_CASH" and o["status"] == "PLACED"


def test_cannot_place_order_without_valid_method(app, client):
    register(client)
    b = order_body(app, [("idly", 1)])
    b["payment_method"] = "UPI"
    assert client.post("/api/orders", json=b).status_code == 400


# ---------------------------------------------------------------------
# 12-13. Order creation, order number, prep time
# ---------------------------------------------------------------------
def test_order_persisted_with_all_fields(app, client):
    register(client)
    r = client.post("/api/orders", json=order_body(app, [("chicken-biryani", 2), ("chicken-65", 1), ("filter-coffee", 2)]))
    assert r.status_code == 201
    o = r.get_json()["order"]
    assert o["order_number"].startswith("LZK-") and o["order_number"].endswith("-0001")
    assert len(o["order_number"]) == len("LZK-20261124-0001")
    assert o["customer_name"] == "Ajay Vishnu" and o["table_number"] == "12"
    assert (o["subtotal"], o["tax"], o["total"]) == (680.0, 34.0, 714.0)
    assert o["payment_method"] == "DEMO_CARD" and o["payment_status"] == "PAID" and o["status"] == "PLACED"
    assert [(i["item_name"], i["quantity"], i["unit_price"]) for i in o["items"]] == [
        ("Chicken Biryani", 2, 220.0), ("Chicken 65", 1, 180.0), ("Filter Coffee", 2, 30.0)]
    assert o["est_ready_at"].endswith("Z")
    assert r.get_json()["estimated_preparation"] == "25\u201335 minutes"


def test_order_numbers_sequential(app, client):
    register(client)
    nums = [client.post("/api/orders", json=order_body(app, [("idly", 1)])).get_json()["order"]["order_number"] for _ in range(3)]
    assert [n.rsplit("-", 1)[1] for n in nums] == ["0001", "0002", "0003"]


@pytest.mark.parametrize("slugs,expected", [
    ([("normal-tea", 1)], (10, 15)),                       # tea 5-10 (+5)
    ([("filter-coffee", 3), ("black-tea", 1)], (10, 15)),
    ([("french-fries", 1)], (15, 20)),                     # snack 10-15 (+5)
    ([("idly", 1)], (15, 20)),                             # tiffin 10-15 (+5)
    ([("plain-dosa", 1)], (15, 25)),                       # tiffin 10-20 (+5)
    ([("veg-biryani", 1)], (25, 35)),                      # biryani 20-30 (+5)
    ([("mutton-mandi", 1)], (35, 45)),                     # mandi 30-40 (+5)
    ([("mutton-mandi", 1), ("normal-tea", 2), ("idly", 1)], (35, 45)),  # longest wins
])
def test_prep_time_estimates(app, client, slugs, expected):
    register(client)
    o = client.post("/api/orders", json=order_body(app, slugs)).get_json()["order"]
    assert (o["est_prep_min_minutes"], o["est_prep_max_minutes"]) == expected


def test_prep_buffer_is_configurable(app, client):
    register(client)
    with app.app_context():
        db.session.get(RestaurantConfig, 1).prep_buffer_minutes = 0
        db.session.commit()
    o = client.post("/api/orders", json=order_body(app, [("mutton-mandi", 1)])).get_json()["order"]
    assert (o["est_prep_min_minutes"], o["est_prep_max_minutes"]) == (30, 40)


def test_unavailable_item_cannot_be_ordered(app, client):
    register(client)
    with app.app_context():
        MenuItem.query.filter_by(slug="idly").first().is_available = False
        db.session.commit()
    r = client.post("/api/orders", json=order_body(app, [("idly", 1)]))
    assert r.status_code == 409 and "Idly" in r.get_json()["message"]


def test_restaurant_closed_blocks_orders(app, client):
    register(client)
    with app.app_context():
        db.session.get(RestaurantConfig, 1).is_open = False
        db.session.commit()
    assert client.post("/api/orders", json=order_body(app, [("idly", 1)])).status_code == 403


def test_client_cannot_override_price_or_customer(app, client):
    register(client)
    b = order_body(app, [("idly", 1)])
    b["items"][0]["unit_price"] = 0.01
    b["customer_id"] = 999
    b["total"] = 1
    o = client.post("/api/orders", json=b).get_json()["order"]
    assert o["subtotal"] == 50.0 and o["customer_name"] == "Ajay Vishnu"


# ---------------------------------------------------------------------
# 16. Duplicate order prevention
# ---------------------------------------------------------------------
def test_idempotency_key_prevents_duplicate_orders(app, client):
    register(client)
    b = order_body(app, [("idly", 1)], idempotency_key="abc12345-key")
    r1 = client.post("/api/orders", json=b)
    r2 = client.post("/api/orders", json=b)
    assert r1.status_code == 201 and r2.status_code == 200
    assert r2.get_json()["duplicate"] is True
    assert r1.get_json()["order"]["order_number"] == r2.get_json()["order"]["order_number"]
    with app.app_context():
        assert Order.query.count() == 1


def test_idempotent_replay_works_for_qr_after_token_consumed(app, client):
    register(client)
    body, r = _start_qr(client, app, [("idly", 1)])
    token = r.get_json()["token"]
    _age(app, token, 11)
    body.update(demo_payment_token=token, idempotency_key="qr-key-12345")
    assert client.post("/api/orders", json=body).status_code == 201
    assert client.post("/api/orders", json=body).status_code == 200
    with app.app_context():
        assert Order.query.count() == 1


def test_idempotency_key_reuse_with_different_cart_rejected(app, client):
    register(client)
    client.post("/api/orders", json=order_body(app, [("idly", 1)], idempotency_key="same-key-123"))
    r = client.post("/api/orders", json=order_body(app, [("mutton-mandi", 1)], idempotency_key="same-key-123"))
    assert r.status_code == 409


# ---------------------------------------------------------------------
# 14 / 17. Order history, status, access control
# ---------------------------------------------------------------------
def test_history_and_status_retrieval(app, client):
    register(client)
    n = client.post("/api/orders", json=order_body(app, [("idly", 1)])).get_json()["order"]["order_number"]
    assert len(client.get("/api/orders").get_json()["orders"]) == 1
    cid = client.get("/api/me").get_json()["customer"]["id"]
    assert len(client.get(f"/api/customer/{cid}/orders").get_json()["orders"]) == 1
    assert client.get(f"/api/orders/{n}/status").get_json()["status"] == "PLACED"
    assert client.get(f"/api/orders/{n}").status_code == 200


def test_customers_cannot_see_each_others_orders(app, client):
    register(client)
    n = client.post("/api/orders", json=order_body(app, [("idly", 1)])).get_json()["order"]["order_number"]
    c2 = client.application.test_client()
    register(c2, mobile="9000000002", email="c@example.com")
    assert c2.get(f"/api/orders/{n}").status_code == 404
    assert c2.get(f"/api/orders/{n}/status").status_code == 404
    assert c2.get("/api/customer/1/orders").status_code == 403
    assert client.get("/api/orders").get_json()["orders"] != []
    assert c2.get("/api/orders").get_json()["orders"] == []


# ---------------------------------------------------------------------
# Staff status flow
# ---------------------------------------------------------------------
H = {"X-Staff-Key": "staff-test-key"}


def test_staff_status_flow_never_automatic(app, client):
    register(client)
    n = client.post("/api/orders", json=order_body(app, [("idly", 1)])).get_json()["order"]["order_number"]
    # an expired estimate must not change status
    with app.app_context():
        Order.query.first().est_ready_at = datetime.utcnow() - timedelta(hours=2)
        db.session.commit()
    assert client.get(f"/api/orders/{n}/status").get_json()["status"] == "PLACED"
    for s in ["CONFIRMED", "PREPARING", "READY", "SERVED"]:
        r = client.patch(f"/api/staff/orders/{n}/status", json={"status": s}, headers=H)
        assert r.status_code == 200 and r.get_json()["order"]["status"] == s
        assert client.get(f"/api/orders/{n}/status").get_json()["status"] == s
    assert client.patch(f"/api/staff/orders/{n}/status", json={"status": "CANCELLED"}, headers=H).status_code == 409


def test_staff_cannot_skip_steps_and_auth_required(app, client):
    register(client)
    n = client.post("/api/orders", json=order_body(app, [("idly", 1)])).get_json()["order"]["order_number"]
    assert client.patch(f"/api/staff/orders/{n}/status", json={"status": "SERVED"}, headers=H).status_code == 409
    assert client.patch(f"/api/staff/orders/{n}/status", json={"status": "CONFIRMED"}).status_code == 401
    assert client.patch(f"/api/staff/orders/{n}/status", json={"status": "CONFIRMED"}, headers={"X-Staff-Key": "bad"}).status_code == 401
    assert client.patch(f"/api/staff/orders/{n}/status", json={"status": "CANCELLED"}, headers=H).status_code == 200


def test_staff_disabled_without_key(app, client):
    app.config["STAFF_API_KEY"] = ""
    assert client.get("/api/staff/orders", headers=H).status_code == 403


def test_staff_marks_cash_paid(app, client):
    register(client)
    n = client.post("/api/orders", json=order_body(app, [("idly", 1)], "CASH")).get_json()["order"]["order_number"]
    r = client.patch(f"/api/staff/orders/{n}/payment", json={}, headers=H)
    assert r.get_json()["order"]["payment_status"] == "PAID"
    n2 = client.post("/api/orders", json=order_body(app, [("idly", 1)])).get_json()["order"]["order_number"]
    assert client.patch(f"/api/staff/orders/{n2}/payment", json={}, headers=H).status_code == 409


# ---------------------------------------------------------------------
# 15. Slack
# ---------------------------------------------------------------------
class _Resp:
    status_code = 200


def test_slack_message_content_and_no_secrets(app, client, monkeypatch):
    sent = []
    monkeypatch.setattr("services.slack_service.requests.post", lambda url, json=None, timeout=None: sent.append((url, json)) or _Resp())
    app.config["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/T/B/real"
    register(client, name="Ajay <Vishnu> & Co", password="supersecret9")
    r = client.post("/api/orders", json=order_body(app, [("chicken-biryani", 2), ("chicken-65", 1), ("filter-coffee", 2)]))
    assert r.status_code == 201
    assert len(sent) == 1
    text = sent[0][1]["text"]
    for needle in ["NEW ORDER – HOTEL LAZZY-KITCHEN", "Table:* 12", "Chicken Biryani x2 @ ₹220", "Chicken 65 x1 @ ₹180",
                   "Filter Coffee x2 @ ₹30", "Total:* ₹714", "DEMO CARD", "Payment Status:* PAID", "Status:* PLACED",
                   "Order Time:*", "25–35 Minutes", r.get_json()["order"]["order_number"]]:
        assert needle in text, needle
    assert "Ajay &lt;Vishnu&gt; &amp; Co" in text                         # escaped
    for secret in ["1234", "4321", "CVV", "PIN", "supersecret9", "scrypt", "pbkdf2"]:
        assert secret not in text, secret


def test_slack_cash_shows_pending_cash(app, client, monkeypatch):
    sent = []
    monkeypatch.setattr("services.slack_service.requests.post", lambda url, json=None, timeout=None: sent.append(json) or _Resp())
    app.config["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/T/B/real"
    register(client)
    client.post("/api/orders", json=order_body(app, [("idly", 1)], "CASH"))
    assert "PENDING_CASH" in sent[0]["text"] and "CASH" in sent[0]["text"]


def test_slack_failure_never_blocks_order(app, client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("slack down")
    monkeypatch.setattr("services.slack_service.requests.post", boom)
    app.config["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/T/B/real"
    register(client)
    assert client.post("/api/orders", json=order_body(app, [("idly", 1)])).status_code == 201


# ---------------------------------------------------------------------
# Sensitive data is never stored
# ---------------------------------------------------------------------
def test_no_card_data_anywhere_in_database(app, client):
    register(client)
    client.post("/api/orders", json=order_body(app, [("idly", 1)]))
    b = order_body(app, [("idly", 1)], "DEMO_QR")
    s = client.post("/api/payments/demo-qr/start", json={"items": b["items"]}).get_json()["token"]
    _age(app, s, 11)
    b["demo_payment_token"] = s
    client.post("/api/orders", json=b)
    with app.app_context():
        dump = []
        for table in db.metadata.sorted_tables:
            if table.name in ("menu_items", "customers"):
                continue
            for row in db.session.execute(table.select()).fetchall():
                dump.append(" ".join(str(v) for v in row))
        blob = " ".join(dump)
        assert "1234 4321" not in blob and "1234432156788765" not in blob
        sensitive = ("card", "pin", "cvv", "upi", "vpa")
        assert not [c.name for t in db.metadata.sorted_tables for c in t.columns
                    if any(w in c.name.lower() for w in sensitive)]

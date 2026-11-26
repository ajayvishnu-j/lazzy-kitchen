from datetime import datetime
from utils.db import db

ORDER_STATUSES = ("PLACED", "CONFIRMED", "PREPARING", "READY", "SERVED", "CANCELLED")
PAYMENT_METHODS = ("DEMO_CARD", "DEMO_QR", "CASH")
PAYMENT_STATUSES = ("PAID", "PENDING_CASH")

PAYMENT_METHOD_LABELS = {
    "DEMO_CARD": "Demo Card",
    "DEMO_QR": "Google Pay (Demo QR)",
    "CASH": "Cash at Counter",
}


def utc_iso(dt):
    """Timestamps are stored in UTC; expose them with an explicit Z so browsers convert correctly."""
    return dt.replace(tzinfo=None).isoformat() + "Z" if dt else None


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), nullable=False, unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    table_number = db.Column(db.String(10), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum(*ORDER_STATUSES), default="PLACED", nullable=False)
    payment_method = db.Column(db.Enum(*PAYMENT_METHODS), default="DEMO_CARD", nullable=False)
    payment_status = db.Column(db.Enum(*PAYMENT_STATUSES), default="PAID", nullable=False)
    est_prep_min_minutes = db.Column(db.Integer, nullable=False, default=15)
    est_prep_max_minutes = db.Column(db.Integer, nullable=False, default=25)
    est_ready_at = db.Column(db.TIMESTAMP, nullable=True)
    idempotency_key = db.Column(db.String(64), nullable=True)
    status_updated_at = db.Column(db.TIMESTAMP, nullable=True)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("customer_id", "idempotency_key", name="uq_orders_customer_idem"),)

    @property
    def estimated_preparation(self):
        return f"{self.est_prep_min_minutes}\u2013{self.est_prep_max_minutes} minutes"

    def to_dict(self, include_items=True):
        data = {
            "id": self.id,
            "order_number": self.order_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "table_number": self.table_number,
            "subtotal": float(self.subtotal),
            "tax": float(self.tax),
            "total": float(self.total),
            "status": self.status,
            "payment_method": self.payment_method,
            "payment_method_label": PAYMENT_METHOD_LABELS.get(self.payment_method, self.payment_method),
            "payment_status": self.payment_status,
            "est_prep_min_minutes": self.est_prep_min_minutes,
            "est_prep_max_minutes": self.est_prep_max_minutes,
            "estimated_preparation": self.estimated_preparation,
            "est_ready_at": utc_iso(self.est_ready_at),
            "created_at": utc_iso(self.created_at),
            "status_updated_at": utc_iso(self.status_updated_at),
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(8, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "menu_item_id": self.menu_item_id,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "total_price": float(self.total_price),
        }

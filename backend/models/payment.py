from datetime import datetime
from utils.db import db


class DemoPaymentSession(db.Model):
    """
    Server-side proof for the Google Pay *demo* QR flow.
    Holds a random token only — never card, PIN, CVV or UPI data.
    """
    __tablename__ = "demo_payment_sessions"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(36), nullable=False, unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    cart_hash = db.Column(db.String(64), nullable=False)
    started_at = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    consumed_at = db.Column(db.TIMESTAMP, nullable=True)

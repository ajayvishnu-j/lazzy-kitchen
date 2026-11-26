from datetime import datetime
from utils.db import db


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(15), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    table_number = db.Column(db.String(10), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    last_login_at = db.Column(db.TIMESTAMP, nullable=True)

    def to_dict(self):
        # password_hash is deliberately never serialised
        return {
            "id": self.id,
            "full_name": self.full_name,
            "mobile": self.mobile,
            "email": self.email,
            "table_number": self.table_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

from datetime import datetime
from utils.db import db

MAIN_CATEGORIES = ("FOOD", "SNACKS_BEVERAGES")


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(8, 2), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)      # legacy remote URL (unused by new UI)
    image_path = db.Column(db.String(255), nullable=True)     # local asset, e.g. assets/images/menu/idly.jpg
    main_category = db.Column(db.Enum(*MAIN_CATEGORIES), nullable=False, default="FOOD")
    category = db.Column(db.String(50), nullable=False)        # sub-group: "South Indian", "Pizza", ...
    flavour = db.Column(db.String(60), nullable=True)
    is_vegetarian = db.Column(db.Boolean, default=True)
    is_available = db.Column(db.Boolean, default=True)
    prep_time_min = db.Column(db.Integer, nullable=False, default=10)
    prep_time_max = db.Column(db.Integer, nullable=False, default=20)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "price": float(self.price),
            "image_path": self.image_path,
            "main_category": self.main_category,
            "category": self.category,
            "flavour": self.flavour,
            "is_vegetarian": bool(self.is_vegetarian),
            "is_available": bool(self.is_available),
            "prep_time_min": self.prep_time_min,
            "prep_time_max": self.prep_time_max,
        }


class RestaurantConfig(db.Model):
    __tablename__ = "restaurant_config"

    id = db.Column(db.Integer, primary_key=True, default=1)
    is_open = db.Column(db.Boolean, default=True)
    prep_time_min_minutes = db.Column(db.Integer, default=15)
    prep_time_max_minutes = db.Column(db.Integer, default=25)
    tax_percent = db.Column(db.Numeric(5, 2), default=5.00)
    prep_buffer_minutes = db.Column(db.Integer, nullable=False, default=5)

    def to_dict(self):
        return {
            "is_open": bool(self.is_open),
            "prep_time_min_minutes": self.prep_time_min_minutes,
            "prep_time_max_minutes": self.prep_time_max_minutes,
            "tax_percent": float(self.tax_percent),
            "prep_buffer_minutes": self.prep_buffer_minutes,
        }

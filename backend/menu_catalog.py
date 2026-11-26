"""
Single source of truth for the Hotel Lazzy-Kitchen menu.

Used by:
  * tools/build_menu_sql.py  -> generates database/migrations/002_menu_catalog.sql
  * tools/menu_images.py     -> knows which image file every item needs
  * tests                    -> seeds the SQLite test database

Prices here are only the INITIAL seed values. Once the rows are in MySQL the
database is the source of truth: change prices with a normal UPDATE and no
code change or redeploy is needed.

Prep times are (min, max) minutes for one order of the item.
"""

FOOD = "FOOD"
SNACKS = "SNACKS_BEVERAGES"

MAIN_CATEGORY_LABELS = {FOOD: "Food", SNACKS: "Snacks & Beverages"}


def _i(slug, name, main, group, price, veg, pmin, pmax, desc, flavour=None, legacy=()):
    return {
        "slug": slug, "name": name, "legacy_names": list(legacy),
        "main_category": main, "category": group, "flavour": flavour,
        "price": price, "is_vegetarian": 1 if veg else 0,
        "prep_time_min": pmin, "prep_time_max": pmax, "description": desc,
    }


SI, RICE = "South Indian", "Rice & Main Course"

CATALOG = [
    # ---------------- FOOD / South Indian ----------------
    _i("idly", "Idly", FOOD, SI, 50, True, 10, 15, "Soft steamed rice cakes served with chutney & sambar", legacy=["Idly"]),
    _i("plain-dosa", "Plain Dosa", FOOD, SI, 70, True, 10, 20, "Crispy golden rice-and-lentil crepe with chutney & sambar", legacy=["Dosa"]),
    _i("masala-dosa", "Masala Dosa", FOOD, SI, 90, True, 12, 20, "Crisp dosa stuffed with spiced potato masala"),
    _i("ghee-roast", "Ghee Roast", FOOD, SI, 100, True, 12, 20, "Paper-thin dosa roasted golden in pure ghee"),
    _i("onion-dosa", "Onion Dosa", FOOD, SI, 85, True, 10, 20, "Crisp dosa topped with caramelised onions"),
    _i("parotta", "Parotta", FOOD, SI, 60, True, 12, 20, "Layered flaky flatbread, perfect with kurma", legacy=["Parotta"]),
    _i("chapathi", "Chapathi", FOOD, SI, 60, True, 10, 15, "Soft whole-wheat flatbread served with kurma", legacy=["Chapathi"]),
    _i("poori", "Poori", FOOD, SI, 65, True, 10, 15, "Deep fried puffed wheat bread with potato masala", legacy=["Poori"]),
    _i("pongal", "Pongal", FOOD, SI, 75, True, 10, 15, "Comforting rice & moong dal dish tempered with ghee", legacy=["Pongal"]),
    _i("medu-vadai", "Medu Vadai", FOOD, SI, 35, True, 10, 15, "Crispy golden lentil doughnuts, soft inside", legacy=["Vadai"]),
    _i("special-sambar", "Special Sambar", FOOD, SI, 40, True, 10, 15, "Signature hotel-style lentil & vegetable stew", legacy=["Special Sambar"]),
    # ---------------- FOOD / Rice & Main Course ----------------
    _i("veg-biryani", "Veg Biryani", FOOD, RICE, 160, True, 20, 30, "Fragrant seeraga samba rice with vegetables and raita"),
    _i("chicken-biryani", "Chicken Biryani", FOOD, RICE, 220, False, 20, 30, "Dum-cooked biryani with tender chicken and raita"),
    _i("chicken-65", "Chicken 65", FOOD, RICE, 180, False, 15, 20, "Spicy deep-fried chicken, a South Indian classic"),
    _i("mutton-mandi", "Mutton Mandi", FOOD, RICE, 450, False, 30, 40, "Slow-cooked mutton on smoky spiced rice"),
    _i("veg-fried-rice", "Veg Fried Rice", FOOD, RICE, 140, True, 15, 20, "Wok-tossed rice with fresh vegetables"),
    _i("chicken-fried-rice", "Chicken Fried Rice", FOOD, RICE, 170, False, 15, 20, "Wok-tossed rice with chicken and spring onion"),
    _i("egg-fried-rice", "Egg Fried Rice", FOOD, RICE, 150, False, 15, 20, "Wok-tossed rice with scrambled egg"),
    _i("chicken-noodles", "Chicken Noodles", FOOD, RICE, 160, False, 15, 20, "Stir-fried noodles with chicken and vegetables"),
    _i("chicken-kothu-parotta", "Chicken Kothu Parotta", FOOD, RICE, 170, False, 15, 25, "Shredded parotta stir-fried with chicken, egg and salna"),
    _i("chicken-gravy", "Chicken Gravy", FOOD, RICE, 190, False, 15, 25, "Home-style chicken curry in a rich masala gravy"),
    _i("paneer-butter-masala", "Paneer Butter Masala", FOOD, RICE, 200, True, 15, 25, "Paneer cubes in a creamy tomato-butter gravy"),
    _i("egg-omelette", "Egg Omelette", FOOD, RICE, 40, False, 10, 15, "Fluffy omelette with onion and green chilli"),
    # ---------------- SNACKS & BEVERAGES ----------------
    _i("normal-tea", "Normal Tea", SNACKS, "Tea", 15, True, 5, 10, "Classic hot milk tea", flavour="Normal"),
    _i("ginger-tea", "Ginger Tea", SNACKS, "Tea", 20, True, 5, 10, "Milk tea brewed with fresh ginger", flavour="Ginger"),
    _i("black-tea", "Black Tea", SNACKS, "Tea", 15, True, 5, 10, "Strong tea without milk", flavour="Black"),
    _i("filter-coffee", "Filter Coffee", SNACKS, "Coffee", 30, True, 5, 10, "Traditional South Indian decoction coffee", flavour="Filter"),
    _i("cappuccino", "Cappuccino", SNACKS, "Coffee", 120, True, 5, 10, "Espresso with steamed milk and thick foam", flavour="Cappuccino"),
    _i("espresso", "Espresso", SNACKS, "Coffee", 90, True, 5, 10, "Bold single-shot Italian-style coffee", flavour="Espresso"),
    _i("latte", "Latte", SNACKS, "Coffee", 130, True, 5, 10, "Smooth espresso with silky steamed milk", flavour="Latte"),
    _i("mocha", "Mocha", SNACKS, "Coffee", 150, True, 5, 10, "Espresso, chocolate and steamed milk", flavour="Mocha"),
    _i("chocolate-donut", "Chocolate Donut", SNACKS, "Donuts", 60, True, 10, 15, "Soft ring donut glazed with rich chocolate", flavour="Chocolate"),
    _i("strawberry-donut", "Strawberry Donut", SNACKS, "Donuts", 70, True, 10, 15, "Soft ring donut with strawberry icing", flavour="Strawberry"),
    _i("glazed-donut", "Glazed Donut", SNACKS, "Donuts", 50, True, 10, 15, "Classic sugar-glazed ring donut", flavour="Glazed"),
    _i("margherita-pizza", "Margherita Pizza", SNACKS, "Pizza", 220, True, 15, 20, "Tomato sauce, mozzarella and fresh basil", flavour="Margherita"),
    _i("veg-loaded-pizza", "Veg Loaded Pizza", SNACKS, "Pizza", 260, True, 15, 20, "Loaded with capsicum, onion, corn and olives", flavour="Veg Loaded"),
    _i("chicken-pizza", "Chicken Pizza", SNACKS, "Pizza", 290, False, 15, 20, "Cheesy pizza topped with spiced chicken", flavour="Chicken"),
    _i("veg-burger", "Veg Burger", SNACKS, "Burger", 110, True, 10, 15, "Crispy veg patty with lettuce and mayo", flavour="Veg"),
    _i("cheese-burger", "Cheese Burger", SNACKS, "Burger", 130, True, 10, 15, "Veg patty with a melted cheese slice", flavour="Cheese"),
    _i("chicken-burger", "Chicken Burger", SNACKS, "Burger", 150, False, 10, 15, "Crispy chicken fillet with lettuce and mayo", flavour="Chicken"),
    _i("double-chicken-burger", "Double Chicken Burger", SNACKS, "Burger", 210, False, 10, 15, "Two crispy chicken fillets, double the bite", flavour="Double Chicken"),
    _i("classic-chicken-shawarma", "Classic Chicken Shawarma", SNACKS, "Shawarma", 120, False, 10, 15, "Grilled chicken, garlic sauce and pickles in a roll", flavour="Classic"),
    _i("spicy-chicken-shawarma", "Spicy Chicken Shawarma", SNACKS, "Shawarma", 130, False, 10, 15, "Chicken shawarma with fiery peri-masala", flavour="Spicy"),
    _i("french-fries", "French Fries", SNACKS, "Additional Snacks", 90, True, 10, 15, "Golden crispy salted potato fries"),
    _i("peri-peri-fries", "Peri Peri Fries", SNACKS, "Additional Snacks", 110, True, 10, 15, "Crispy fries dusted with peri peri seasoning"),
]

assert len({i["slug"] for i in CATALOG}) == len(CATALOG), "duplicate slug in catalog"

-- =====================================================================
-- Hotel Lazzy-Kitchen — Database Schema
-- =====================================================================
CREATE DATABASE IF NOT EXISTS lazzy_kitchen
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE lazzy_kitchen;

-- ---------------------------------------------------------------------
-- customers
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    full_name       VARCHAR(120)  NOT NULL,
    mobile          VARCHAR(15)   NOT NULL,
    email           VARCHAR(150)  NOT NULL,
    table_number    VARCHAR(10)   NOT NULL,
    password_hash   VARCHAR(255)  NOT NULL,
    created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_customers_email (email),
    UNIQUE KEY uq_customers_mobile (mobile),
    INDEX idx_customers_table (table_number)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- menu_items
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS menu_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100)   NOT NULL,
    description     VARCHAR(255)   NOT NULL,
    price           DECIMAL(8,2)   NOT NULL,
    image_url       VARCHAR(500)   NOT NULL,
    category        VARCHAR(50)    NOT NULL,
    is_vegetarian   TINYINT(1)     NOT NULL DEFAULT 1,
    is_available    TINYINT(1)     NOT NULL DEFAULT 1,
    created_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_menu_category (category),
    INDEX idx_menu_available (is_available)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- orders
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    order_number    VARCHAR(30)    NOT NULL,
    customer_id     INT            NOT NULL,
    customer_name   VARCHAR(120)   NOT NULL,
    table_number    VARCHAR(10)    NOT NULL,
    subtotal        DECIMAL(10,2)  NOT NULL,
    tax             DECIMAL(10,2)  NOT NULL,
    total           DECIMAL(10,2)  NOT NULL,
    status          ENUM('PLACED','CONFIRMED','PREPARING','READY','SERVED','CANCELLED')
                    NOT NULL DEFAULT 'PLACED',
    created_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_orders_number (order_number),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id)
        REFERENCES customers(id) ON DELETE CASCADE,
    INDEX idx_orders_status (status),
    INDEX idx_orders_created (created_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- order_items
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT            NOT NULL,
    menu_item_id    INT            NOT NULL,
    item_name       VARCHAR(100)   NOT NULL,
    quantity        INT            NOT NULL,
    unit_price      DECIMAL(8,2)   NOT NULL,
    total_price     DECIMAL(10,2)  NOT NULL,
    CONSTRAINT fk_order_items_order FOREIGN KEY (order_id)
        REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_order_items_menu FOREIGN KEY (menu_item_id)
        REFERENCES menu_items(id),
    INDEX idx_order_items_order (order_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- restaurant_config  (single-row config table: open/closed, prep time)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS restaurant_config (
    id                      INT PRIMARY KEY DEFAULT 1,
    is_open                 TINYINT(1) NOT NULL DEFAULT 1,
    prep_time_min_minutes   INT NOT NULL DEFAULT 15,
    prep_time_max_minutes   INT NOT NULL DEFAULT 25,
    tax_percent             DECIMAL(5,2) NOT NULL DEFAULT 5.00
) ENGINE=InnoDB;

INSERT INTO restaurant_config (id, is_open, prep_time_min_minutes, prep_time_max_minutes, tax_percent)
VALUES (1, 1, 15, 25, 5.00)
ON DUPLICATE KEY UPDATE id = id;

-- ---------------------------------------------------------------------
-- Seed menu data (Tamil Nadu South Indian tiffin items)
-- ---------------------------------------------------------------------
INSERT INTO menu_items (name, description, price, image_url, category, is_vegetarian, is_available) VALUES
('Idly',           'Soft steamed rice cakes served with chutney & sambar', 50.00, 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=600&q=80', 'Breakfast', 1, 1),
('Dosa',           'Crispy golden rice-and-lentil crepe',                  70.00, 'https://images.unsplash.com/photo-1630383249896-424e482df921?w=600&q=80', 'Breakfast', 1, 1),
('Parotta',        'Layered flaky flatbread, perfect with kurma',          60.00, 'https://images.unsplash.com/photo-1596797038530-2c107229654b?w=600&q=80', 'Breakfast', 1, 1),
('Chapathi',       'Soft whole-wheat flatbread',                           60.00, 'https://images.unsplash.com/photo-1574653853027-5382a3d23a15?w=600&q=80', 'Breakfast', 1, 1),
('Poori',          'Deep fried puffed wheat bread with potato masala',     65.00, 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=600&q=80', 'Breakfast', 1, 1),
('Pongal',         'Comforting rice & moong dal dish tempered with ghee',  75.00, 'https://images.unsplash.com/photo-1626132647523-66b3bf5e6c92?w=600&q=80', 'Breakfast', 1, 1),
('Vadai',          'Crispy golden lentil fritters',                       35.00, 'https://images.unsplash.com/photo-1626777553635-be0aa040c1b0?w=600&q=80', 'Breakfast', 1, 1),
('Special Sambar', 'Signature hotel-style lentil & vegetable stew',        40.00, 'https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=600&q=80', 'Special',   1, 1);

-- ===== Enhancements (same content as database/migrations/*.sql) =====
-- =====================================================================
-- Migration 001 - Schema enhancements (additive, idempotent)
--   * customers      : last_login_at
--   * menu_items     : slug, main_category, flavour, image_path, prep times, sort order
--   * orders         : payment method/status, estimated prep, idempotency key
--   * restaurant_config : prep_buffer_minutes
--   * demo_payment_sessions (new): server-side proof for the demo QR flow
--
-- Safe to run more than once. Does NOT drop, rename or delete any column,
-- table or row, so existing customers and orders are preserved.
--
-- Run against the existing database:
--   mysql -u <user> -p lazzy_kitchen < database/migrations/001_schema_enhancements.sql
-- =====================================================================

DROP PROCEDURE IF EXISTS lzk_add_column;
DROP PROCEDURE IF EXISTS lzk_add_index;

DELIMITER $$

CREATE PROCEDURE lzk_add_column(IN p_table VARCHAR(64), IN p_column VARCHAR(64), IN p_definition TEXT)
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = DATABASE() AND table_name = p_table AND column_name = p_column) THEN
        SET @lzk_sql = CONCAT('ALTER TABLE `', p_table, '` ADD COLUMN `', p_column, '` ', p_definition);
        PREPARE lzk_stmt FROM @lzk_sql;
        EXECUTE lzk_stmt;
        DEALLOCATE PREPARE lzk_stmt;
    END IF;
END$$

CREATE PROCEDURE lzk_add_index(IN p_table VARCHAR(64), IN p_index VARCHAR(64), IN p_definition TEXT)
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.statistics
                   WHERE table_schema = DATABASE() AND table_name = p_table AND index_name = p_index) THEN
        SET @lzk_sql = CONCAT('ALTER TABLE `', p_table, '` ADD ', p_definition);
        PREPARE lzk_stmt FROM @lzk_sql;
        EXECUTE lzk_stmt;
        DEALLOCATE PREPARE lzk_stmt;
    END IF;
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- customers  (password_hash, unique email/mobile already exist)
-- ---------------------------------------------------------------------
CALL lzk_add_column('customers', 'last_login_at', 'TIMESTAMP NULL DEFAULT NULL');

-- ---------------------------------------------------------------------
-- menu_items
-- ---------------------------------------------------------------------
CALL lzk_add_column('menu_items', 'slug',          'VARCHAR(80) NULL');
CALL lzk_add_column('menu_items', 'main_category', "ENUM('FOOD','SNACKS_BEVERAGES') NOT NULL DEFAULT 'FOOD'");
CALL lzk_add_column('menu_items', 'flavour',       'VARCHAR(60) NULL');
CALL lzk_add_column('menu_items', 'image_path',    'VARCHAR(255) NULL');
CALL lzk_add_column('menu_items', 'prep_time_min', 'SMALLINT UNSIGNED NOT NULL DEFAULT 10');
CALL lzk_add_column('menu_items', 'prep_time_max', 'SMALLINT UNSIGNED NOT NULL DEFAULT 20');
CALL lzk_add_column('menu_items', 'sort_order',    'INT NOT NULL DEFAULT 0');
CALL lzk_add_column('menu_items', 'updated_at',    'TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP');

-- Images are now local files (image_path). The legacy remote URL becomes optional.
ALTER TABLE menu_items MODIFY image_url VARCHAR(500) NULL;

CALL lzk_add_index('menu_items', 'uq_menu_slug',          'UNIQUE KEY uq_menu_slug (slug)');
CALL lzk_add_index('menu_items', 'idx_menu_main_category', 'INDEX idx_menu_main_category (main_category, is_available, sort_order)');

-- ---------------------------------------------------------------------
-- orders
-- ---------------------------------------------------------------------
CALL lzk_add_column('orders', 'payment_method',       "ENUM('DEMO_CARD','DEMO_QR','CASH') NOT NULL DEFAULT 'DEMO_CARD'");
CALL lzk_add_column('orders', 'payment_status',       "ENUM('PAID','PENDING_CASH') NOT NULL DEFAULT 'PAID'");
CALL lzk_add_column('orders', 'est_prep_min_minutes', 'SMALLINT UNSIGNED NOT NULL DEFAULT 15');
CALL lzk_add_column('orders', 'est_prep_max_minutes', 'SMALLINT UNSIGNED NOT NULL DEFAULT 25');
CALL lzk_add_column('orders', 'est_ready_at',         'TIMESTAMP NULL DEFAULT NULL');
CALL lzk_add_column('orders', 'idempotency_key',      'VARCHAR(64) NULL');
CALL lzk_add_column('orders', 'status_updated_at',    'TIMESTAMP NULL DEFAULT NULL');

CALL lzk_add_index('orders', 'uq_orders_customer_idem', 'UNIQUE KEY uq_orders_customer_idem (customer_id, idempotency_key)');
CALL lzk_add_index('orders', 'idx_orders_customer',     'INDEX idx_orders_customer (customer_id, created_at)');
CALL lzk_add_index('orders', 'idx_orders_payment',      'INDEX idx_orders_payment (payment_status)');

-- ---------------------------------------------------------------------
-- restaurant_config
-- ---------------------------------------------------------------------
CALL lzk_add_column('restaurant_config', 'prep_buffer_minutes', 'SMALLINT UNSIGNED NOT NULL DEFAULT 5');

-- ---------------------------------------------------------------------
-- demo_payment_sessions
-- Server-side record for the Google Pay *demo* QR flow. It proves that the
-- customer really waited for the simulated confirmation before an order is
-- created. It holds NO card, PIN, CVV or UPI data - only a random token.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS demo_payment_sessions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    token         CHAR(36)       NOT NULL,
    customer_id   INT            NOT NULL,
    amount        DECIMAL(10,2)  NOT NULL,
    cart_hash     CHAR(64)       NOT NULL,
    started_at    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    consumed_at   TIMESTAMP      NULL DEFAULT NULL,
    UNIQUE KEY uq_demo_pay_token (token),
    INDEX idx_demo_pay_customer (customer_id),
    CONSTRAINT fk_demo_pay_customer FOREIGN KEY (customer_id)
        REFERENCES customers(id) ON DELETE CASCADE
) ENGINE=InnoDB;

DROP PROCEDURE IF EXISTS lzk_add_column;
DROP PROCEDURE IF EXISTS lzk_add_index;

-- =====================================================================
-- Migration 002 - Menu catalogue (FOOD / SNACKS & BEVERAGES)
-- GENERATED by tools/build_menu_sql.py from backend/menu_catalog.py
-- Idempotent. Never overwrites price or is_available of existing rows.
-- Requires migration 001.
-- =====================================================================

-- Idly
UPDATE menu_items SET slug='idly', name='Idly', description='Soft steamed rice cakes served with chutney & sambar', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/idly.jpg', prep_time_min=10, prep_time_max=15, sort_order=10 WHERE slug IS NULL AND name IN ('Idly', 'Idly') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'idly', 'Idly', 'Soft steamed rice cakes served with chutney & sambar', 50.00, NULL, 'assets/images/menu/idly.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 10, 15, 10
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='idly');

-- Plain Dosa
UPDATE menu_items SET slug='plain-dosa', name='Plain Dosa', description='Crispy golden rice-and-lentil crepe with chutney & sambar', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/plain-dosa.jpg', prep_time_min=10, prep_time_max=20, sort_order=20 WHERE slug IS NULL AND name IN ('Dosa', 'Plain Dosa') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'plain-dosa', 'Plain Dosa', 'Crispy golden rice-and-lentil crepe with chutney & sambar', 70.00, NULL, 'assets/images/menu/plain-dosa.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 10, 20, 20
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='plain-dosa');

-- Masala Dosa
UPDATE menu_items SET slug='masala-dosa', name='Masala Dosa', description='Crisp dosa stuffed with spiced potato masala', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/masala-dosa.jpg', prep_time_min=12, prep_time_max=20, sort_order=30 WHERE slug IS NULL AND name IN ('Masala Dosa') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'masala-dosa', 'Masala Dosa', 'Crisp dosa stuffed with spiced potato masala', 90.00, NULL, 'assets/images/menu/masala-dosa.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 12, 20, 30
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='masala-dosa');

-- Ghee Roast
UPDATE menu_items SET slug='ghee-roast', name='Ghee Roast', description='Paper-thin dosa roasted golden in pure ghee', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/ghee-roast.jpg', prep_time_min=12, prep_time_max=20, sort_order=40 WHERE slug IS NULL AND name IN ('Ghee Roast') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'ghee-roast', 'Ghee Roast', 'Paper-thin dosa roasted golden in pure ghee', 100.00, NULL, 'assets/images/menu/ghee-roast.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 12, 20, 40
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='ghee-roast');

-- Onion Dosa
UPDATE menu_items SET slug='onion-dosa', name='Onion Dosa', description='Crisp dosa topped with caramelised onions', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/onion-dosa.jpg', prep_time_min=10, prep_time_max=20, sort_order=50 WHERE slug IS NULL AND name IN ('Onion Dosa') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'onion-dosa', 'Onion Dosa', 'Crisp dosa topped with caramelised onions', 85.00, NULL, 'assets/images/menu/onion-dosa.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 10, 20, 50
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='onion-dosa');

-- Parotta
UPDATE menu_items SET slug='parotta', name='Parotta', description='Layered flaky flatbread, perfect with kurma', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/parotta.jpg', prep_time_min=12, prep_time_max=20, sort_order=60 WHERE slug IS NULL AND name IN ('Parotta', 'Parotta') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'parotta', 'Parotta', 'Layered flaky flatbread, perfect with kurma', 60.00, NULL, 'assets/images/menu/parotta.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 12, 20, 60
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='parotta');

-- Chapathi
UPDATE menu_items SET slug='chapathi', name='Chapathi', description='Soft whole-wheat flatbread served with kurma', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/chapathi.jpg', prep_time_min=10, prep_time_max=15, sort_order=70 WHERE slug IS NULL AND name IN ('Chapathi', 'Chapathi') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chapathi', 'Chapathi', 'Soft whole-wheat flatbread served with kurma', 60.00, NULL, 'assets/images/menu/chapathi.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 10, 15, 70
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chapathi');

-- Poori
UPDATE menu_items SET slug='poori', name='Poori', description='Deep fried puffed wheat bread with potato masala', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/poori.jpg', prep_time_min=10, prep_time_max=15, sort_order=80 WHERE slug IS NULL AND name IN ('Poori', 'Poori') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'poori', 'Poori', 'Deep fried puffed wheat bread with potato masala', 65.00, NULL, 'assets/images/menu/poori.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 10, 15, 80
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='poori');

-- Pongal
UPDATE menu_items SET slug='pongal', name='Pongal', description='Comforting rice & moong dal dish tempered with ghee', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/pongal.jpg', prep_time_min=10, prep_time_max=15, sort_order=90 WHERE slug IS NULL AND name IN ('Pongal', 'Pongal') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'pongal', 'Pongal', 'Comforting rice & moong dal dish tempered with ghee', 75.00, NULL, 'assets/images/menu/pongal.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 10, 15, 90
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='pongal');

-- Medu Vadai
UPDATE menu_items SET slug='medu-vadai', name='Medu Vadai', description='Crispy golden lentil doughnuts, soft inside', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/medu-vadai.jpg', prep_time_min=10, prep_time_max=15, sort_order=100 WHERE slug IS NULL AND name IN ('Vadai', 'Medu Vadai') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'medu-vadai', 'Medu Vadai', 'Crispy golden lentil doughnuts, soft inside', 35.00, NULL, 'assets/images/menu/medu-vadai.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 10, 15, 100
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='medu-vadai');

-- Special Sambar
UPDATE menu_items SET slug='special-sambar', name='Special Sambar', description='Signature hotel-style lentil & vegetable stew', main_category='FOOD', category='South Indian', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/special-sambar.jpg', prep_time_min=10, prep_time_max=15, sort_order=110 WHERE slug IS NULL AND name IN ('Special Sambar', 'Special Sambar') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'special-sambar', 'Special Sambar', 'Signature hotel-style lentil & vegetable stew', 40.00, NULL, 'assets/images/menu/special-sambar.jpg', 'South Indian', 'FOOD', NULL, 1, 1, 10, 15, 110
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='special-sambar');

-- Veg Biryani
UPDATE menu_items SET slug='veg-biryani', name='Veg Biryani', description='Fragrant seeraga samba rice with vegetables and raita', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/veg-biryani.jpg', prep_time_min=20, prep_time_max=30, sort_order=120 WHERE slug IS NULL AND name IN ('Veg Biryani') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'veg-biryani', 'Veg Biryani', 'Fragrant seeraga samba rice with vegetables and raita', 160.00, NULL, 'assets/images/menu/veg-biryani.jpg', 'Rice & Main Course', 'FOOD', NULL, 1, 1, 20, 30, 120
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='veg-biryani');

-- Chicken Biryani
UPDATE menu_items SET slug='chicken-biryani', name='Chicken Biryani', description='Dum-cooked biryani with tender chicken and raita', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=0, image_path='assets/images/menu/chicken-biryani.jpg', prep_time_min=20, prep_time_max=30, sort_order=130 WHERE slug IS NULL AND name IN ('Chicken Biryani') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chicken-biryani', 'Chicken Biryani', 'Dum-cooked biryani with tender chicken and raita', 220.00, NULL, 'assets/images/menu/chicken-biryani.jpg', 'Rice & Main Course', 'FOOD', NULL, 0, 1, 20, 30, 130
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chicken-biryani');

-- Chicken 65
UPDATE menu_items SET slug='chicken-65', name='Chicken 65', description='Spicy deep-fried chicken, a South Indian classic', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=0, image_path='assets/images/menu/chicken-65.jpg', prep_time_min=15, prep_time_max=20, sort_order=140 WHERE slug IS NULL AND name IN ('Chicken 65') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chicken-65', 'Chicken 65', 'Spicy deep-fried chicken, a South Indian classic', 180.00, NULL, 'assets/images/menu/chicken-65.jpg', 'Rice & Main Course', 'FOOD', NULL, 0, 1, 15, 20, 140
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chicken-65');

-- Mutton Mandi
UPDATE menu_items SET slug='mutton-mandi', name='Mutton Mandi', description='Slow-cooked mutton on smoky spiced rice', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=0, image_path='assets/images/menu/mutton-mandi.jpg', prep_time_min=30, prep_time_max=40, sort_order=150 WHERE slug IS NULL AND name IN ('Mutton Mandi') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'mutton-mandi', 'Mutton Mandi', 'Slow-cooked mutton on smoky spiced rice', 450.00, NULL, 'assets/images/menu/mutton-mandi.jpg', 'Rice & Main Course', 'FOOD', NULL, 0, 1, 30, 40, 150
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='mutton-mandi');

-- Veg Fried Rice
UPDATE menu_items SET slug='veg-fried-rice', name='Veg Fried Rice', description='Wok-tossed rice with fresh vegetables', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/veg-fried-rice.jpg', prep_time_min=15, prep_time_max=20, sort_order=160 WHERE slug IS NULL AND name IN ('Veg Fried Rice') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'veg-fried-rice', 'Veg Fried Rice', 'Wok-tossed rice with fresh vegetables', 140.00, NULL, 'assets/images/menu/veg-fried-rice.jpg', 'Rice & Main Course', 'FOOD', NULL, 1, 1, 15, 20, 160
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='veg-fried-rice');

-- Chicken Fried Rice
UPDATE menu_items SET slug='chicken-fried-rice', name='Chicken Fried Rice', description='Wok-tossed rice with chicken and spring onion', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=0, image_path='assets/images/menu/chicken-fried-rice.jpg', prep_time_min=15, prep_time_max=20, sort_order=170 WHERE slug IS NULL AND name IN ('Chicken Fried Rice') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chicken-fried-rice', 'Chicken Fried Rice', 'Wok-tossed rice with chicken and spring onion', 170.00, NULL, 'assets/images/menu/chicken-fried-rice.jpg', 'Rice & Main Course', 'FOOD', NULL, 0, 1, 15, 20, 170
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chicken-fried-rice');

-- Egg Fried Rice
UPDATE menu_items SET slug='egg-fried-rice', name='Egg Fried Rice', description='Wok-tossed rice with scrambled egg', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=0, image_path='assets/images/menu/egg-fried-rice.jpg', prep_time_min=15, prep_time_max=20, sort_order=180 WHERE slug IS NULL AND name IN ('Egg Fried Rice') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'egg-fried-rice', 'Egg Fried Rice', 'Wok-tossed rice with scrambled egg', 150.00, NULL, 'assets/images/menu/egg-fried-rice.jpg', 'Rice & Main Course', 'FOOD', NULL, 0, 1, 15, 20, 180
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='egg-fried-rice');

-- Chicken Noodles
UPDATE menu_items SET slug='chicken-noodles', name='Chicken Noodles', description='Stir-fried noodles with chicken and vegetables', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=0, image_path='assets/images/menu/chicken-noodles.jpg', prep_time_min=15, prep_time_max=20, sort_order=190 WHERE slug IS NULL AND name IN ('Chicken Noodles') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chicken-noodles', 'Chicken Noodles', 'Stir-fried noodles with chicken and vegetables', 160.00, NULL, 'assets/images/menu/chicken-noodles.jpg', 'Rice & Main Course', 'FOOD', NULL, 0, 1, 15, 20, 190
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chicken-noodles');

-- Chicken Kothu Parotta
UPDATE menu_items SET slug='chicken-kothu-parotta', name='Chicken Kothu Parotta', description='Shredded parotta stir-fried with chicken, egg and salna', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=0, image_path='assets/images/menu/chicken-kothu-parotta.jpg', prep_time_min=15, prep_time_max=25, sort_order=200 WHERE slug IS NULL AND name IN ('Chicken Kothu Parotta') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chicken-kothu-parotta', 'Chicken Kothu Parotta', 'Shredded parotta stir-fried with chicken, egg and salna', 170.00, NULL, 'assets/images/menu/chicken-kothu-parotta.jpg', 'Rice & Main Course', 'FOOD', NULL, 0, 1, 15, 25, 200
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chicken-kothu-parotta');

-- Chicken Gravy
UPDATE menu_items SET slug='chicken-gravy', name='Chicken Gravy', description='Home-style chicken curry in a rich masala gravy', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=0, image_path='assets/images/menu/chicken-gravy.jpg', prep_time_min=15, prep_time_max=25, sort_order=210 WHERE slug IS NULL AND name IN ('Chicken Gravy') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chicken-gravy', 'Chicken Gravy', 'Home-style chicken curry in a rich masala gravy', 190.00, NULL, 'assets/images/menu/chicken-gravy.jpg', 'Rice & Main Course', 'FOOD', NULL, 0, 1, 15, 25, 210
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chicken-gravy');

-- Paneer Butter Masala
UPDATE menu_items SET slug='paneer-butter-masala', name='Paneer Butter Masala', description='Paneer cubes in a creamy tomato-butter gravy', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/paneer-butter-masala.jpg', prep_time_min=15, prep_time_max=25, sort_order=220 WHERE slug IS NULL AND name IN ('Paneer Butter Masala') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'paneer-butter-masala', 'Paneer Butter Masala', 'Paneer cubes in a creamy tomato-butter gravy', 200.00, NULL, 'assets/images/menu/paneer-butter-masala.jpg', 'Rice & Main Course', 'FOOD', NULL, 1, 1, 15, 25, 220
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='paneer-butter-masala');

-- Egg Omelette
UPDATE menu_items SET slug='egg-omelette', name='Egg Omelette', description='Fluffy omelette with onion and green chilli', main_category='FOOD', category='Rice & Main Course', flavour=NULL, is_vegetarian=0, image_path='assets/images/menu/egg-omelette.jpg', prep_time_min=10, prep_time_max=15, sort_order=230 WHERE slug IS NULL AND name IN ('Egg Omelette') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'egg-omelette', 'Egg Omelette', 'Fluffy omelette with onion and green chilli', 40.00, NULL, 'assets/images/menu/egg-omelette.jpg', 'Rice & Main Course', 'FOOD', NULL, 0, 1, 10, 15, 230
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='egg-omelette');

-- Normal Tea
UPDATE menu_items SET slug='normal-tea', name='Normal Tea', description='Classic hot milk tea', main_category='SNACKS_BEVERAGES', category='Tea', flavour='Normal', is_vegetarian=1, image_path='assets/images/menu/normal-tea.jpg', prep_time_min=5, prep_time_max=10, sort_order=240 WHERE slug IS NULL AND name IN ('Normal Tea') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'normal-tea', 'Normal Tea', 'Classic hot milk tea', 15.00, NULL, 'assets/images/menu/normal-tea.jpg', 'Tea', 'SNACKS_BEVERAGES', 'Normal', 1, 1, 5, 10, 240
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='normal-tea');

-- Ginger Tea
UPDATE menu_items SET slug='ginger-tea', name='Ginger Tea', description='Milk tea brewed with fresh ginger', main_category='SNACKS_BEVERAGES', category='Tea', flavour='Ginger', is_vegetarian=1, image_path='assets/images/menu/ginger-tea.jpg', prep_time_min=5, prep_time_max=10, sort_order=250 WHERE slug IS NULL AND name IN ('Ginger Tea') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'ginger-tea', 'Ginger Tea', 'Milk tea brewed with fresh ginger', 20.00, NULL, 'assets/images/menu/ginger-tea.jpg', 'Tea', 'SNACKS_BEVERAGES', 'Ginger', 1, 1, 5, 10, 250
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='ginger-tea');

-- Black Tea
UPDATE menu_items SET slug='black-tea', name='Black Tea', description='Strong tea without milk', main_category='SNACKS_BEVERAGES', category='Tea', flavour='Black', is_vegetarian=1, image_path='assets/images/menu/black-tea.jpg', prep_time_min=5, prep_time_max=10, sort_order=260 WHERE slug IS NULL AND name IN ('Black Tea') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'black-tea', 'Black Tea', 'Strong tea without milk', 15.00, NULL, 'assets/images/menu/black-tea.jpg', 'Tea', 'SNACKS_BEVERAGES', 'Black', 1, 1, 5, 10, 260
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='black-tea');

-- Filter Coffee
UPDATE menu_items SET slug='filter-coffee', name='Filter Coffee', description='Traditional South Indian decoction coffee', main_category='SNACKS_BEVERAGES', category='Coffee', flavour='Filter', is_vegetarian=1, image_path='assets/images/menu/filter-coffee.jpg', prep_time_min=5, prep_time_max=10, sort_order=270 WHERE slug IS NULL AND name IN ('Filter Coffee') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'filter-coffee', 'Filter Coffee', 'Traditional South Indian decoction coffee', 30.00, NULL, 'assets/images/menu/filter-coffee.jpg', 'Coffee', 'SNACKS_BEVERAGES', 'Filter', 1, 1, 5, 10, 270
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='filter-coffee');

-- Cappuccino
UPDATE menu_items SET slug='cappuccino', name='Cappuccino', description='Espresso with steamed milk and thick foam', main_category='SNACKS_BEVERAGES', category='Coffee', flavour='Cappuccino', is_vegetarian=1, image_path='assets/images/menu/cappuccino.jpg', prep_time_min=5, prep_time_max=10, sort_order=280 WHERE slug IS NULL AND name IN ('Cappuccino') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'cappuccino', 'Cappuccino', 'Espresso with steamed milk and thick foam', 120.00, NULL, 'assets/images/menu/cappuccino.jpg', 'Coffee', 'SNACKS_BEVERAGES', 'Cappuccino', 1, 1, 5, 10, 280
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='cappuccino');

-- Espresso
UPDATE menu_items SET slug='espresso', name='Espresso', description='Bold single-shot Italian-style coffee', main_category='SNACKS_BEVERAGES', category='Coffee', flavour='Espresso', is_vegetarian=1, image_path='assets/images/menu/espresso.jpg', prep_time_min=5, prep_time_max=10, sort_order=290 WHERE slug IS NULL AND name IN ('Espresso') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'espresso', 'Espresso', 'Bold single-shot Italian-style coffee', 90.00, NULL, 'assets/images/menu/espresso.jpg', 'Coffee', 'SNACKS_BEVERAGES', 'Espresso', 1, 1, 5, 10, 290
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='espresso');

-- Latte
UPDATE menu_items SET slug='latte', name='Latte', description='Smooth espresso with silky steamed milk', main_category='SNACKS_BEVERAGES', category='Coffee', flavour='Latte', is_vegetarian=1, image_path='assets/images/menu/latte.jpg', prep_time_min=5, prep_time_max=10, sort_order=300 WHERE slug IS NULL AND name IN ('Latte') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'latte', 'Latte', 'Smooth espresso with silky steamed milk', 130.00, NULL, 'assets/images/menu/latte.jpg', 'Coffee', 'SNACKS_BEVERAGES', 'Latte', 1, 1, 5, 10, 300
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='latte');

-- Mocha
UPDATE menu_items SET slug='mocha', name='Mocha', description='Espresso, chocolate and steamed milk', main_category='SNACKS_BEVERAGES', category='Coffee', flavour='Mocha', is_vegetarian=1, image_path='assets/images/menu/mocha.jpg', prep_time_min=5, prep_time_max=10, sort_order=310 WHERE slug IS NULL AND name IN ('Mocha') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'mocha', 'Mocha', 'Espresso, chocolate and steamed milk', 150.00, NULL, 'assets/images/menu/mocha.jpg', 'Coffee', 'SNACKS_BEVERAGES', 'Mocha', 1, 1, 5, 10, 310
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='mocha');

-- Chocolate Donut
UPDATE menu_items SET slug='chocolate-donut', name='Chocolate Donut', description='Soft ring donut glazed with rich chocolate', main_category='SNACKS_BEVERAGES', category='Donuts', flavour='Chocolate', is_vegetarian=1, image_path='assets/images/menu/chocolate-donut.jpg', prep_time_min=10, prep_time_max=15, sort_order=320 WHERE slug IS NULL AND name IN ('Chocolate Donut') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chocolate-donut', 'Chocolate Donut', 'Soft ring donut glazed with rich chocolate', 60.00, NULL, 'assets/images/menu/chocolate-donut.jpg', 'Donuts', 'SNACKS_BEVERAGES', 'Chocolate', 1, 1, 10, 15, 320
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chocolate-donut');

-- Strawberry Donut
UPDATE menu_items SET slug='strawberry-donut', name='Strawberry Donut', description='Soft ring donut with strawberry icing', main_category='SNACKS_BEVERAGES', category='Donuts', flavour='Strawberry', is_vegetarian=1, image_path='assets/images/menu/strawberry-donut.jpg', prep_time_min=10, prep_time_max=15, sort_order=330 WHERE slug IS NULL AND name IN ('Strawberry Donut') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'strawberry-donut', 'Strawberry Donut', 'Soft ring donut with strawberry icing', 70.00, NULL, 'assets/images/menu/strawberry-donut.jpg', 'Donuts', 'SNACKS_BEVERAGES', 'Strawberry', 1, 1, 10, 15, 330
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='strawberry-donut');

-- Glazed Donut
UPDATE menu_items SET slug='glazed-donut', name='Glazed Donut', description='Classic sugar-glazed ring donut', main_category='SNACKS_BEVERAGES', category='Donuts', flavour='Glazed', is_vegetarian=1, image_path='assets/images/menu/glazed-donut.jpg', prep_time_min=10, prep_time_max=15, sort_order=340 WHERE slug IS NULL AND name IN ('Glazed Donut') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'glazed-donut', 'Glazed Donut', 'Classic sugar-glazed ring donut', 50.00, NULL, 'assets/images/menu/glazed-donut.jpg', 'Donuts', 'SNACKS_BEVERAGES', 'Glazed', 1, 1, 10, 15, 340
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='glazed-donut');

-- Margherita Pizza
UPDATE menu_items SET slug='margherita-pizza', name='Margherita Pizza', description='Tomato sauce, mozzarella and fresh basil', main_category='SNACKS_BEVERAGES', category='Pizza', flavour='Margherita', is_vegetarian=1, image_path='assets/images/menu/margherita-pizza.jpg', prep_time_min=15, prep_time_max=20, sort_order=350 WHERE slug IS NULL AND name IN ('Margherita Pizza') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'margherita-pizza', 'Margherita Pizza', 'Tomato sauce, mozzarella and fresh basil', 220.00, NULL, 'assets/images/menu/margherita-pizza.jpg', 'Pizza', 'SNACKS_BEVERAGES', 'Margherita', 1, 1, 15, 20, 350
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='margherita-pizza');

-- Veg Loaded Pizza
UPDATE menu_items SET slug='veg-loaded-pizza', name='Veg Loaded Pizza', description='Loaded with capsicum, onion, corn and olives', main_category='SNACKS_BEVERAGES', category='Pizza', flavour='Veg Loaded', is_vegetarian=1, image_path='assets/images/menu/veg-loaded-pizza.jpg', prep_time_min=15, prep_time_max=20, sort_order=360 WHERE slug IS NULL AND name IN ('Veg Loaded Pizza') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'veg-loaded-pizza', 'Veg Loaded Pizza', 'Loaded with capsicum, onion, corn and olives', 260.00, NULL, 'assets/images/menu/veg-loaded-pizza.jpg', 'Pizza', 'SNACKS_BEVERAGES', 'Veg Loaded', 1, 1, 15, 20, 360
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='veg-loaded-pizza');

-- Chicken Pizza
UPDATE menu_items SET slug='chicken-pizza', name='Chicken Pizza', description='Cheesy pizza topped with spiced chicken', main_category='SNACKS_BEVERAGES', category='Pizza', flavour='Chicken', is_vegetarian=0, image_path='assets/images/menu/chicken-pizza.jpg', prep_time_min=15, prep_time_max=20, sort_order=370 WHERE slug IS NULL AND name IN ('Chicken Pizza') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chicken-pizza', 'Chicken Pizza', 'Cheesy pizza topped with spiced chicken', 290.00, NULL, 'assets/images/menu/chicken-pizza.jpg', 'Pizza', 'SNACKS_BEVERAGES', 'Chicken', 0, 1, 15, 20, 370
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chicken-pizza');

-- Veg Burger
UPDATE menu_items SET slug='veg-burger', name='Veg Burger', description='Crispy veg patty with lettuce and mayo', main_category='SNACKS_BEVERAGES', category='Burger', flavour='Veg', is_vegetarian=1, image_path='assets/images/menu/veg-burger.jpg', prep_time_min=10, prep_time_max=15, sort_order=380 WHERE slug IS NULL AND name IN ('Veg Burger') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'veg-burger', 'Veg Burger', 'Crispy veg patty with lettuce and mayo', 110.00, NULL, 'assets/images/menu/veg-burger.jpg', 'Burger', 'SNACKS_BEVERAGES', 'Veg', 1, 1, 10, 15, 380
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='veg-burger');

-- Cheese Burger
UPDATE menu_items SET slug='cheese-burger', name='Cheese Burger', description='Veg patty with a melted cheese slice', main_category='SNACKS_BEVERAGES', category='Burger', flavour='Cheese', is_vegetarian=1, image_path='assets/images/menu/cheese-burger.jpg', prep_time_min=10, prep_time_max=15, sort_order=390 WHERE slug IS NULL AND name IN ('Cheese Burger') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'cheese-burger', 'Cheese Burger', 'Veg patty with a melted cheese slice', 130.00, NULL, 'assets/images/menu/cheese-burger.jpg', 'Burger', 'SNACKS_BEVERAGES', 'Cheese', 1, 1, 10, 15, 390
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='cheese-burger');

-- Chicken Burger
UPDATE menu_items SET slug='chicken-burger', name='Chicken Burger', description='Crispy chicken fillet with lettuce and mayo', main_category='SNACKS_BEVERAGES', category='Burger', flavour='Chicken', is_vegetarian=0, image_path='assets/images/menu/chicken-burger.jpg', prep_time_min=10, prep_time_max=15, sort_order=400 WHERE slug IS NULL AND name IN ('Chicken Burger') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'chicken-burger', 'Chicken Burger', 'Crispy chicken fillet with lettuce and mayo', 150.00, NULL, 'assets/images/menu/chicken-burger.jpg', 'Burger', 'SNACKS_BEVERAGES', 'Chicken', 0, 1, 10, 15, 400
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='chicken-burger');

-- Double Chicken Burger
UPDATE menu_items SET slug='double-chicken-burger', name='Double Chicken Burger', description='Two crispy chicken fillets, double the bite', main_category='SNACKS_BEVERAGES', category='Burger', flavour='Double Chicken', is_vegetarian=0, image_path='assets/images/menu/double-chicken-burger.jpg', prep_time_min=10, prep_time_max=15, sort_order=410 WHERE slug IS NULL AND name IN ('Double Chicken Burger') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'double-chicken-burger', 'Double Chicken Burger', 'Two crispy chicken fillets, double the bite', 210.00, NULL, 'assets/images/menu/double-chicken-burger.jpg', 'Burger', 'SNACKS_BEVERAGES', 'Double Chicken', 0, 1, 10, 15, 410
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='double-chicken-burger');

-- Classic Chicken Shawarma
UPDATE menu_items SET slug='classic-chicken-shawarma', name='Classic Chicken Shawarma', description='Grilled chicken, garlic sauce and pickles in a roll', main_category='SNACKS_BEVERAGES', category='Shawarma', flavour='Classic', is_vegetarian=0, image_path='assets/images/menu/classic-chicken-shawarma.jpg', prep_time_min=10, prep_time_max=15, sort_order=420 WHERE slug IS NULL AND name IN ('Classic Chicken Shawarma') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'classic-chicken-shawarma', 'Classic Chicken Shawarma', 'Grilled chicken, garlic sauce and pickles in a roll', 120.00, NULL, 'assets/images/menu/classic-chicken-shawarma.jpg', 'Shawarma', 'SNACKS_BEVERAGES', 'Classic', 0, 1, 10, 15, 420
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='classic-chicken-shawarma');

-- Spicy Chicken Shawarma
UPDATE menu_items SET slug='spicy-chicken-shawarma', name='Spicy Chicken Shawarma', description='Chicken shawarma with fiery peri-masala', main_category='SNACKS_BEVERAGES', category='Shawarma', flavour='Spicy', is_vegetarian=0, image_path='assets/images/menu/spicy-chicken-shawarma.jpg', prep_time_min=10, prep_time_max=15, sort_order=430 WHERE slug IS NULL AND name IN ('Spicy Chicken Shawarma') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'spicy-chicken-shawarma', 'Spicy Chicken Shawarma', 'Chicken shawarma with fiery peri-masala', 130.00, NULL, 'assets/images/menu/spicy-chicken-shawarma.jpg', 'Shawarma', 'SNACKS_BEVERAGES', 'Spicy', 0, 1, 10, 15, 430
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='spicy-chicken-shawarma');

-- French Fries
UPDATE menu_items SET slug='french-fries', name='French Fries', description='Golden crispy salted potato fries', main_category='SNACKS_BEVERAGES', category='Additional Snacks', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/french-fries.jpg', prep_time_min=10, prep_time_max=15, sort_order=440 WHERE slug IS NULL AND name IN ('French Fries') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'french-fries', 'French Fries', 'Golden crispy salted potato fries', 90.00, NULL, 'assets/images/menu/french-fries.jpg', 'Additional Snacks', 'SNACKS_BEVERAGES', NULL, 1, 1, 10, 15, 440
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='french-fries');

-- Peri Peri Fries
UPDATE menu_items SET slug='peri-peri-fries', name='Peri Peri Fries', description='Crispy fries dusted with peri peri seasoning', main_category='SNACKS_BEVERAGES', category='Additional Snacks', flavour=NULL, is_vegetarian=1, image_path='assets/images/menu/peri-peri-fries.jpg', prep_time_min=10, prep_time_max=15, sort_order=450 WHERE slug IS NULL AND name IN ('Peri Peri Fries') ORDER BY id LIMIT 1;
INSERT INTO menu_items (slug, name, description, price, image_url, image_path, category, main_category, flavour, is_vegetarian, is_available, prep_time_min, prep_time_max, sort_order)
SELECT 'peri-peri-fries', 'Peri Peri Fries', 'Crispy fries dusted with peri peri seasoning', 110.00, NULL, 'assets/images/menu/peri-peri-fries.jpg', 'Additional Snacks', 'SNACKS_BEVERAGES', NULL, 1, 1, 10, 15, 450
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM menu_items WHERE slug='peri-peri-fries');

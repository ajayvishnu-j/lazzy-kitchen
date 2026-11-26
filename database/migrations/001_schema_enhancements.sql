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

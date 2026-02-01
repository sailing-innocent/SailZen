-- Migration: Create Necessity (生活物资) Tables
-- Author: sailing-innocent
-- Date: 2026-02-01
-- Description: Creates all tables for the necessity module including residences, containers, categories, items, inventory, journeys, etc.

-- Note: SQLAlchemy will auto-create these tables, but this SQL file is provided for manual migration reference.

-- Residences (住所)
CREATE TABLE IF NOT EXISTS residences (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE,
    type INTEGER DEFAULT 2,
    address VARCHAR(500),
    description TEXT,
    is_portable BOOLEAN DEFAULT FALSE,
    priority INTEGER DEFAULT 10,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Containers (容器/存储位置)
CREATE TABLE IF NOT EXISTS containers (
    id SERIAL PRIMARY KEY,
    residence_id INTEGER NOT NULL REFERENCES residences(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES containers(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    type INTEGER DEFAULT 99,
    description TEXT,
    capacity INTEGER,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_containers_residence ON containers(residence_id);
CREATE INDEX IF NOT EXISTS idx_containers_parent ON containers(parent_id);

-- Item Categories (物资类别)
CREATE TABLE IF NOT EXISTS item_categories (
    id SERIAL PRIMARY KEY,
    parent_id INTEGER REFERENCES item_categories(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE,
    icon VARCHAR(100),
    is_consumable BOOLEAN DEFAULT FALSE,
    default_unit VARCHAR(50) DEFAULT '个',
    description TEXT,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_categories_parent ON item_categories(parent_id);

-- Items (物资)
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id INTEGER REFERENCES item_categories(id) ON DELETE SET NULL,
    type INTEGER DEFAULT 0,
    brand VARCHAR(100),
    model VARCHAR(100),
    serial_number VARCHAR(100),
    description TEXT,
    purchase_date TIMESTAMP,
    purchase_price VARCHAR(50),
    warranty_until TIMESTAMP,
    expire_date TIMESTAMP,
    importance INTEGER DEFAULT 3,
    portability INTEGER DEFAULT 3,
    tags VARCHAR(500),
    image_url VARCHAR(500),
    state INTEGER DEFAULT 0,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_items_category ON items(category_id);
CREATE INDEX IF NOT EXISTS idx_items_state ON items(state);
CREATE INDEX IF NOT EXISTS idx_items_expire_date ON items(expire_date);

-- Inventories (库存记录)
CREATE TABLE IF NOT EXISTS inventories (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    residence_id INTEGER NOT NULL REFERENCES residences(id) ON DELETE CASCADE,
    container_id INTEGER REFERENCES containers(id) ON DELETE SET NULL,
    quantity NUMERIC(10, 2) DEFAULT 1,
    unit VARCHAR(50) DEFAULT '个',
    min_quantity NUMERIC(10, 2) DEFAULT 0,
    max_quantity NUMERIC(10, 2) DEFAULT 0,
    last_check_time TIMESTAMP,
    notes TEXT,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(item_id, residence_id, container_id)
);

CREATE INDEX IF NOT EXISTS idx_inventories_item ON inventories(item_id);
CREATE INDEX IF NOT EXISTS idx_inventories_residence ON inventories(residence_id);
CREATE INDEX IF NOT EXISTS idx_inventories_container ON inventories(container_id);

-- Journeys (旅程)
CREATE TABLE IF NOT EXISTS journeys (
    id SERIAL PRIMARY KEY,
    from_residence_id INTEGER NOT NULL REFERENCES residences(id),
    to_residence_id INTEGER NOT NULL REFERENCES residences(id),
    depart_time TIMESTAMP,
    arrive_time TIMESTAMP,
    status INTEGER DEFAULT 0,
    transport_mode VARCHAR(100),
    notes TEXT,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_journeys_from ON journeys(from_residence_id);
CREATE INDEX IF NOT EXISTS idx_journeys_to ON journeys(to_residence_id);
CREATE INDEX IF NOT EXISTS idx_journeys_status ON journeys(status);

-- Journey Items (旅程物资)
CREATE TABLE IF NOT EXISTS journey_items (
    id SERIAL PRIMARY KEY,
    journey_id INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity NUMERIC(10, 2) DEFAULT 1,
    is_return BOOLEAN DEFAULT FALSE,
    from_container_id INTEGER REFERENCES containers(id) ON DELETE SET NULL,
    to_container_id INTEGER REFERENCES containers(id) ON DELETE SET NULL,
    status INTEGER DEFAULT 0,
    notes TEXT,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_journey_items_journey ON journey_items(journey_id);
CREATE INDEX IF NOT EXISTS idx_journey_items_item ON journey_items(item_id);

-- Consumptions (消耗记录)
CREATE TABLE IF NOT EXISTS consumptions (
    id SERIAL PRIMARY KEY,
    inventory_id INTEGER NOT NULL REFERENCES inventories(id) ON DELETE CASCADE,
    quantity NUMERIC(10, 2) NOT NULL,
    htime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_consumptions_inventory ON consumptions(inventory_id);
CREATE INDEX IF NOT EXISTS idx_consumptions_htime ON consumptions(htime);

-- Replenishments (补货记录)
CREATE TABLE IF NOT EXISTS replenishments (
    id SERIAL PRIMARY KEY,
    inventory_id INTEGER NOT NULL REFERENCES inventories(id) ON DELETE CASCADE,
    quantity NUMERIC(10, 2) NOT NULL,
    source INTEGER DEFAULT 0,
    source_residence_id INTEGER REFERENCES residences(id) ON DELETE SET NULL,
    cost VARCHAR(50),
    transaction_id INTEGER,
    htime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_replenishments_inventory ON replenishments(inventory_id);
CREATE INDEX IF NOT EXISTS idx_replenishments_htime ON replenishments(htime);

-- Seed Default Residences
INSERT INTO residences (name, code, type, address, description, is_portable, priority) VALUES
    ('合肥住所', 'HF', 0, '', '稳定仓库，长期存储', FALSE, 1),
    ('杭州住所', 'HZ', 1, '', '后备仓库，周末往返', FALSE, 2),
    ('上海住所', 'SH', 2, '', '工作住所，日常居住', FALSE, 3),
    ('随身携带', 'PORTABLE', 3, '', '随身携带物品', TRUE, 0)
ON CONFLICT (code) DO NOTHING;

-- Seed Default Categories (via API call to /api/v1/necessity/category/seed)
-- The category seeding is handled by the API endpoint for better control

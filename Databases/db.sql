
-- =============================================================
-- ENUMS
-- =============================================================

CREATE TYPE equipment_status AS ENUM ('Active', 'Maintenance', 'Broken');
CREATE TYPE maintenance_status AS ENUM ('In Progress', 'Pending', 'Completed', 'Cancelled');
CREATE TYPE user_role AS ENUM ('farm_manager', 'technician', 'operator');

-- =============================================================
-- USERS
-- =============================================================

CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    user_name     VARCHAR(15)  NOT NULL,
    user_surname  VARCHAR(15)  NOT NULL,
    user_role     user_role    NOT NULL,
    email         VARCHAR(50)  NOT NULL UNIQUE DEFAULT 'no-reply@example.com',
    password_hash TEXT         NOT NULL DEFAULT ''
);

-- =============================================================
-- OPERATORS
-- =============================================================

CREATE TABLE operators (
    operator_id             INT          PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    operator_name           VARCHAR(50)  NOT NULL,
    certificate_no          VARCHAR(50),
    certificate_type        VARCHAR(50),
    certificate_expiry_date DATE,
    hire_date               DATE,
    phone                   VARCHAR(15),
    email                   VARCHAR(50)  DEFAULT 'no-reply@example.com'
);

-- =============================================================
-- EQUIPMENTS
-- =============================================================

CREATE TABLE equipments (
    equipment_id          SERIAL PRIMARY KEY,
    equipment_name        VARCHAR(100) NOT NULL,
    type                  VARCHAR(50)  NOT NULL,
    brand                 VARCHAR(50),
    model                 VARCHAR(30),
    serial_number         VARCHAR(30)  DEFAULT '00000',
    purchase_date         DATE         DEFAULT '2025-02-02',
    purchase_cost         NUMERIC(12,2),
    status                equipment_status NOT NULL DEFAULT 'Broken',
    required_certification VARCHAR(50),
    created_at            TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- =============================================================
-- COMPONENTS
-- =============================================================

CREATE TABLE components (
    component_id   SERIAL PRIMARY KEY,
    component_name VARCHAR(50)  NOT NULL,
    unit_price     NUMERIC(10,2),
    category       VARCHAR(15),
    stock_quantity INT          NOT NULL DEFAULT 0,
    notes          VARCHAR(100)
);

-- =============================================================
-- MAINTENANCE
-- =============================================================

CREATE TABLE maintenance (
    maintenance_id SERIAL PRIMARY KEY,
    equipment_id   INT          NOT NULL REFERENCES equipments(equipment_id) ON DELETE CASCADE,
    technician_id  INT  REFERENCES users(user_id) ON DELETE SET NULL,
    status         maintenance_status NOT NULL DEFAULT 'In Progress',
    date_from      DATE,
    date_to        DATE,
    cost           NUMERIC(12,2) DEFAULT 0,
    description    VARCHAR(200) DEFAULT 'Not Detected',
    notes          VARCHAR(100),

    CONSTRAINT chk_maintenance_dates CHECK (date_to IS NULL OR date_to >= date_from)
);

-- =============================================================
-- MAINTENANCE_COMPONENT  (N:M junction)
-- =============================================================

CREATE TABLE maintenance_component (
    maintenance_id INT NOT NULL REFERENCES maintenance(maintenance_id) ON DELETE CASCADE,
    component_id   INT NOT NULL REFERENCES components(component_id)   ON DELETE RESTRICT,
    quantity       INT NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (maintenance_id, component_id)
);

-- =============================================================
-- ASSIGNMENTS
-- =============================================================

CREATE TABLE assignments (
    assignment_id SERIAL PRIMARY KEY,
    equipment_id  INT          NOT NULL REFERENCES equipments(equipment_id) ON DELETE CASCADE,
    op_id         INT          NOT NULL REFERENCES operators(operator_id)   ON DELETE CASCADE,
    time_period   VARCHAR(25),
    approval      BOOLEAN      DEFAULT FALSE
);

-- =============================================================
-- INDEXES  (performance)
-- =============================================================

CREATE INDEX idx_maintenance_equipment  ON maintenance(equipment_id);
CREATE INDEX idx_maintenance_technician ON maintenance(technician_id);
CREATE INDEX idx_assignments_equipment  ON assignments(equipment_id);
CREATE INDEX idx_assignments_operator   ON assignments(op_id);

-- =============================================================
-- END OF SCHEMA
-- =============================================================
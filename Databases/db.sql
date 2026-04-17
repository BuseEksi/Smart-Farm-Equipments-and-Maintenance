DROP TABLE IF EXISTS users;
CREATE TABLE users(
    user_id SERIAL PRIMARY KEY,
    user_name VARCHAR(15) NOT NULL,
    user_surname VARCHAR(15) NOT NULL,
    user_nickname VARCHAR (20) NOT NULL,
    user_password VARCHAR(25) NOT NULL,
    user_role VARCHAR(10) NOT NULL


);
-- Stores farm equipment information including certification requirements.
CREATE TABLE Equipments (
    equipment_id SERIAL PRIMARY KEY,
    status VARCHAR(15) CHECK (status IN ('Active', 'In Service', 'Broken')),
    model VARCHAR(50) NOT NULL,
    serial VARCHAR(50),
    required_certification VARCHAR(50),
    specs VARCHAR(100)
);

--Records all maintenance activities performed on equipment
CREATE TABLE Maintenance (
    maintenance_id SERIAL PRIMARY KEY,
    status VARCHAR(15),
    date DATE NOT NULL,
    total_cost DECIMAL(10,2),
    time_period VARCHAR(25),
    equipment_id INT REFERENCES Equipments(equipment_id)
);

-- Stores spare parts and components used in maintenance
CREATE TABLE Components (
    component_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    cost DECIMAL(10,2)
);

-- Stores operator information including certification details
CREATE TABLE Operators (
    op_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    certificate_no VARCHAR(50),
    certificate_type VARCHAR(50),
    certificate_expiry_date DATE CHECK (certificate_expiry_date > '2000-01-01')
);

-- Links operators to equipment for a specific time period
CREATE TABLE Assignments (
    assignment_id SERIAL PRIMARY KEY,
    time_period VARCHAR(25),
    approval BOOLEAN,
    equipment_id INT REFERENCES Equipments(equipment_id),
    op_id INT REFERENCES Operators(op_id)
);

-- Junction table for the N:M relationship between Maintenance and Components
CREATE TABLE Maintenance_Component (
    maintenance_id INT REFERENCES Maintenance(maintenance_id),
    component_id INT REFERENCES Components(component_id),
    quantity INT NOT NULL,
    PRIMARY KEY (maintenance_id, component_id)
);


SELECT * FROM users;

ALTER TABLE users
DROP column user_nickname;

ALTER TABLE users
ADD column email VARCHAR(50) NOT NULL DEFAULT 'no-reply@example.com';

UPDATE users
SET email = 'bus3eks1@gmail.com'
WHERE user_id =1;

UPDATE users
SET email = 'gozdeuzal@gmail.com'
WHERE user_id = 2;

SELECT * FROM users;

ALTER TABLE equipments
ADD COLUMN equipment_name VARCHAR(15) NOT NULL;
ALTER TABLE equipments
ADD COLUMN type VARCHAR(15) NOT NULL;
ALTER TABLE equipments
ADD COLUMN brand VARCHAR(15) NOT NULL;
ALTER TABLE equipments
ADD COLUMN model VARCHAR(15) NOT NULL;
ALTER TABLE equipments
ADD COLUMN serial_number VARCHAR(15) NOT NULL DEFAULT '00000';
ALTER TABLE equipments
ADD COLUMN  purchase_date DATE;
ALTER TABLE equipments
ADD COLUMN purchase_cost DECIMAL(12,2);

ALTER TABLE equipments
ALTER COLUMN purchase_date SET DEFAULT '02.02.2025';

ALTER TABLE equipments
ALTER COLUMN brand DROP NOT NULL;

ALTER TABLE equipments
ALTER COLUMN model DROP NOT NULL;

ALTER TABLE equipments
ALTER COLUMN purchase_cost DROP NOT NULL;

ALTER TABLE equipments
ALTER COLUMN serial_number DROP NOT NULL;

CREATE TYPE equipment_status AS ENUM ('Active', 'Maintenance', 'Broken');

ALTER TABLE equipments
ADD COLUMN status equipment_status DEFAULT 'Broken';

CREATE TYPE maintenance_status AS ENUM ('Pending', 'In Progress', 'Completed');

ALTER TABLE maintenance
ALTER COLUMN status TYPE maintenance_status USING status::maintenance_status,
    ALTER COLUMN status SET DEFAULT 'In Progress';

ALTER TABLE maintenance
DROP COLUMN date;

ALTER TABLE maintenance
ADD COLUMN date_from DATE;

ALTER TABLE maintenance
ADD COLUMN date_to DATE;

ALTER TABLE maintenance
DROP COLUMN time_period;

ALTER TABLE maintenance
ADD COLUMN description VARCHAR(200) NOT NULL DEFAULT 'Not Detected';

ALTER TABLE maintenance
ADD op_id INT REFERENCES Operators(op_id) DEFAULT NULL;

ALTER TABLE maintenance
ADD COLUMN cost DECIMAL(12,2) DEFAULT 0;

ALTER TABLE maintenance
ADD COLUMN notes VARCHAR(100) DEFAULT NULL;

ALTER TABLE maintenance
DROP COLUMN total_cost;

ALTER TABLE maintenance
ADD COLUMN maintenance_date DATE NOT NULL;
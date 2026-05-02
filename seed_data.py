import psycopg2
import random
from faker import Faker
from datetime import timedelta, date
from werkzeug.security import generate_password_hash

fake = Faker('en_US')
random.seed(42)

# ─── DB CONNECTION ────────────────────────────────────────────────
conn = psycopg2.connect(
    host="localhost",
    database="farm_eq_maintenance",
    user="buseeksi",
    password="823607"
)
cur = conn.cursor()
tech_ids = []

print("Connected successfully, inserting data...")

# ─── ENUM VALUES ──────────────────────────────────────────────────
EQUIPMENT_STATUSES = ['Active', 'Maintenance', 'Broken']
MAINTENANCE_STATUSES = ['Pending', 'In Progress', 'Completed']
EQUIPMENT_TYPES = ['Agriculture', 'Harvesting', 'Irrigation', 'Pest Control', 'Transportation', 'Other']
CERTIFICATE_TYPES = ['Class A', 'Class B', 'Class C', 'Forklift', 'Pesticide', 'Heavy Machinery']

BRANDS = ['John Deere', 'CLAAS', 'New Holland', 'Case IH', 'Fendt', 'Massey Ferguson',
          'Kubota', 'Deutz-Fahr', 'Valtra', 'Same']

EQUIPMENT_NAMES = {
    'Agriculture':    ['Tractor', 'Rotary Tiller', 'Plow', 'Disc Harrow', 'Cultivator', 'Seed Drill'],
    'Harvesting':     ['Combine Harvester', 'Corn Harvester', 'Sugar Beet Harvester', 'Potato Harvester'],
    'Irrigation':     ['Sprinkler System', 'Drip Irrigation Pump', 'Water Pump', 'Irrigation Pipe Machine'],
    'Pest Control':   ['Sprayer', 'Boom Sprayer', 'Tractor Sprayer', 'Drone Sprayer'],
    'Transportation': ['Trailer', 'Tanker', 'Front Loader', 'Flatbed Cart'],
    'Other':          ['Hay Baler', 'Silage Machine', 'Fertilizer Spreader', 'Mower'],
}

COMPONENT_NAMES = [
    ('Engine Oil Filter', 'Engine'),
    ('Air Filter', 'Engine'),
    ('Fuel Filter', 'Engine'),
    ('V-Belt', 'Transmission'),
    ('Hydraulic Filter', 'Hydraulics'),
    ('Hydraulic Pump', 'Hydraulics'),
    ('Brake Pad', 'Brakes'),
    ('Front Tire', 'Wheels'),
    ('Rear Tire', 'Wheels'),
    ('Battery', 'Electrical'),
    ('Alternator', 'Electrical'),
    ('Starter Motor', 'Electrical'),
    ('Coolant Water Pump', 'Cooling'),
    ('Thermostat', 'Cooling'),
    ('Radiator', 'Cooling'),
    ('Clutch Disc', 'Transmission'),
    ('Gearbox Oil', 'Transmission'),
    ('Differential Oil', 'Transmission'),
    ('Piston Ring Set', 'Engine'),
    ('Spark Plugs', 'Engine'),
    ('Fuel Injector', 'Engine'),
    ('Power Steering Pump', 'Steering'),
    ('Tie Rod End', 'Steering'),
    ('Shock Absorber', 'Suspension'),
    ('Harvester Blade', 'Harvesting'),
    ('Threshing Drum', 'Harvesting'),
    ('Sieve Set', 'Harvesting'),
    ('Irrigation Nozzle', 'Irrigation'),
    ('Drip Hose Set', 'Irrigation'),
    ('Sprayer Nozzle', 'Pest Control'),
]

MAINTENANCE_DESCRIPTIONS = [
    'Routine maintenance performed',
    'Engine fault repaired',
    'Oil change completed',
    'Brake system inspection',
    'Hydraulic system service',
    'Electrical system check',
    'Tire replacement',
    'Filter replacement',
    'Periodic scheduled maintenance',
    'Emergency breakdown repair',
    'Pre-season service',
    'Cooling system flush',
    'Drivetrain maintenance',
    'Cutting blades replaced',
    'Irrigation system service',
    'Sprayer equipment cleaning',
    'Full system diagnostic',
    'Fuel system cleaning',
    'Transmission overhaul',
    'Battery and charging system check',

]



# ─── 1. OPERATORS (150 records) ───────────────────────────────────
print("Inserting operators...")
operator_ids = []
for _ in range(150):
    name = fake.name()
    cert_no = fake.bothify(text='??-####-??').upper() if random.random() > 0.1 else None
    cert_type = random.choice(CERTIFICATE_TYPES) if cert_no else None
    hire_date = fake.date_between(start_date='-10y', end_date='-6m')
    phone = fake.numerify(text='05#########') if random.random() > 0.05 else None
    email = fake.email() if random.random() > 0.1 else None
    cert_expiry = fake.date_between(start_date='-2y', end_date='+3y') if cert_no else None

    cur.execute("""
        INSERT INTO operators (operator_name, certificate_no, certificate_type, 
                               hire_date, phone, email, certificate_expiry_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING operator_id
    """, (name, cert_no, cert_type, hire_date, phone, email, cert_expiry))
    operator_ids.append(cur.fetchone()[0])
conn.commit()
print(f"  {len(operator_ids)} operators inserted.")

#------------------------------------------------------------------

print("Inserting users...")

# Farm Manager (farm_manager)
cur.execute("""
    INSERT INTO users (user_name, user_surname, user_role, email, password_hash)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (email) DO NOTHING
""", ('farm_manager', 'User', 'farm_manager', 'admin@farm.com', generate_password_hash('admin123')))

# Maintenance Team (technicians)
for i in range(5):
    cur.execute("""
        INSERT INTO users (user_name, user_surname, user_role, email, password_hash)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING
        RETURNING user_id
    """, (fake.first_name(), fake.last_name(), 'technician',
          f'technician{i + 1}@farm.com',
          generate_password_hash('tech123')))
    result = cur.fetchone()
    if result:
        tech_ids.append(result[0])

# Operators — her operator için bir users kaydı oluştur ve user_id'yi operators tablosuna yaz
print("Linking operators to user accounts...")
for op_id in operator_ids:
    cur.execute("SELECT operator_name FROM operators WHERE operator_id = %s", (op_id,))
    op = cur.fetchone()
    name_parts = op[0].split(' ', 1)
    first = name_parts[0]
    last = name_parts[1] if len(name_parts) > 1 else ''
    email = f"operator{op_id}@farm.com"

    cur.execute("""
        INSERT INTO users (user_name, user_surname, user_role, email, password_hash)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING
        RETURNING user_id
    """, (first[:15], last[:15], 'operator', email, generate_password_hash('op123')))

    result = cur.fetchone()
    if result:
        user_id = result[0]
        cur.execute("UPDATE operators SET user_id = %s WHERE operator_id = %s", (user_id, op_id))

conn.commit()
print("  Users and operator accounts inserted.")


# ─── 2. COMPONENTS (30 records) ───────────────────────────────────
print("Inserting components...")
component_ids = []
for comp_name, category in COMPONENT_NAMES:
    unit_price = round(random.uniform(50, 8000), 2)
    stock_qty = random.randint(0, 200)
    notes = fake.sentence(nb_words=6) if random.random() > 0.5 else None

    cur.execute("""
        INSERT INTO components (component_name, category, unit_price, stock_quantity, notes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING component_id
    """, (comp_name, category, unit_price, stock_qty, notes))
    component_ids.append(cur.fetchone()[0])

conn.commit()
print(f"  {len(component_ids)} components inserted.")

# ─── 3. EQUIPMENTS (500 records) ──────────────────────────────────
print("Inserting equipment...")
equipment_ids = []
for _ in range(500):
    eq_type = random.choice(EQUIPMENT_TYPES)
    eq_name = random.choice(EQUIPMENT_NAMES[eq_type])
    brand = random.choice(BRANDS)
    model = fake.bothify(text='??-####').upper()
    serial = fake.bothify(text='??########').upper()
    purchase_date = fake.date_between(start_date='-15y', end_date='-1y')
    purchase_cost = round(random.uniform(5000, 500000), 2)
    status = random.choices(EQUIPMENT_STATUSES, weights=[65, 25, 10])[0]

    cur.execute("""
        INSERT INTO equipments (equipment_name, type, brand, model, serial_number,
                                purchase_date, purchase_cost, status, required_certification)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING equipment_id
    """, (eq_name, eq_type, brand, model, serial, purchase_date, purchase_cost, status,
          random.choice(CERTIFICATE_TYPES) if random.random() > 0.2 else None))
    equipment_ids.append(cur.fetchone()[0])
conn.commit()
print(f"  {len(equipment_ids)} equipment inserted.")

# ─── 4. MAINTENANCE (4500 records) ────────────────────────────────
print("Inserting maintenance records... (this may take a moment)")
maintenance_ids = []
for i in range(4500):
    eq_id = random.choice(equipment_ids)
    tech_id = random.choice(tech_ids) if random.random() > 0.1 else None
    date_from = fake.date_between(start_date='-5y', end_date='today')
    status = random.choices(MAINTENANCE_STATUSES, weights=[20, 25, 55])[0]

    if status == 'Completed':
        date_to = date_from + timedelta(days=random.randint(1, 30))
    else:
        date_to = None

    cost = round(random.uniform(200, 50000), 2) if status in ('Completed', 'In Progress') else None
    description = random.choice(MAINTENANCE_DESCRIPTIONS)
    notes = fake.sentence(nb_words=8) if random.random() > 0.6 else None

    cur.execute("""
        INSERT INTO maintenance (status, equipment_id, description, technician_id,
                                 cost, notes, date_from, date_to)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING maintenance_id
    """, (status, eq_id, description, tech_id, cost, notes, date_from, date_to))
    maintenance_ids.append(cur.fetchone()[0])

    if (i + 1) % 500 == 0:
        conn.commit()
        print(f"  {i+1}/4500...")

conn.commit()
print(f"  {len(maintenance_ids)} maintenance records inserted.")

# ─── 5. MAINTENANCE_COMPONENT ─────────────────────────────────────
print("Inserting maintenance-component relations...")
mc_count = 0
for m_id in maintenance_ids:
    if random.random() > 0.4:
        chosen = random.sample(component_ids, random.randint(1, 4))
        for c_id in chosen:
            quantity = random.randint(1, 5)
            cur.execute("""
                INSERT INTO maintenance_component (maintenance_id, component_id, quantity)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (m_id, c_id, quantity))
            mc_count += 1

conn.commit()
print(f"  {mc_count} maintenance-component records inserted.")

# ─── 5.5 ASSIGNMENTS ──────────────────────────────────────────────
print("Inserting assignments...")
assignment_count = 0
for _ in range(1000):
    eq_id = random.choice(equipment_ids)
    op_id = random.choice(operator_ids)
    start = fake.date_between(start_date='-3y', end_date='-1m')
    end = start + timedelta(days=random.randint(7, 180))
    time_period = f"{start} / {end}"
    approval = random.choice([True, False, None])

    cur.execute("""
        INSERT INTO assignments (equipment_id, op_id, time_period, approval)
        VALUES (%s, %s, %s, %s)
    """, (eq_id, op_id, time_period, approval))
    assignment_count += 1

conn.commit()
print(f"  {assignment_count} assignments inserted.")




# ─── SUMMARY ──────────────────────────────────────────────────────
cur.execute("SELECT COUNT(*) FROM equipments");            eq_total   = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM maintenance");           m_total    = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM operators");             op_total   = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM components");            comp_total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM maintenance_component"); mc_total   = cur.fetchone()[0]

print("\n✅ All data inserted successfully!")
print(f"   equipments             : {eq_total}")
print(f"   maintenance            : {m_total}")
print(f"   operators              : {op_total}")
print(f"   components             : {comp_total}")
print(f"   maintenance_component  : {mc_total}")
print(f"   TOTAL                  : {eq_total + m_total + op_total + comp_total + mc_total}")

cur.close()
conn.close()
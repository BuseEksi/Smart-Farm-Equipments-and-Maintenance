import math

from flask import Flask, render_template, session, request, redirect, url_for, abort, flash
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date



app = Flask(__name__)
app.secret_key = '823607-Buse'

def connect_db():
    conn= psycopg2.connect(
        host="localhost",
        database="farm_final",
        user="buseeksi",
        password="823607"
    )
    return conn



@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


    cur.execute("SELECT COUNT(*) AS total FROM equipments;")
    total_equipment = cur.fetchone()["total"]


    cur.execute("SELECT COUNT(*) AS cnt FROM equipments "
                "WHERE created_at >= DATE_TRUNC('month', NOW());")
    new_this_month = cur.fetchone()["cnt"]


    cur.execute("SELECT COUNT(*) AS cnt FROM maintenance WHERE status = 'In Progress';")
    active_maintenance = cur.fetchone()["cnt"]


    cur.execute("SELECT COUNT(*) AS cnt FROM maintenance WHERE status = 'Pending';")
    upcoming = cur.fetchone()["cnt"]


    cur.execute("SELECT COUNT(*) AS cnt FROM equipments WHERE status = 'Broken';")
    broken = cur.fetchone()["cnt"]


    cur.execute("SELECT COUNT(*) AS cnt FROM equipments "
                "WHERE status = 'Broken' AND updated_at >= NOW() - INTERVAL '7 days';")
    broken_week = cur.fetchone()["cnt"]


    cur.execute("SELECT COALESCE(SUM(cost), 0) AS total FROM maintenance "
                "WHERE date_from >= DATE_TRUNC('month', NOW());")
    monthly_cost = cur.fetchone()["total"]


    budget_ok = monthly_cost < 50000


    cur.execute("SELECT m.maintenance_id, m.equipment_id, e.equipment_name, "
                "m.description, m.date_from AS maintenance_date, m.status "
                "FROM maintenance m JOIN equipments e ON m.equipment_id = e.equipment_id "
                "ORDER BY m.date_from DESC LIMIT 5;")
    recent_maintenance = cur.fetchall()


    cur.execute("SELECT e.equipment_id, e.equipment_name, e.type, e.status, "
                "MAX(m.date_from) AS last_maintenance "
                "FROM equipments e LEFT JOIN maintenance m ON e.equipment_id = m.equipment_id "
                "GROUP BY e.equipment_id, e.equipment_name, e.type, e.status "
                "ORDER BY e.equipment_name LIMIT 8;")
    equipment_summary = cur.fetchall()

    if session.get("role") == "operator":
        cur.execute("""
            SELECT COUNT(*) AS cnt 
            FROM assignments a
            WHERE a.op_id = %s AND a.approval = true
        """, (session.get("user_id"),))
        my_tasks = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) AS cnt 
            FROM assignments a
            WHERE a.op_id = %s AND a.approval IS NULL
        """, (session.get("user_id"),))
        my_pending = cur.fetchone()["cnt"]
    else:
        my_tasks = 0
        my_pending = 0

    if session.get("role") == "technician":
        cur.execute("""
            SELECT COUNT(*) AS cnt 
            FROM maintenance m
            WHERE m.technician_id = %s
            AND m.status IN ('In Progress', 'Pending')
        """, (session.get("user_id"),))
        my_tasks = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) AS cnt 
            FROM maintenance m
            WHERE m.technician_id = %s
            AND m.status = 'Pending'
        """, (session.get("user_id"),))
        my_pending = cur.fetchone()["cnt"]


    cur.close()
    conn.close()


    stats = {
        "total_equipment": total_equipment,
        "new_this_month": new_this_month,
        "active_maintenance": active_maintenance,
        "upcoming": upcoming,
        "broken": broken,
        "broken_week": broken_week,
        "monthly_cost": monthly_cost,
        "budget_ok": budget_ok,
        "my_tasks": my_tasks,
        "my_pending": my_pending,
    }

    return render_template("dashboard.html",
                           stats=stats,
                           recent_maintenance=recent_maintenance,
                           equipment_summary=equipment_summary)


@app.route('/signup', methods=['GET'])
def signup():
    return render_template("signup.html")


@app.route('/signup', methods=['POST'])
def signup_post():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)  # ← eklendi
    name = request.form['name']
    surname = request.form['surname']
    password = request.form['password']
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    role = "operator"
    email = request.form['email']

    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    exists = cur.fetchone()
    if exists:
        flash("User already exists")
        cur.close()
        conn.close()
        return redirect(url_for('login'))

    cur.execute(
        "INSERT INTO users (user_name, user_surname, user_role, email, password_hash) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING user_id",
        (name, surname, role, email, hashed_password))
    new_user_id = cur.fetchone()['user_id']

    cur.execute(
        "INSERT INTO operators (operator_id, operator_name) VALUES (%s, %s)",
        (new_user_id, f"{name} {surname}"))

    conn.commit()
    cur.close()
    conn.close()
    flash("Account created successfully. Please log in.")
    return redirect(url_for('login'))
@app.route('/', methods=['GET'])
def login():
    return render_template("login.html")
@app.route("/login", methods=["POST"])
def login_form():
    email = request.form["email"]
    password = request.form["password"]


    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    exist = cur.fetchone()

    if exist and check_password_hash(exist["password_hash"], password):
        session["logged_in"] = True
        session["email"] = email
        session["user_id"] = exist["user_id"]
        session["username"] = exist["user_name"]
        session["role"] = exist["user_role"]
        session["user_surname"] = exist["user_surname"]

        cur.close()
        conn.close()

        return redirect(url_for('dashboard'))
    else:
        flash("Invalid email or password.", "error")
        cur.close()
        conn.close()
        return redirect(url_for('login'))

@app.route("/logout")
def logout():
    session.pop("email", None)
    session.pop("logged_in", None)
    session.clear()
    return redirect(url_for('login'))

@app.route("/equipment", methods=["GET"])
def equipment():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    type_ = request.args.get("type", "")
    page = int(request.args.get("page", 1))
    offset = (page - 1) * 10

    query = "SELECT * FROM equipments WHERE 1=1"

    params = []
    if q:
        query += " AND equipment_name ILIKE %s"
        params.append(f"%{q}%")
    if status:
        query += " AND status::text = %s"
        params.append(status)
    if type_:
        query += " AND type = %s"
        params.append(type_)


    count_query = "SELECT COUNT(*) AS cnt FROM (" + query + ") AS sub"
    cur.execute(count_query, params)
    total_count = cur.fetchone()["cnt"]
    pages = math.ceil(total_count / 10) if total_count else 1


    query += " ORDER BY equipment_id DESC LIMIT 10 OFFSET %s"
    params.append(offset)

    cur.execute(query, params)
    items = cur.fetchall()
    cur.close()
    conn.close()

    equipment_types = ['Agriculture', 'Harvesting', 'Irrigation', 'Pest Control', 'Transportation', 'Other']

    return render_template("equipments_list.html", equipment=items, total=total_count,
                           total_pages=pages, current_page=page, equipment_types=equipment_types)

@app.route("/equipment/new", methods=["GET"])
def equipment_new():
    if session.get("logged_in"):
        return render_template("equipment_form.html")
    else:
        return redirect(url_for('login'))

@app.route("/equipment/new", methods=["POST"])
def equipment_new_post():
    if session.get("logged_in"):
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("INSERT INTO equipments (equipment_name, type, brand, model, serial_number, purchase_date, purchase_cost) VALUES (%s, %s, %s, %s, %s , %s, %s)",
                    (request.form["equipment_name"],
                    request.form["equipment_type"],
                    request.form["brand"] or None,
                    request.form["model"] or None,
                    request.form["serial_number"] or None,
                    request.form["purchase_date"] or None,
                    request.form["purchase_cost"] or None
                    ))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('equipment'))
    else:
        return redirect(url_for('login'))

@app.route("/equipment/edit/<int:equipment_id>", methods=["GET", "POST"])
def equipment_edit(equipment_id):
    if session.get("logged_in") and session.get("role") == "farm_manager":
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if  request.method == "POST":
            equipment_name = request.form["equipment_name"]
            equipment_type = request.form["equipment_type"]
            brand = request.form["brand"] or None
            model = request.form["model"] or None
            serial_number = request.form["serial_number"] or None
            purchase_date = request.form["purchase_date"] or None
            purchase_cost = request.form["purchase_cost"] or None
            cur.execute("UPDATE equipments SET equipment_name = %s , type= %s ,brand = %s,"
                        " model = %s , serial_number = %s , purchase_date = %s ,purchase_cost = %s WHERE equipment_id = %s"

                        , (equipment_name, equipment_type, brand, model, serial_number, purchase_date, purchase_cost, equipment_id))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('equipment'))
        else:
            cur.execute("SELECT * FROM equipments WHERE equipment_id = %s", (equipment_id,))
            equipment = cur.fetchone()
            cur.close()
            conn.close()

            return render_template('equipment_form.html', equipment=equipment)
    else:
        return redirect(url_for('login'))

@app.route("/equipment/delete/<int:equipment_id>", methods=["POST"])
def equipment_delete(equipment_id):
    if session.get("logged_in") and session.get("role") == "farm_manager" and request.method == "POST":
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM equipments WHERE equipment_id = %s", (equipment_id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('equipment'))

@app.route("/equipment/<int:equipment_id>", methods=["GET"])
def equipment_detail(equipment_id):
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM equipments WHERE equipment_id = %s", (equipment_id,))
    equipment = cur.fetchone()

    cur.execute("SELECT COUNT(*) AS cnt FROM maintenance WHERE equipment_id = %s;", (equipment_id,))
    maint_count = cur.fetchone()["cnt"]


    cur.execute("SELECT COALESCE(SUM(cost), 0) AS total FROM maintenance WHERE equipment_id = %s;", (equipment_id,))
    total_cost = cur.fetchone()["total"]


    cur.execute("SELECT MAX(date_from) AS last FROM maintenance WHERE equipment_id = %s;", (equipment_id,))
    last_maint = cur.fetchone()["last"]

    cur.execute("""
        SELECT m.maintenance_id, m.date_from, m.date_to, m.status, m.cost,
               m.description, m.notes,
               t.user_name
        FROM maintenance m
        LEFT JOIN users t ON m.technician_id = t.user_id
        WHERE m.equipment_id = %s
        ORDER BY m.date_from DESC
    """, (equipment_id,))
    maintenance_history = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("equipment_detail.html" , maintenance_history=maintenance_history, equipment=equipment, maint_count=maint_count,
                           total_cost=total_cost,
                           last_maint=last_maint,)


"""
Maintenance Route'ları - Güncellenmiş Versiyon
Technician atama ve Component stok yönetimi ile
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from psycopg2.extras import RealDictCursor


# === MAINTENANCE LİSTELEME ===
@app.route('/maintenance')
def maintenance_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))


# --- PAGINATION ---
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

# --- FILTERS ---
    q = request.args.get('q', '').strip()
    equipment_filter = request.args.get('equipment_id')
    status_filter = request.args.get('status')
    technician_filter = request.args.get('technician_id')
    date_from = request.args.get('date_from')


    where_conditions = []
    params = []

    conn = connect_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)



# SEARCH
    if q:
        where_conditions.append("""
            (m.description ILIKE %s 
            OR e.equipment_name ILIKE %s 
             OR t.user_name ILIKE %s)
        """)
        search = f"%{q}%"
        params.extend([search, search, search])

    if equipment_filter:
        where_conditions.append("m.equipment_id = %s")
        params.append(equipment_filter)

    if status_filter:
        where_conditions.append("m.status = %s")
        params.append(status_filter)

    if technician_filter:
        where_conditions.append("m.technician_id = %s")
        params.append(technician_filter)

    if date_from:
        where_conditions.append("m.date_from >= %s")
        params.append(date_from)



    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)



# --- TOTAL COUNT ---
    count_query = f"""
        SELECT COUNT(*) AS cnt
        FROM maintenance m
        LEFT JOIN equipments e ON m.equipment_id = e.equipment_id
        LEFT JOIN users t ON m.technician_id = t.user_id
        {where_clause}
    """
    cur.execute(count_query, params)
    total = cur.fetchone()['cnt']

    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

# --- DATA QUERY ---
    data_query = f"""
        SELECT m.*, 
            e.equipment_name,
            e.type AS equipment_type,
            t.user_name AS technician_name
        FROM maintenance m
        LEFT JOIN equipments e ON m.equipment_id = e.equipment_id
        LEFT JOIN users t ON m.technician_id = t.user_id
        {where_clause}
        ORDER BY m.date_from DESC
        LIMIT %s OFFSET %s
    """
    cur.execute(data_query, params + [per_page, offset])
    maintenances = cur.fetchall()

# --- DROPDOWNS ---
    cur.execute("SELECT equipment_id, equipment_name FROM equipments ORDER BY equipment_name")
    equipments = cur.fetchall()

    cur.execute("""
        SELECT user_id, user_name 
        FROM users 
        WHERE user_role = 'technician'
        ORDER BY user_name
        """)
    technicians = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('maintenance_list.html', maintenance=maintenances,
                           total=total, current_page=page, total_pages=total_pages,
                           q=q, equipments=equipments, technicians=technicians,
                           equipment_filter=equipment_filter, status_filter=status_filter,
                           technician_filter=technician_filter ,date_from=date_from)






# === YENİ MAINTENANCE OLUŞTURMA (GET) ===
@app.route('/maintenance/new', methods=['GET'])
def maintenance_new_form():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Equipment'ları çek
    cur.execute("SELECT * FROM equipments ORDER BY equipment_name")
    equipments = cur.fetchall()

    # Technician'ları çek (user_role = 'technician' olanlar)
    cur.execute("""
        SELECT user_id, user_name, email 
        FROM users 
        WHERE user_role = 'technician'
        ORDER BY user_name
    """)
    technicians = cur.fetchall()

    # Component'lari çek (stokta olanlar)
    cur.execute("""
        SELECT component_id, component_name, stock_quantity
        FROM components
        WHERE stock_quantity > 0
        ORDER BY component_name
    """)
    components = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('maintenance_form.html',
                           equipments=equipments,
                           technicians=technicians,
                           components=components,
                           maintenance=None,
                           selected_components=[],
                           selected_quantities={})


# === YENİ MAINTENANCE OLUŞTURMA (POST) ===
@app.route('/maintenance/new', methods=['POST'])
def maintenance_new_submit():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    equipment_id = request.form.get('equipment_id')
    description = request.form.get('description')
    date_from = request.form.get('date_from')
    status = request.form.get('status')
    technician_id = request.form.get('technician_id') or None
    cost = request.form.get('cost') or None
    notes = request.form.get('notes') or None

    # Component'leri al
    component_ids = request.form.getlist('component_ids[]')

    conn = connect_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1. Maintenance kaydını oluştur
        cur.execute("""
            INSERT INTO maintenance 
            (equipment_id, description, date_from, status, technician_id, cost, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING maintenance_id
        """, (equipment_id, description, date_from, status, technician_id, cost, notes))

        maintenance_id = cur.fetchone()['maintenance_id']

        # 2. Seçilen component'leri işle
        for component_id in component_ids:
            quantity = int(request.form.get(f'component_quantities_{component_id}', 1))

            # Component stoğunu kontrol et
            cur.execute("""
                SELECT stock_quantity, component_name 
                FROM components 
                WHERE component_id = %s
            """, (component_id,))
            component = cur.fetchone()

            if not component:
                raise Exception(f"Component ID {component_id} bulunamadı!")

            if component['stock_quantity'] < quantity:
                raise Exception(
                    f"{component['component_name']} için yeterli stok yok! "
                    f"İstenen: {quantity}, Mevcut: {component['stock_quantity']}"
                )

            # maintenance_component tablosuna ekle
            cur.execute("""
                INSERT INTO maintenance_component 
                (maintenance_id, component_id, quantity)
                VALUES (%s, %s, %s)
            """, (maintenance_id, component_id, quantity))

            # Component stoğunu düşür
            cur.execute("""
                UPDATE components 
                SET stock_quantity = stock_quantity - %s
                WHERE component_id = %s
            """, (quantity, component_id))

        conn.commit()
        flash('Maintenance record created successfully!', 'success')
        return redirect(url_for('maintenance_list'))

    except Exception as e:
        conn.rollback()
        flash(f'Error creating maintenance: {str(e)}', 'error')
        return redirect(url_for('maintenance_new_form'))

    finally:
        cur.close()
        conn.close()


# === MAINTENANCE DÜZENLEME (GET) ===
@app.route('/maintenance/edit/<int:maintenance_id>', methods=['GET'])
def maintenance_edit_form(maintenance_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Maintenance kaydını çek
    cur.execute("""
        SELECT * FROM maintenance 
        WHERE maintenance_id = %s
    """, (maintenance_id,))
    maintenance = cur.fetchone()

    if not maintenance:
        flash('Maintenance record not found!', 'error')
        return redirect(url_for('maintenance_list'))

    # Equipment'ları çek
    cur.execute("SELECT * FROM equipments ORDER BY equipment_name")
    equipments = cur.fetchall()

    # Technician'ları çek
    cur.execute("""
        SELECT user_id, user_name, email 
        FROM users 
        WHERE user_role = 'technician'
        ORDER BY user_name
    """)
    technicians = cur.fetchall()

    # Tüm component'lari çek
    cur.execute("""
        SELECT component_id, component_name, stock_quantity
        FROM components
        ORDER BY component_name
    """)
    components = cur.fetchall()

    # Bu maintenance'ta kullanılan component'leri çek
    cur.execute("""
        SELECT component_id, quantity
        FROM maintenance_component
        WHERE maintenance_id = %s
    """, (maintenance_id,))
    used_components = cur.fetchall()

    selected_components = [c['component_id'] for c in used_components]
    selected_quantities = {c['component_id']: c['quantity'] for c in used_components}

    cur.close()
    conn.close()

    return render_template('maintenance_form.html',
                           maintenance=maintenance,
                           equipments=equipments,
                           technicians=technicians,
                           components=components,
                           selected_components=selected_components,
                           selected_quantities=selected_quantities)


# === MAINTENANCE DÜZENLEME (POST) ===
@app.route('/maintenance/edit/<int:maintenance_id>', methods=['POST'])
def maintenance_edit_submit(maintenance_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    equipment_id = request.form.get('equipment_id')
    description = request.form.get('description')
    date_from = request.form.get('date_from')
    status = request.form.get('status')
    technician_id = request.form.get('technician_id') or None
    cost = request.form.get('cost') or None
    notes = request.form.get('notes') or None

    # Yeni component'leri al
    new_component_ids = request.form.getlist('component_ids[]')

    conn = connect_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1. Eski component'leri geri ekle (stok geri kazanımı)
        cur.execute("""
            SELECT component_id, quantity
            FROM maintenance_component
            WHERE maintenance_id = %s
        """, (maintenance_id,))
        old_components = cur.fetchall()

        for old_comp in old_components:
            cur.execute("""
                UPDATE components 
                SET stock_quantity = stock_quantity + %s
                WHERE component_id = %s
            """, (old_comp['quantity'], old_comp['component_id']))

        # 2. Eski component kayıtlarını sil
        cur.execute("""
            DELETE FROM maintenance_component
            WHERE maintenance_id = %s
        """, (maintenance_id,))

        # 3. Maintenance kaydını güncelle
        cur.execute("""
            UPDATE maintenance
            SET equipment_id = %s,
                description = %s,
                date_from = %s,
                status = %s,
                technician_id = %s,
                cost = %s,
                notes = %s
            WHERE maintenance_id = %s
        """, (equipment_id, description, date_from, status,
              technician_id, cost, notes, maintenance_id))

        # 4. Yeni component'leri ekle
        for component_id in new_component_ids:
            quantity = int(request.form.get(f'component_quantities_{component_id}', 1))

            # Stok kontrolü
            cur.execute("""
                SELECT stock_quantity, component_name 
                FROM components 
                WHERE component_id = %s
            """, (component_id,))
            component = cur.fetchone()

            if not component:
                raise Exception(f"Component ID {component_id} bulunamadı!")

            if component['stock_quantity'] < quantity:
                raise Exception(
                    f"{component['component_name']} için yeterli stok yok! "
                    f"İstenen: {quantity}, Mevcut: {component['stock_quantity']}"
                )

            # maintenance_component tablosuna ekle
            cur.execute("""
                INSERT INTO maintenance_component 
                (maintenance_id, component_id, quantity)
                VALUES (%s, %s, %s)
            """, (maintenance_id, component_id, quantity))

            # Stoğu düşür
            cur.execute("""
                UPDATE components 
                SET stock_quantity = stock_quantity - %s
                WHERE component_id = %s
            """, (quantity, component_id))

        conn.commit()
        flash('Maintenance record updated successfully!', 'success')
        return redirect(url_for('maintenance_list'))

    except Exception as e:
        conn.rollback()
        flash(f'Error updating maintenance: {str(e)}', 'error')
        return redirect(url_for('maintenance_edit_form', maintenance_id=maintenance_id))

    finally:
        cur.close()
        conn.close()


# === MAINTENANCE SİLME ===
@app.route('/maintenance/delete/<int:maintenance_id>', methods=['POST'])
def maintenance_delete(maintenance_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Sadece farm_manager silebilir
    if session.get('role') != 'farm_manager':
        flash('Only farm managers can delete maintenance records!', 'error')
        return redirect(url_for('maintenance_list'))

    conn = connect_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1. Kullanılan component'leri stoka geri ekle
        cur.execute("""
            SELECT component_id, quantity
            FROM maintenance_component
            WHERE maintenance_id = %s
        """, (maintenance_id,))
        used_components = cur.fetchall()

        for comp in used_components:
            cur.execute("""
                UPDATE components 
                SET stock_quantity = stock_quantity + %s
                WHERE component_id = %s
            """, (comp['quantity'], comp['component_id']))

        # 2. maintenance_component kayıtlarını sil
        cur.execute("""
            DELETE FROM maintenance_component
            WHERE maintenance_id = %s
        """, (maintenance_id,))

        # 3. Maintenance kaydını sil
        cur.execute("""
            DELETE FROM maintenance
            WHERE maintenance_id = %s
        """, (maintenance_id,))

        conn.commit()
        flash('Maintenance record deleted successfully!', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Error deleting maintenance: {str(e)}', 'error')

    finally:
        cur.close()
        conn.close()

    return redirect(url_for('maintenance_list'))


@app.route("/maintenance/<int:maintenance_id>", methods=["GET"])
def maintenance_detail(maintenance_id):
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
    SELECT m.*,
    e.equipment_name, e.model, e.brand, e.serial_number, e.type as equipment_type,
    t.user_name as technician_name
    FROM maintenance m
    JOIN equipments e ON m.equipment_id = e.equipment_id
    LEFT JOIN users t ON m.technician_id = t.user_id
    WHERE m.maintenance_id = %s
    """, (maintenance_id,))

    maintenance_record = cur.fetchone()

    if not maintenance_record:
        cur.close()
        conn.close()
        return "Maintenance record couldn't found.", 404


    cur.execute("""
        SELECT mc.quantity, c.unit_price, (mc.quantity * c.unit_price) as total_price,
               c.component_name, c.category
        FROM maintenance_component mc
        JOIN components c ON mc.component_id = c.component_id
        WHERE mc.maintenance_id = %s
    """, (maintenance_id,))
    used_components = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('maintenance_detail.html',
                           maintenance=maintenance_record,
                           components=used_components)

@app.route("/components", methods=["GET"])
def components():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    q = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '')

    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    where_conditions = []
    params = []

    if q:
        where_conditions.append("component_name ILIKE %s")
        params.append(f"%{q}%")

    if category_filter:
        where_conditions.append("category = %s")
        params.append(category_filter)

    where_clause = ("WHERE " + " AND ".join(where_conditions)) if where_conditions else ""

    cur.execute(f"SELECT COUNT(*) AS cnt FROM components {where_clause}", params)
    total = cur.fetchone()['cnt']

    offset = (page - 1) * per_page
    cur.execute(f"SELECT * FROM components {where_clause} ORDER BY component_id DESC LIMIT %s OFFSET %s",
                params + [per_page, offset])
    all_components = cur.fetchall()


    cur.execute("SELECT DISTINCT category FROM components WHERE category IS NOT NULL ORDER BY category")
    categories = [row['category'] for row in cur.fetchall()]

    cur.close()
    conn.close()

    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    return render_template("components_list.html",
                           components=all_components,
                           total=total,
                           current_page=page,
                           total_pages=total_pages,
                           q=q,
                           category_filter=category_filter,
                           categories=categories)

@app.route("/components/new", methods=["GET"])
def component_new():
    if session.get("role") == 'farm_manager':
        return render_template("component_form.html")
    else:
        return redirect(url_for('login'))

@app.route("/components/new", methods=["POST"])
def component_new_form():
    if session.get("role") == 'farm_manager':
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        component_name = request.form["component_name"]
        category=request.form["category"] or None
        unit_price = request.form["unit_price"] or None
        stock_quantity = request.form["stock_quantity"] or None
        notes = request.form["notes"] or None
        cur.execute("INSERT INTO components (component_name, category, unit_price, stock_quantity, notes)" 
                    "VALUES (%s, %s, %s, %s, %s)", (component_name, category, unit_price, stock_quantity, notes))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('components'))
    else:
        return redirect(url_for('login'))

@app.route("/components/edit/<int:component_id>", methods=["GET","POST"])
def component_edit(component_id):
    if session.get("role") == 'farm_manager':
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if request.method == "POST":
            component_name = request.form["component_name"]
            category = request.form["category"] or None
            unit_price = request.form["unit_price"] or None
            stock_quantity = request.form["stock_quantity"] or None
            notes = request.form["notes"] or None
            cur.execute("UPDATE components SET component_name = %s, category = %s, unit_price = %s, stock_quantity = %s, notes = %s WHERE component_id = %s",
                    (component_name, category, unit_price, stock_quantity, notes, component_id))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('components'))
        else:
            cur.execute("SELECT * FROM components WHERE component_id = %s", (component_id,))
            component = cur.fetchone()
            cur.close()
            conn.close()
            return render_template("component_form.html", component=component)
    else:
        return redirect(url_for('login'))

@app.route("/components/delete/<int:component_id>", methods=["POST"])
def component_delete(component_id):
    if session.get("role") == 'farm_manager':
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("DELETE FROM components WHERE component_id = %s", (component_id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('components'))
    else:
        return redirect(url_for('login'))

@app.route("/operators", methods=["GET"])
def operators():
    if session.get("role") != 'farm_manager':
        flash("You don't have permission to access this page.", "error")
        return redirect("/dashboard")
    page = request.args.get('page', 1, type=int)
    per_page = 10

    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT COUNT(*) AS count FROM operators")
    total = cur.fetchone()['count']

    offset = (page - 1) * per_page
    cur.execute("""
        SELECT o.*, COUNT(a.assignment_id) AS assignment_count
        FROM operators o
        LEFT JOIN assignments a ON o.operator_id = a.op_id
        GROUP BY o.operator_id
        ORDER BY o.operator_id DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    all_operators = cur.fetchall()

    cur.close()
    conn.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template("operators_list.html",
        operators=all_operators,
        total=total,
        current_page=page,
        total_pages=total_pages
    )

@app.route("/operators/new", methods=["GET"])
def operators_new():
    if session.get("role") == 'farm_manager':
        return render_template("operator_form.html")
    else:
        return redirect(url_for('login'))

@app.route("/operators/new", methods=["POST"])
def operator_new_form():
    if session.get("role") == 'farm_manager':
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        operator_name = request.form["operator_name"]
        certificate_no = request.form["certificate_no"] or None
        certificate_type = request.form["certificate_type"] or None
        hire_date = request.form["hire_date"] or None
        phone = request.form["phone"] or None
        email = request.form["email"] or None
        password = request.form["password"]  # new field

        # 1. Create the users row first
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        cur.execute(
            "INSERT INTO users (user_name, user_surname, user_role, email, password_hash) "
            "VALUES (%s, %s, 'operator', %s, %s) RETURNING user_id",
            (operator_name, '', email, hashed_password)
        )
        new_user_id = cur.fetchone()['user_id']

        # 2. Create the operators profile row linked to that user
        cur.execute(
            "INSERT INTO operators (operator_name, certificate_no, certificate_type, "
            "hire_date, phone, email, operator_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (operator_name, certificate_no, certificate_type,
             hire_date, phone, email, new_user_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('operators'))
    else:
        return redirect(url_for('login'))

@app.route("/operators/edit/<int:operator_id>", methods=["GET","POST"])
def operator_edit(operator_id):
    if session.get("role") == 'farm_manager':
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if request.method == "POST":
            operator_name = request.form["operator_name"]

            certificate_no = request.form["certificate_no"] or None
            certificate_type = request.form["certificate_type"] or None
            hire_date = request.form["hire_date"] or None
            phone = request.form["phone"] or None
            email = request.form["email"] or None
            cur.execute("UPDATE operators SET operator_name = %s , "
                    "certificate_no = %s, certificate_type = %s, hire_date = %s, phone = %s, email = %s WHERE operator_id = %s",
                    (operator_name, certificate_no, certificate_type, hire_date, phone, email, operator_id))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('operators'))
        else:
            cur.execute("SELECT * FROM operators WHERE operator_id = %s", (operator_id,))
            operator = cur.fetchone()
            cur.close()
            conn.close()
            return render_template("operator_form.html", operator=operator)
    else:
        return redirect(url_for('login'))

@app.route("/operators/delete/<int:operator_id>", methods=["POST"])
def operator_delete(operator_id):
    if session.get("role") == 'farm_manager':
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id = %s", (operator_id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('operators'))
    else:
        return redirect(url_for('login'))


@app.route("/assignments/request/<int:equipment_id>", methods=["POST"])
def assignment_request(equipment_id):
    if session.get("role") != "operator":
        return redirect(url_for('login'))

    op_id = session.get("user_id")
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT assignment_id FROM assignments
        WHERE equipment_id = %s AND op_id = %s AND (approval IS NULL OR approval = TRUE)
    """, (equipment_id, op_id))
    existing = cur.fetchone()

    if existing:
        flash("You already have an active or pending assignment for this equipment.", "error")
    else:
        cur.execute("""
            INSERT INTO assignments (equipment_id, op_id, approval)
            VALUES (%s, %s, NULL)
        """, (equipment_id, op_id))
        conn.commit()
        flash("Assignment request submitted.", "success")

    cur.close()
    conn.close()


    next_page = request.form.get("next", "equipment")
    if next_page == "detail":
        return redirect(url_for('equipment_detail', equipment_id=equipment_id))
    return redirect(url_for('equipment'))



@app.route("/assignments/approve/<int:assignment_id>", methods=["POST"])
def assignment_approve(assignment_id):
    if session.get("role") != "farm_manager":
        return redirect(url_for('login'))

    conn = connect_db()
    cur = conn.cursor()
    cur.execute("UPDATE assignments SET approval = TRUE WHERE assignment_id = %s", (assignment_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Assignment approved.", "success")
    return redirect(url_for('assignments'))



@app.route("/assignments/reject/<int:assignment_id>", methods=["POST"])
def assignment_reject(assignment_id):
    if session.get("role") != "farm_manager":
        return redirect(url_for('login'))

    conn = connect_db()
    cur = conn.cursor()
    cur.execute("UPDATE assignments SET approval = FALSE WHERE assignment_id = %s", (assignment_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Assignment rejected.", "error")
    return redirect(url_for('assignments'))
@app.route("/technicians")
def technicians():
    if session.get("role") == 'farm_manager':
        page = request.args.get('page', 1, type=int)
        per_page = 10
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE user_role = 'technician'")
        total = cur.fetchone()['cnt']


        offset = (page - 1) * per_page
        cur.execute("SELECT * FROM users WHERE user_role = 'technician' ORDER BY user_id DESC LIMIT %s OFFSET %s",
                    (per_page, offset))
        all_technicians = cur.fetchall()
        total_pages = (total + per_page - 1) // per_page
        cur.close()
        conn.close()
        return render_template("technicians_list.html", technicians=all_technicians, total=len(all_technicians), current_page=page, total_pages=total_pages)

@app.route("/technicians/new", methods=["GET", "POST"])
def new_technician():
    if session.get("role") != "farm_manager":
        flash("You don't have permission to access this page.", "error")
        return redirect("/dashboard")

    if request.method == "POST":
        name = request.form["name"]
        surname = request.form["surname"]
        email = request.form["email"]
        password = request.form["password"]

        conn = connect_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (user_name, user_surname, email, user_role, password_hash) VALUES (%s, %s, %s, 'technician', %s)",
            (name, surname, email, generate_password_hash(password))
        )
        conn.commit()
        cur.close()
        conn.close()
        flash("Technician added successfully.", "success")
        return redirect("/technicians")

    return render_template("technician_form.html")

@app.route("/technicians/delete/<int:technician_id>", methods=["POST"])
def delete_technician(technician_id):
    if session.get("role") != "farm_manager":
        flash("You don't have permission to access this page.", "error")
        return redirect("/dashboard")
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("DELETE FROM users WHERE user_id = %s", (technician_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Technician deleted successfully.", "success")
    return redirect("/technicians")

@app.route("/my-maintenance", methods=["GET"])
def my_maintenance():
    if session.get("role") != "technician":
        return redirect(url_for('login'))

    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status')

    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    where_conditions = ["m.technician_id = %s"]
    params = [session.get("user_id")]

    if q:
        where_conditions.append("(e.equipment_name ILIKE %s OR m.description ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    if status_filter:
        where_conditions.append("m.status = %s")
        params.append(status_filter)

    where_clause = "WHERE " + " AND ".join(where_conditions)

    cur.execute(f"""
        SELECT COUNT(*) AS cnt
        FROM maintenance m
        LEFT JOIN equipments e ON m.equipment_id = e.equipment_id
        {where_clause}
    """, params)
    total = cur.fetchone()["cnt"]
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    cur.execute(f"""
        SELECT m.*, e.equipment_name, e.type AS equipment_type
        FROM maintenance m
        LEFT JOIN equipments e ON m.equipment_id = e.equipment_id
        {where_clause}
        ORDER BY m.date_from DESC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    maintenances = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("technician_maintenance_list.html",
                           maintenance=maintenances,
                           total=total,
                           current_page=page,
                           total_pages=total_pages,
                           q=q,
                           status_filter=status_filter)


@app.route("/my-maintenance/edit/<int:maintenance_id>", methods=["GET", "POST"])
def my_maintenance_edit(maintenance_id):
    if session.get("role") != "technician":
        return redirect(url_for('login'))

    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


    cur.execute("SELECT * FROM maintenance WHERE maintenance_id = %s AND technician_id = %s",
                (maintenance_id, session.get("user_id")))
    maintenance = cur.fetchone()

    if not maintenance:
        flash("Record not found or you don't have permission to edit it.", "error")
        cur.close()
        conn.close()
        return redirect(url_for('my_maintenance'))

    if request.method == "POST":
        status = request.form.get("status")
        date_from = request.form.get("date_from")
        date_to = request.form.get("date_to") or None
        cost = request.form.get("cost") or None
        description = request.form.get("description")
        notes = request.form.get("notes") or None

        new_component_ids = request.form.getlist("component_ids[]")

        try:

            cur.execute("SELECT component_id, quantity FROM maintenance_component WHERE maintenance_id = %s",
                        (maintenance_id,))
            old_components = cur.fetchall()
            for old in old_components:
                cur.execute("UPDATE components SET stock_quantity = stock_quantity + %s WHERE component_id = %s",
                            (old["quantity"], old["component_id"]))

            cur.execute("DELETE FROM maintenance_component WHERE maintenance_id = %s", (maintenance_id,))

            cur.execute("""
                UPDATE maintenance
                SET status = %s, date_from = %s, date_to = %s,
                    cost = %s, description = %s, notes = %s
                WHERE maintenance_id = %s
            """, (status, date_from, date_to, cost, description, notes, maintenance_id))

            for component_id in new_component_ids:
                quantity = int(request.form.get(f"component_quantities_{component_id}", 1))
                cur.execute("SELECT stock_quantity, component_name FROM components WHERE component_id = %s",
                            (component_id,))
                component = cur.fetchone()
                if component["stock_quantity"] < quantity:
                    raise Exception(f"{component['component_name']} için yeterli stok yok!")
                cur.execute("INSERT INTO maintenance_component (maintenance_id, component_id, quantity) VALUES (%s, %s, %s)",
                            (maintenance_id, component_id, quantity))
                cur.execute("UPDATE components SET stock_quantity = stock_quantity - %s WHERE component_id = %s",
                            (quantity, component_id))

            conn.commit()
            flash("Maintenance record updated successfully.", "success")
            return redirect(url_for('my_maintenance'))

        except Exception as e:
            conn.rollback()
            flash(f"Error: {str(e)}", "error")


    cur.execute("SELECT * FROM equipments ORDER BY equipment_name")
    equipments = cur.fetchall()

    cur.execute("SELECT component_id, component_name, stock_quantity FROM components ORDER BY component_name")
    components = cur.fetchall()

    cur.execute("SELECT component_id, quantity FROM maintenance_component WHERE maintenance_id = %s", (maintenance_id,))
    used = cur.fetchall()
    selected_components = [c["component_id"] for c in used]
    selected_quantities = {c["component_id"]: c["quantity"] for c in used}

    cur.close()
    conn.close()

    return render_template("maintenance_form.html",
                           maintenance=maintenance,
                           equipments=equipments,
                           technicians=[],
                           components=components,
                           selected_components=selected_components,
                           selected_quantities=selected_quantities)


@app.route("/assignments", methods=["GET"])
def assignments():
    if not session.get("logged_in"):
        return redirect(url_for('login'))

    page = request.args.get('page', 1, type=int)
    per_page = 10
    q = request.args.get("q", "")
    approval = request.args.get("approval", "")

    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    base_query = """
        SELECT a.assignment_id, a.time_period, a.approval,
               e.equipment_name, e.type,
               o.operator_name, o.certificate_type
        FROM assignments a
        JOIN equipments e ON a.equipment_id = e.equipment_id
        JOIN operators o ON a.op_id = o.operator_id
        WHERE 1=1
    """
    params = []

    if session.get("role") == "operator":
        base_query += " AND a.op_id = %s"
        params.append(session.get("user_id"))

    if q:
        base_query += " AND (e.equipment_name ILIKE %s OR o.operator_name ILIKE %s)"
        params.extend([f"%{q}%", f"%{q}%"])

    if approval == "approved":
        base_query += " AND a.approval = true"
    elif approval == "rejected":
        base_query += " AND a.approval = false"
    elif approval == "pending":
        base_query += " AND a.approval IS NULL"

    count_query = "SELECT COUNT(*) AS cnt FROM (" + base_query + ") AS sub"
    cur.execute(count_query, params)
    total = cur.fetchone()["cnt"]

    base_query += " ORDER BY a.assignment_id DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])

    cur.execute(base_query, params)
    all_assignments = cur.fetchall()
    cur.close()
    conn.close()

    total_pages = (total + per_page - 1) // per_page
    return render_template("assignments_list.html",
        assignments=all_assignments,
        total=total,
        current_page=page,
        total_pages=total_pages,
        q=q,
        approval=approval)

@app.route("/assignments/new", methods=["GET"])
def assignment_new():
    if session.get("role") != "farm_manager":
        return redirect(url_for('login'))
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT equipment_id, equipment_name, brand, model, status, required_certification
        FROM equipments 
        WHERE status != 'Broken'
        ORDER BY equipment_name
    """)
    equipments = cur.fetchall()
    cur.execute("SELECT operator_id, operator_name, certificate_type FROM operators ORDER BY certificate_type , operator_name")
    operators = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("assignment_form.html", equipments=equipments, operators=operators)


@app.route("/assignments/new", methods=["POST"])
def assignment_new_post():

    if session.get("role") != "farm_manager":
        return redirect(url_for('login'))

    op_id = request.form.get("op_id")
    eq_id = request.form.get("equipment_id")

    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


    cur.execute("""
        SELECT o.certificate_type, e.required_certification 
        FROM operators o, equipments e 
        WHERE o.operator_id = %s AND e.equipment_id = %s
    """, (op_id, eq_id))
    check = cur.fetchone()


    if not check or check["certificate_type"] != check["required_certification"]:
        flash("Assignment failed: Operator certification does not match equipment requirement.")
        cur.close()
        conn.close()
        return redirect(url_for('assignment_new'))


    cur.execute("""
        INSERT INTO assignments (equipment_id, op_id, time_period, approval)
        VALUES (%s, %s, %s, %s)
    """, (
        eq_id,
        op_id,
        request.form["time_period"] or None,
        request.form.get("approval") == "true" if request.form.get("approval") else None
    ))

    conn.commit()
    cur.close()
    conn.close()


    return redirect(url_for('assignments'))

@app.route("/assignments/delete/<int:assignment_id>", methods=["POST"])
def assignment_delete(assignment_id):
    if session.get("role") != "farm_manager":
        return redirect(url_for('login'))
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM assignments WHERE assignment_id = %s", (assignment_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('assignments'))


@app.route("/api/check-certification", methods=["GET"])
def check_certification():
    op_id = request.args.get("op_id")
    eq_id = request.args.get("eq_id")
    if not op_id or not eq_id:
        return {"status": "ok"}

    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT o.certificate_type, o.certificate_no, o.certificate_expiry_date,
               e.required_certification
        FROM operators o, equipments e
        WHERE o.operator_id = %s AND e.equipment_id = %s
    """, (op_id, eq_id))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return {"status": "ok"}


    if not row["certificate_no"]:
        return {"status": "error", "message": "This operator does not have a certificate."}


    if row["certificate_expiry_date"] and row["certificate_expiry_date"].strftime("%Y-%m-%d") < date.today().strftime(
            "%Y-%m-%d"):
        return {"status": "warning", "message": f"Certification expired on: {row['certificate_expiry_date']}"}


    if row["certificate_type"] != row["required_certification"]:
        return {"status": "warning",
                "message": f"Certification mismatch — Operator: {row['certificate_type']}, Equipment Requirement: {row['required_certification']}"}


    return {"status": "ok", "message": "Certification is valid."}

@app.route("/queries", methods=["GET"])
def queries():
    return render_template("queries.html", results={})
@app.route("/queries/1", methods=["GET"])
def queries_1():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT e.equipment_id, e.equipment_name, "
                "COUNT(m.maintenance_id) AS maintenance_count "
                "FROM equipments e LEFT JOIN maintenance m "
                "ON e.equipment_id = m.equipment_id GROUP BY e.equipment_id,"
                " e.equipment_name ORDER BY maintenance_count DESC LIMIT 10; ")



    equipment_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q1" : equipment_query})


@app.route("/queries/2", methods=["GET"])
def queries_2():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT 
            u.user_name || ' ' || u.user_surname AS technician_full_name, 
            u.email,
            COUNT(m.maintenance_id) AS maintenance_count 
        FROM users u 
        LEFT JOIN maintenance m ON u.user_id = m.technician_id 
        WHERE u.user_role = 'technician'
        GROUP BY u.user_id, u.user_name, u.user_surname, u.email 
        ORDER BY maintenance_count DESC 
        LIMIT 10;
    """)
    technician_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q2": technician_query})
@app.route("/queries/3", methods=["GET"])
def queries_3():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT m.maintenance_id, e.equipment_id, e.equipment_name, m.date_from, m.cost "
                "FROM equipments e LEFT JOIN maintenance m "
                "ON e.equipment_id = m.equipment_id "
                "WHERE m.cost IS NOT NULL "
                "ORDER BY m.cost DESC LIMIT 10;")
    highest_cost_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q3": highest_cost_query})

@app.route("/queries/4", methods=["GET"])
def queries_4():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT c.component_name, c.category, COUNT(mc.maintenance_id) AS usage_count "
                "FROM components c LEFT JOIN maintenance_component mc "
                "ON c.component_id = mc.component_id "
                "GROUP BY c.component_id, c.component_name, c.category "
                "ORDER BY usage_count DESC LIMIT 10;")
    cmp_usage_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q4": cmp_usage_query})


@app.route("/queries/5", methods=["GET"])
def queries_5():
    if session.get("role") != "farm_manager":
        return redirect(url_for('dashboard'))

    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


    cur.execute("""
        SELECT TO_CHAR(date_from, 'YYYY-MM') AS month, 
               COUNT(maintenance_id) AS count, 
               SUM(cost) AS total_cost 
        FROM maintenance 
        WHERE date_from IS NOT NULL 
        GROUP BY month 
        ORDER BY month DESC 
        LIMIT 12;
    """)

    trend_query = cur.fetchall()
    cur.close()
    conn.close()


    return render_template("queries.html", results={"q5": trend_query})


@app.route("/queries/6", methods=["GET"])
def queries_6():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


    cur.execute("""
        SELECT e.type, 
               COUNT(m.maintenance_id) AS count, 
               AVG(EXTRACT(EPOCH FROM (m.date_to::timestamp - m.date_from::timestamp)) / 86400)::float AS avg_days 
        FROM equipments e 
        JOIN maintenance m ON e.equipment_id = m.equipment_id 
        WHERE m.date_from IS NOT NULL AND m.date_to IS NOT NULL 
        GROUP BY e.type 
        ORDER BY avg_days DESC 
        LIMIT 10;
    """)

    duration_query = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("queries.html", results={"q6": duration_query})
@app.route("/queries/7", methods=["GET"])
def queries_7():
    if session.get("role") != "farm_manager":
        return redirect(url_for('dashboard'))
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT 
            a.assignment_id,
            o.operator_name,
            o.certificate_type,
            o.certificate_expiry_date,
            e.equipment_name,
            e.required_certification,
            a.time_period,
            CASE 
                WHEN o.certificate_no IS NULL THEN 'No Certificate'
                WHEN o.certificate_expiry_date < CURRENT_DATE THEN 'Expired'
                WHEN o.certificate_type != e.required_certification THEN 'Type Mismatch'
                ELSE 'Compliant'
            END AS compliance_status
        FROM assignments a
        JOIN operators o ON a.op_id = o.operator_id
        JOIN equipments e ON a.equipment_id = e.equipment_id
        WHERE o.certificate_no IS NULL
           OR o.certificate_expiry_date < CURRENT_DATE
           OR o.certificate_type != e.required_certification
        ORDER BY a.assignment_id DESC
        LIMIT 20;
    """)
    compliance_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q7": compliance_query})


if __name__ == '__main__':
    app.run()

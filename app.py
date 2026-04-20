import math

from flask import Flask, render_template, session, request, redirect, url_for
import psycopg2.extras



app = Flask(__name__)
app.secret_key = '823607-Buse'

def connect_db():
    conn= psycopg2.connect(
        host="localhost",
        database="farm_eq_maintenance",
        user="buseeksi",
        password="823607"
    )
    return conn


@app.route("/dashboard")
def dashboard():
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
        "my_tasks": 0,
        "my_pending": 0,
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
    cur = conn.cursor()
    name= request.form['name']
    surname= request.form['surname']
    password= request.form['password']
    role= "user"
    email= request.form['email']

    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    exists = cur.fetchone()
    if exists:
        print("User already exists")
        cur.close()
        conn.close()
        return redirect(url_for('dashboard'))
    else:
        cur.execute("INSERT INTO users (user_name, user_surname, user_password, user_role, email) VALUES (%s, %s, %s, %s, %s)",
                    (name, surname, password, role, email))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('dashboard'))
@app.route('/', methods=['GET'])
def login():
    return render_template("home.html")
@app.route("/login", methods=["POST"])
def login_form():
    email = request.form["email"]
    session["email"] = email
    password = request.form["password"]
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE email = %s and user_password = %s ", (email, password))
    exist = cur.fetchone()
    if exist:
        session["logged_in"] = True
        session["username"] = exist["user_name"]
        session["role"] = exist["user_role"]

        cur.close()
        conn.close()

        return redirect(url_for('dashboard'))
    else:
        cur.close()
        conn.close()
        return redirect(url_for('dashboard'))

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
        query += " AND status = %s::equipment_status"
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

    return render_template("equipment_list.html", equipment=items, total=total_count,
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
    if session.get("logged_in") and session.get("role") == "admin":
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
    if session.get("logged_in") and session.get("role") == "admin" and request.method == "POST":
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
               o.operator_name
        FROM maintenance m
        LEFT JOIN operators o ON m.operator_id = o.operator_id
        WHERE m.equipment_id = %s
        ORDER BY m.date_from DESC
    """, (equipment_id,))
    maintenance_history = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("equipment_detail.html" , maintenance_history=maintenance_history, equipment=equipment, maint_count=maint_count,
                           total_cost=total_cost,
                           last_maint=last_maint,)

@app.route("/maintenance", methods=["GET"])
def maintenance():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    page = int(request.args.get("page", 1))
    offset = (page - 1) * 10

    query = """
        SELECT m.*, e.equipment_name 
        FROM maintenance m
        JOIN equipments e ON m.equipment_id = e.equipment_id
        WHERE 1=1
    """

    params = []
    if q:
        query += " AND equipment_name ILIKE %s"
        params.append(f"%{q}%")
    if status:
        query += " AND m.status = %s"
        params.append(status)
    if date_from:
        query += " AND m.date_from >= %s::date"
        params.append(date_from)
    if date_to:
        query += " AND m.date_to <= %s::date"
        params.append(date_to)


    count_query = "SELECT COUNT(*) AS cnt FROM (" + query + ") AS sub"
    cur.execute(count_query, params)
    total_count = cur.fetchone()["cnt"]
    pages = math.ceil(total_count / 10) if total_count else 1


    query += " ORDER BY m.date_from DESC LIMIT 10 OFFSET %s"
    params.append(offset)

    cur.execute(query, params)
    items = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("maintenance_list.html", maintenance=items, total=total_count,
                           total_pages=pages, current_page=page)

@app.route("/maintenance/new", methods=["GET"])
def maintenance_new():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT equipment_id , equipment_name, type FROM equipments ORDER BY equipment_id DESC")
    equipments = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("maintenance_form.html" , equipments=equipments)
@app.route("/maintenance/new", methods=["POST"])
def maintenance_new_form():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("INSERT INTO maintenance (status,  equipment_id, description, operator_id, cost, notes, date_from) "
                "VALUES (%s, %s, %s, %s, %s, %s ,%s)", (request.form["status"],
                                                        request.form["equipment_id"],
                                                        request.form["description"],
                                                        request.form["operator_id"] or None,
                                                        request.form["cost"] or None,
                                                        request.form["notes"] or None,
                                                        request.form["date_from"]))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('maintenance'))

@app.route("/maintenance/delete/<int:maintenance_id>", methods=["POST"])
def maintenance_delete(maintenance_id):
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("DELETE FROM maintenance WHERE maintenance_id = %s", (maintenance_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('maintenance'))

@app.route("/maintenance/edit/<int:maintenance_id>", methods=["GET","POST"])
def maintenance_edit(maintenance_id):
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT equipment_id , equipment_name, type FROM equipments ORDER BY equipment_id DESC")
    equipments = cur.fetchall()
    cur.execute("SELECT operator_id, operator_name FROM operators ORDER BY operator_id DESC")
    operators = cur.fetchall()
    if request.method == "POST":
        status = request.form["status"]
        equipment_id = request.form["equipment_id"]
        description = request.form["description"]
        date_from = request.form["date_from"]
        operator_id = request.form["operator_id"] or None
        cost = request.form["cost"] or None
        notes = request.form["notes"] or None
        cur.execute("UPDATE maintenance SET equipment_id = %s , status= %s ,description = %s,"
                        " date_from = %s , operator_id = %s , cost = %s ,notes = %s WHERE maintenance_id = %s",
                    (equipment_id, status, description, date_from, operator_id, cost, notes, maintenance_id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('maintenance'))
    else:
        cur.execute("SELECT * FROM maintenance WHERE maintenance_id = %s", (maintenance_id,))
        maintenance = cur.fetchone()
        cur.close()
        conn.close()
        return render_template("maintenance_form.html", maintenance=maintenance, equipments=equipments, operators=operators)

@app.route("/components", methods=["GET"])
def components():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM components ORDER BY component_id DESC")
    components = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("component.html" , components=components)

@app.route("/components/new", methods=["GET"])
def component_new():
    if session.get("role") == 'admin':
        return render_template("component_form.html")
    else:
        return redirect(url_for('login'))

@app.route("/components/new", methods=["POST"])
def component_new_form():
    if session.get("role") == 'admin':
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
    if session.get("role") == 'admin':
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
    if session.get("role") == 'admin':
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
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT o.*, COUNT(m.maintenance_id) AS maintenance_count
        FROM operators o
        LEFT JOIN maintenance m ON o.operator_id = m.operator_id
        GROUP BY o.operator_id
        ORDER BY o.operator_id DESC
    """)
    all_operators = cur.fetchall()
    total = len(all_operators)
    cur.close()
    conn.close()
    return render_template("operators_list.html", operators=all_operators, total=total)

@app.route("/operators/new", methods=["GET"])
def operators_new():
    if session.get("role") == 'admin':
        return render_template("operator_form.html")
    else:
        return redirect(url_for('login'))

@app.route("/operators/new", methods=["POST"])
def operator_new_form():
    if session.get("role") == 'admin':
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        operator_name = request.form["operator_name"]
        certificate_no = request.form["certificate_no"] or None
        certificate_type = request.form["certificate_type"] or None
        hire_date = request.form["hire_date"] or None
        phone= request.form["phone"] or None
        email = request.form["email"] or None
        cur.execute(
        "INSERT INTO operators (operator_name, certificate_no, certificate_type, hire_date, phone, email)"
                "VALUES(%s, %s, %s, %s, %s, %s)",
        (operator_name, certificate_no, certificate_type, hire_date, phone, email))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('operators'))
    else:
        return redirect(url_for('login'))

@app.route("/operators/edit/<int:operator_id>", methods=["GET","POST"])
def operator_edit(operator_id):
    if session.get("role") == 'admin':
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
    if session.get("role") == 'admin':
        conn = connect_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("DELETE FROM operators WHERE operator_id = %s", (operator_id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('operators'))
    else:
        return redirect(url_for('login'))



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
                "ON e.equipment_id = m.equipment_id GROUP BY e.equipment_id, e.equipment_name;")
    equipment_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q1" : equipment_query})

@app.route("/queries/2", methods=["GET"])
def queries_2():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT o.operator_name as operator_name, o.certificate_no,"
                "COUNT(m.maintenance_id) AS maintenance_count "
                "FROM operators o LEFT JOIN maintenance m ON o.operator_id = m.operator_id "
                "GROUP BY o.operator_id, o.operator_name ORDER BY o.operator_id;")
    operator_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q2" : operator_query})

@app.route("/queries/3", methods=["GET"])
def queries_3():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT m.maintenance_id, e.equipment_id, e.equipment_name, m.date_from, m.cost "
                "FROM equipments e LEFT JOIN maintenance m "
                "ON e.equipment_id = m.equipment_id "
                "WHERE m.cost IS NOT NULL "
                "ORDER BY m.cost DESC;")
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
                "ORDER BY usage_count DESC;")
    cmp_usage_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q4": cmp_usage_query})

@app.route("/queries/5", methods=["GET"])
def queries_5():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT TO_CHAR(date_from, 'YYYY-MM') AS month, "
                "COUNT(*) AS count, "
                "SUM(cost) AS total_cost "
                "FROM maintenance "
                "WHERE date_from >= NOW() - INTERVAL '12 months' "
                "GROUP BY month "
                "ORDER BY month ASC;")
    trend_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q5": trend_query})

@app.route("/queries/6", methods=["GET"])
def queries_6():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT e.type, "
                "COUNT(m.maintenance_id) AS count, "
                "AVG(m.date_to - m.date_from) AS avg_days "
                "FROM equipments e LEFT JOIN maintenance m "
                "ON e.equipment_id = m.equipment_id "
                "WHERE m.date_from IS NOT NULL AND m.date_to IS NOT NULL "
                "GROUP BY e.type "
                "ORDER BY avg_days DESC;")
    duration_query = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("queries.html", results={"q6": duration_query})


if __name__ == '__main__':
    app.run()

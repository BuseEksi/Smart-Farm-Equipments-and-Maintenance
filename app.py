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

@app.route('/')
def home():
    return render_template('home.html')


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
        return redirect(url_for('home'))
    else:
        cur.execute("INSERT INTO users (user_name, user_surname, user_password, user_role, email) VALUES (%s, %s, %s, %s, %s)",
                    (name, surname, password, role, email))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('home'))

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

        return redirect(url_for('home'))
    else:
        cur.close()
        conn.close()
        return redirect(url_for('home'))

@app.route("/logout")
def logout():
    session.pop("email", None)
    session.pop("logged_in", None)
    return redirect(url_for('home'))

@app.route("/equipment", methods=["GET"])
def equipment():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    q= request.args.get("q" , "")
    status = request.args.get("status", "")
    type_ = request.args.get("type", "")

    query = "SELECT * FROM equipments WHERE 1=1"

    params = []
    if q:
        query += " AND equipment_name ILIKE %s"
        params.append(f"%{q}%")
    if status:
        query += " AND status = %s"
        params.append(status)
    if type_:
        query += " AND type = %s"
        params.append(type_)

    cur.execute(query, params)
    items = cur.fetchall()
    total_count = len(items)
    pages = math.ceil(total_count / 10)
    equipment_types = ['Agriculture', 'Harvesting', 'Irrigation', 'Pest Control', 'Transportation', 'Other']

    return render_template("equipment_list.html" , equipment=items , total=total_count,
                           total_pages=pages, current_page=1, equipment_types=equipment_types)

@app.route("/equipment/new", methods=["GET"])
def equipment_new():
    if session["logged_in"]:
        return render_template("equipment_form.html")

@app.route("/equipment/new", methods=["POST"])
def equipment_new_post():
    if session["logged_in"]:
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

@app.route("/equipment/edit/<int:equipment_id>", methods=["GET", "POST"])
def equipment_edit(equipment_id):
    if session["logged_in"] and session["role"] == "admin":
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

@app.route("/equipment/delete/<int:equipment_id>", methods=["POST"])
def equipment_delete(equipment_id):
    if session["logged_in"] and session["role"] == "admin" and request.method == "POST":
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM equipments WHERE equipment_id = %s", (equipment_id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('equipment'))

@app.route("/maintenance", methods=["GET"])
def maintenance():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

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
        query += " AND status = %s"
        params.append(status)
    if date_from:
        query += " AND date_from = %s"
        params.append(date_from)
    if date_to:
        query += " AND date_to = %s"
        params.append(date_to)

    cur.execute(query, params)
    items = cur.fetchall()
    total_count = len(items)
    pages = math.ceil(total_count / 10)


    return render_template("maintenance_list.html", maintenance=items, total=total_count,
                           total_pages=pages, current_page=1)

@app.route("/maintenance/new", methods=["GET"])
def maintenance_new():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT equipment_id , equipment_name, type FROM equipments ORDER BY equipment_id DESC")
    equipments = cur.fetchall()
    return render_template("maintenance_form.html" , equipments=equipments)
@app.route("/maintenance/new", methods=["POST"])
def maintenance_new_form():
    conn = connect_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("INSERT INTO maintenance (status,  equipment_id, description, operator_id, cost, notes, maintenance_date) "
                "VALUES (%s, %s, %s, %s, %s, %s ,%s)",(request.form["status"],
                                               request.form["equipment_id"],
                                               request.form["description"],
                                               request.form["operator_id"] or None,
                                               request.form["cost"] or None,
                                               request.form["notes"] or None,
                                               request.form["maintenance_date"]) )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('maintenance'))


if __name__ == '__main__':
    app.run()

import os
import psycopg2
import psycopg2.extras
import io
import sqlite3
import fitz
from datetime import datetime, date, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, g, send_file, jsonify
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
try:
    from pypdf import PdfReader, PdfWriter
except Exception:
    from PyPDF2 import PdfReader, PdfWriter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ccm_performance_software.db")
LOGO_PATH = os.path.join(BASE_DIR, "static", "logo.png")

app = Flask(__name__)
app.secret_key = "ccm-ultra-secret-2026"

def get_db():
    if 'db' not in g:
        DATABASE_URL = os.environ.get("DATABASE_URL")
        g.db = psycopg2.connect(DATABASE_URL)
    return g.db

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        id SERIAL PRIMARY KEY,
        name TEXT,
        plate TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id SERIAL PRIMARY KEY,
        name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id SERIAL PRIMARY KEY,
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS damages (
        id SERIAL PRIMARY KEY,
    )
    """)

    db.commit()
@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def sync_default_vehicle_prices():
    db = psycopg2.connect(os.environ.get("DATABASE_URL"))
    cur = db.cursor()
    updates = [
        ("AC CM 6660", 500, 900, 1000, 4500, 2000, 3000),
        ("AC CM 6606", 500, 900, 1000, 4500, 2000, 3000),
        ("AC CM 3330", 250, 600, 700, 2699, 1000, 2000),
        ("AC CM 8808", 300, 800, 900, 4000, 2000, 3000),
        ("AC CM 8080", 95, 280, 300, 1500, 500, 1000),
        ("AC CM 8081", 110, 299, 319, 1800, 500, 1000),
    ]
    for plate, daily_price, four_day_price, weekend_price, monthly_price, deposit_short, deposit_month in updates:
        cur.execute("""
            UPDATE vehicles
            SET daily_price=?, four_day_price=?, weekend_price=?, monthly_price=?, deposit_short=?, deposit_month=?
            WHERE plate=?
        """, (daily_price, four_day_price, weekend_price, monthly_price, deposit_short, deposit_month, plate))
    db.commit()
    db.close()

def init_db():
    db = psycopg2.connect(os.environ.get("DATABASE_URL"))
    cur = db.cursor()

    # FIX OLD DATABASE COLUMNS
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS daily_price REAL DEFAULT 0")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS four_day_price REAL DEFAULT 0")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS weekend_price REAL DEFAULT 0")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS monthly_price REAL DEFAULT 0")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS deposit_short REAL DEFAULT 0")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS deposit_month REAL DEFAULT 0")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS km_day INTEGER DEFAULT 150")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS km_offer INTEGER DEFAULT 350")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS km_month INTEGER DEFAULT 1000")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Frei'")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS image_link TEXT")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS color_tag TEXT DEFAULT ''")
    cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS note TEXT DEFAULT ''")

    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS first_name TEXT DEFAULT ''")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_name TEXT DEFAULT ''")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS phone TEXT")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS email TEXT")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS address TEXT")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS birth_date TEXT")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS license_no TEXT")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS license_checked TEXT DEFAULT 'Nein'")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS license_link TEXT")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS id_link TEXT")
    cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS note TEXT")

    cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS vehicle_id INTEGER")
    cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS customer_id INTEGER")
    cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS start_date TEXT")
    cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS pickup_time TEXT")
    cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS end_date TEXT")
    cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS return_time TEXT")    # USERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # VEHICLES
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vehicles(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        plate TEXT NOT NULL,
        daily_price REAL NOT NULL,
        four_day_price REAL NOT NULL,
        weekend_price REAL NOT NULL,
        monthly_price REAL NOT NULL,
        deposit_short REAL NOT NULL,
        deposit_month REAL NOT NULL,
        km_day INTEGER NOT NULL DEFAULT 150,
        km_offer INTEGER NOT NULL DEFAULT 350,
        km_month INTEGER NOT NULL DEFAULT 1000,
        status TEXT NOT NULL DEFAULT 'Frei',
        image_link TEXT,
        color_tag TEXT DEFAULT '',
        note TEXT DEFAULT ''
    )
    """)

    # CUSTOMERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers(
        id SERIAL PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        birth_date TEXT,
        license_no TEXT,
        license_checked TEXT DEFAULT 'Nein',
        license_link TEXT,
        id_link TEXT,
        note TEXT
    )
    """)

    # BOOKINGS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings(
        id SERIAL PRIMARY KEY,
        vehicle_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        pickup_time TEXT,
        end_date TEXT NOT NULL,
        return_time TEXT,
        special_price REAL,
        special_reason TEXT,
        extra_km REAL DEFAULT 0,
        deposit_status TEXT DEFAULT 'nicht bezahlt',
        pickup_km REAL,
        return_km REAL,
        pickup_fuel TEXT,
        return_fuel TEXT,
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(id),
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )
    """)

    # RESERVATIONS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reservations(
        id SERIAL PRIMARY KEY,
        customer_name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        vehicle_name TEXT,
        start_date TEXT,
        end_date TEXT,
        pickup_time TEXT,
        return_time TEXT,
        status TEXT DEFAULT 'offen',
        source TEXT DEFAULT 'Telefon / WhatsApp',
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # DAMAGES
    cur.execute("""
    CREATE TABLE IF NOT EXISTS damages(
        id SERIAL PRIMARY KEY,
        vehicle_id INTEGER NOT NULL,
        customer_id INTEGER,
        description TEXT NOT NULL,
        location_on_vehicle TEXT,
        cost REAL DEFAULT 0,
        file_link TEXT,
        status TEXT DEFAULT 'offen',
        note TEXT,
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(id),
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )
    """)

    # SETTINGS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    # DEFAULT ADMIN
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users(username, password) VALUES (%s, %s)",
            ("admin", "ccm123")
        )

    # DEFAULT VEHICLES
    cur.execute("SELECT COUNT(*) FROM vehicles")
    if cur.fetchone()[0] == 0:
        vehicles = [
            ("Audi RS6 Performance (blue)", "AC CM 6660", 500, 900, 1000, 4500, 2000, 3000, 150, 350, 1000, "Frei", "", "blue", ""),
            ("Audi RS6 Performance (black)", "AC CM 6666", 500, 900, 1000, 4500, 2000, 3000, 150, 350, 1000, "Frei", "", "black", ""),
            ("Audi RS3 Sportback", "AC CM 3330", 250, 600, 700, 2699, 1000, 2000, 150, 350, 1000, "Frei", "", "", ""),
            ("Audi RSQ8 (blue)", "AC CM 8880", 300, 800, 900, 4000, 2000, 3000, 150, 350, 1000, "Frei", "", "blue", ""),
            ("VW GTI", "AC CM 8080", 95, 280, 300, 1500, 500, 1000, 150, 350, 1000, "Frei", "", "", ""),
            ("VW GTI Clubsport", "AC CM 8081", 110, 299, 319, 1800, 500, 1000, 150, 350, 1000, "Frei", "", "", "")
        ]

        cur.executemany("""
        INSERT INTO vehicles(
            name,
            plate,
            daily_price,
            four_day_price,
            weekend_price,
            monthly_price,
            deposit_short,
            deposit_month,
            km_day,
            km_offer,
            km_month,
            status,
            image_link,
            color_tag,
            note
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, vehicles)

    db.commit()
    cur.close()
    db.close()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()

def contract_no(booking_id):
    return f"CCM-2026-{booking_id:03d}"

def invoice_no(booking_id):
    return f"CCM-RG-2026-{booking_id:03d}"

def get_setting(key, default=""):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT value FROM settings WHERE key=%s", (key,))
    row = cur.fetchone()
    return row[0] if row else default

def wrap_text(text, max_chars=90):
    words = str(text).split()
    lines = []
    line = []
    for word in words:
        test = " ".join(line + [word])
        if len(test) > max_chars and line:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))
    return lines

def draw_wrapped_lines(c, lines, x, y, width_chars=90, font="Helvetica", size=9, leading=12):
    c.setFont(font, size)
    for entry in lines:
        sublines = wrap_text(entry, width_chars) if isinstance(entry, str) else [str(entry)]
        for sub in sublines:
            c.drawString(x, y, sub)
            y -= leading
    return y

def calculate_price(row):
    start = parse_date(row["start_date"])
    end = parse_date(row["end_date"])
    days = (end - start).days + 1
    weekday = start.weekday()

    if row["special_price"] not in (None, "", 0):
        tariff = "Sonderpreis"
        rent = float(row["special_price"])
        deposit = float(row["deposit_short"])
        km = int(row["km_offer"])
    elif days >= 28:
        tariff = "Monat"
        rent = float(row["monthly_price"])
        deposit = float(row["deposit_month"])
        km = int(row["km_month"])
    elif days == 4:
        tariff = "4 Tage"
        rent = float(row["four_day_price"])
        deposit = float(row["deposit_short"])
        km = int(row["km_offer"])
    elif weekday == 4 and days == 3:
        tariff = "Fr-So"
        rent = float(row["weekend_price"])
        deposit = float(row["deposit_short"])
        km = int(row["km_offer"])
    else:
        tariff = "Tag"
        rent = float(row["daily_price"]) * days
        deposit = float(row["deposit_short"])
        km = int(row["km_day"]) * days

    extra = float(row["extra_km"] or 0)
    extra_price = extra * 1.0
    total = rent + extra_price
    profit = total * 0.85
    return {
        "days": days,
        "tariff": tariff,
        "rent": round(rent, 2),
        "deposit": round(deposit, 2),
        "extra_price": round(extra_price, 2),
        "total": round(total, 2),
        "profit": round(profit, 2),
        "included_km": km
    }

def fetch_bookings_full():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT b.*,
               v.name AS vehicle_name, v.plate, v.image_link, v.color_tag, v.status AS vehicle_status,
               v.daily_price, v.four_day_price, v.weekend_price, v.monthly_price,
               v.deposit_short, v.deposit_month, v.km_day, v.km_offer, v.km_month,
               c.first_name || ' ' || c.last_name AS customer_name,
               c.phone, c.email, c.address, c.license_no, c.license_checked
        FROM bookings b
        JOIN vehicles v ON v.id=b.vehicle_id
        JOIN customers c ON c.id=b.customer_id
        ORDER BY b.start_date DESC, b.id DESC
    """)
    return cur.fetchall()

def monthly_revenue(bookings):
    vals = {m: 0 for m in range(1, 13)}
    for row in bookings:
        calc = calculate_price(row)
        vals[parse_date(row["start_date"]).month] += calc["total"]
    return vals

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        
        db = get_db()
        cur = db.cursor()
        
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u, p))
        rows = cur.fetchone()        
        if row:
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            return redirect(url_for("dashboard"))
        flash("Login falsch.")
    return render_template("login.html", title="Login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) FROM vehicles")
    vehicles_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM customers")
    customers_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM bookings")
    bookings_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM damages")
    damages_count = cur.fetchone()[0]

    totals = {
        "vehicles": vehicles_count,
        "customers": customers_count,
        "bookings": bookings_count,
        "damages": damages_count,
    }

    bookings = fetch_bookings_full()
    revenue = 0
    profit = 0
    recent = []

    for row in bookings[:8]:
        calc = calculate_price(row)
        revenue += calc["total"]
        profit += calc["profit"]
        recent.append({"row": row, "calc": calc, "contract_no": contract_no(row["id"])})

    cur.execute("SELECT * FROM vehicles ORDER BY name")
    vehicle_status = cur.fetchall()

    month_vals = monthly_revenue(bookings)
    max_val = max(month_vals.values()) if month_vals else 0

    month_data = []
    month_names = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

    for i in range(1, 13):
        v = month_vals[i]
        pct = 0 if max_val == 0 else max(6, int(v / max_val * 100))
        month_data.append({"label": month_names[i - 1], "value": round(v, 2), "pct": pct})

    util = []

    for v in vehicle_status:
        cur.execute("SELECT COUNT(*) FROM bookings WHERE vehicle_id=%s", (v[0],))
        count = cur.fetchone()[0]
        util.append({"name": v[1], "count": count})

    return render_template(
        "dashboard.html",
        title="Dashboard",
        totals=totals,
        revenue=revenue,
        profit=profit,
        recent=recent,
        vehicle_status=vehicle_status,
        month_data=month_data,
        util=util
    )@app.route("/vehicles", methods=["GET", "POST"])
@login_required
def vehicles():
    db = get_db()
    if request.method == "POST":
        db.execute("""
            INSERT INTO vehicles(
                name, plate, daily_price, four_day_price, weekend_price, monthly_price,
                deposit_short, deposit_month, km_day, km_offer, km_month, status, image_link, color_tag, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form.get("name", ""), request.form.get("plate", ""), request.form.get("daily_price", ""),
            request.form.get("four_day_price", ""), request.form.get("weekend_price", ""), request.form.get("monthly_price", ""),
            request.form.get("deposit_short", ""), request.form.get("deposit_month", ""), request.form.get("km_day", 150),
            request.form.get("km_offer", 350), request.form.get("km_month", 1000),
            request.form.get("status", "Frei"), request.form.get("image_link", ""), request.form.get("color_tag", ""), request.form.get("note", "")
        ))
        db.commit()
        flash("Fahrzeug gespeichert.")
        return redirect(url_for("vehicles"))
    items = db.execute("SELECT * FROM vehicles ORDER BY name").fetchall()
    return render_template("vehicles.html", title="Fahrzeuge", items=items)

@app.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    db = get_db()
    if request.method == "POST":
        db.execute("""
            INSERT INTO customers(
                first_name,last_name,phone,email,address,birth_date,license_no,
                license_checked,license_link,id_link,note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form.get("first_name", ""), request.form.get("last_name", ""), request.form.get("phone", ""),
            request.form.get("email", ""), request.form.get("address", ""), request.form.get("birth_date", ""),
            request.form.get("license_no", ""), request.form.get("license_checked", "Nein"),
            request.form.get("license_link", ""), request.form.get("id_link", ""), request.form.get("note", "")
        ))
        db.commit()
        flash("Kunde gespeichert.")
        return redirect(url_for("customers"))

    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        items = db.execute("""
            SELECT * FROM customers
            WHERE first_name LIKE ? OR last_name LIKE ? OR phone LIKE ? OR email LIKE ? OR license_no LIKE ?
            ORDER BY last_name, first_name
        """, (like, like, like, like, like)).fetchall()
    else:
        items = db.execute("SELECT * FROM customers ORDER BY last_name, first_name").fetchall()

    return render_template("customers.html", title="Kunden", items=items, edit_item=None, q=q)


@app.route("/customers/edit/<int:customer_id>", methods=["GET", "POST"])
@login_required
def customer_edit(customer_id):
    db = get_db()
    item = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if not item:
        flash("Kunde nicht gefunden.")
        return redirect(url_for("customers"))

    if request.method == "POST":
        db.execute("""
            UPDATE customers
            SET first_name=?, last_name=?, phone=?, email=?, address=?, birth_date=?,
                license_no=?, license_checked=?, license_link=?, id_link=?, note=?
            WHERE id=?
        """, (
            request.form.get("first_name", ""), request.form.get("last_name", ""), request.form.get("phone", ""),
            request.form.get("email", ""), request.form.get("address", ""), request.form.get("birth_date", ""),
            request.form.get("license_no", ""), request.form.get("license_checked", "Nein"),
            request.form.get("license_link", ""), request.form.get("id_link", ""), request.form.get("note", ""),
            customer_id
        ))
        db.commit()
        flash("Kunde aktualisiert.")
        return redirect(url_for("customers"))

    items = db.execute("SELECT * FROM customers ORDER BY last_name, first_name").fetchall()
    return render_template("customers.html", title="Kunden", items=items, edit_item=item, q="")

@app.route("/customers/delete/<int:customer_id>", methods=["POST"])
@login_required
def customer_delete(customer_id):
    db = get_db()
    item = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if not item:
        flash("Kunde nicht gefunden.")
        return redirect(url_for("customers"))

    booking_count = db.execute("SELECT COUNT(*) c FROM bookings WHERE customer_id=?", (customer_id,)).fetchone()["c"]
    damage_count = db.execute("SELECT COUNT(*) c FROM damages WHERE customer_id=?", (customer_id,)).fetchone()["c"]

    if booking_count > 0 or damage_count > 0:
        flash("Kunde kann nicht gelöscht werden, solange Buchungen oder Schäden verknüpft sind.")
        return redirect(url_for("customers"))

    db.execute("DELETE FROM customers WHERE id=?", (customer_id,))
    db.commit()
    flash("Kunde gelöscht.")
    return redirect(url_for("customers"))

@app.route("/bookings", methods=["GET", "POST"])
@login_required
def bookings():
    db = get_db()
    if request.method == "POST":
        db.execute("""
            INSERT INTO bookings(
                vehicle_id,customer_id,start_date,pickup_time,end_date,return_time,
                special_price,special_reason,extra_km,deposit_status,pickup_km,return_km,pickup_fuel,return_fuel,note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form.get("vehicle_id", ""), request.form.get("customer_id", ""), request.form.get("start_date", ""),
            request.form.get("pickup_time", ""), request.form.get("end_date", ""), request.form.get("return_time", ""),
            request.form.get("special_price") or None, request.form.get("special_reason", ""),
            request.form.get("extra_km") or 0, request.form.get("deposit_status", "nicht bezahlt"),
            request.form.get("pickup_km") or None, request.form.get("return_km") or None,
            request.form.get("pickup_fuel", ""), request.form.get("return_fuel", ""), request.form.get("note", "")
        ))
        db.commit()
        flash("Buchung gespeichert.")
        return redirect(url_for("bookings"))

    vehicles = db.execute("SELECT id, name FROM vehicles ORDER BY name").fetchall()
    customers = db.execute("SELECT id, first_name || ' ' || last_name AS full_name FROM customers ORDER BY last_name, first_name").fetchall()
    rows = fetch_bookings_full()
    items = []
    for row in rows:
        calc = calculate_price(row)
        items.append({"row": row, "calc": calc, "contract_no": contract_no(row["id"]), "invoice_no": invoice_no(row["id"])})
    return render_template("bookings.html", title="Buchungen", vehicles=vehicles, customers=customers, items=items, edit_item=None)

@app.route("/bookings/edit/<int:booking_id>", methods=["GET", "POST"])
@login_required
def booking_edit(booking_id):
    db = get_db()
    item = db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if not item:
        flash("Buchung nicht gefunden.")
        return redirect(url_for("bookings"))

    if request.method == "POST":
        db.execute("""
            UPDATE bookings
            SET vehicle_id=?, customer_id=?, start_date=?, pickup_time=?, end_date=?, return_time=?,
                special_price=?, special_reason=?, extra_km=?, deposit_status=?, pickup_km=?, return_km=?,
                pickup_fuel=?, return_fuel=?, note=?
            WHERE id=?
        """, (
            request.form.get("vehicle_id", ""), request.form.get("customer_id", ""), request.form.get("start_date", ""),
            request.form.get("pickup_time", ""), request.form.get("end_date", ""), request.form.get("return_time", ""),
            request.form.get("special_price") or None, request.form.get("special_reason", ""),
            request.form.get("extra_km") or 0, request.form.get("deposit_status", "nicht bezahlt"),
            request.form.get("pickup_km") or None, request.form.get("return_km") or None,
            request.form.get("pickup_fuel", ""), request.form.get("return_fuel", ""), request.form.get("note", ""),
            booking_id
        ))
        db.commit()
        flash("Buchung aktualisiert.")
        return redirect(url_for("bookings"))

    vehicles = db.execute("SELECT id, name FROM vehicles ORDER BY name").fetchall()
    customers = db.execute("SELECT id, first_name || ' ' || last_name AS full_name FROM customers ORDER BY last_name, first_name").fetchall()
    rows = fetch_bookings_full()
    items = []
    for row in rows:
        calc = calculate_price(row)
        items.append({"row": row, "calc": calc, "contract_no": contract_no(row["id"]), "invoice_no": invoice_no(row["id"])})
    return render_template("bookings.html", title="Buchungen", vehicles=vehicles, customers=customers, items=items, edit_item=item)

@app.route("/bookings/delete/<int:booking_id>", methods=["POST"])
@login_required
def booking_delete(booking_id):
    db = get_db()
    db.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    db.commit()
    flash("Buchung gelöscht.")
    return redirect(url_for("bookings"))

@app.route("/contracts")
@login_required
def contracts():
    items = []
    for row in fetch_bookings_full():
        calc = calculate_price(row)
        items.append({"row": row, "calc": calc, "contract_no": contract_no(row["id"]), "invoice_no": invoice_no(row["id"])})
    return render_template("contracts.html", title="Verträge", items=items)


@app.route("/reservations", methods=["GET", "POST"])
@login_required
def reservations():
    db = get_db()
    if request.method == "POST":
        db.execute("""
            INSERT INTO reservations(
                customer_name, phone, email, vehicle_name, start_date, end_date,
                pickup_time, return_time, status, source, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form.get("customer_name", ""),
            request.form.get("phone", ""),
            request.form.get("email", ""),
            request.form.get("vehicle_name", ""),
            request.form.get("start_date", ""),
            request.form.get("end_date", ""),
            request.form.get("pickup_time", ""),
            request.form.get("return_time", ""),
            request.form.get("status", "offen"),
            request.form.get("source", "Telefon / WhatsApp"),
            request.form.get("note", "")
        ))
        db.commit()
        flash("Reservierung gespeichert.")
        return redirect(url_for("reservations"))

    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    sql = """
        SELECT * FROM reservations
        WHERE 1=1
    """
    params = []
    if q:
        like = f"%{q}%"
        sql += " AND (customer_name LIKE ? OR phone LIKE ? OR email LIKE ? OR vehicle_name LIKE ? OR note LIKE ?)"
        params += [like, like, like, like, like]
    if status_filter:
        sql += " AND status = ?"
        params.append(status_filter)
    sql += """
        ORDER BY
            CASE status
                WHEN 'offen' THEN 1
                WHEN 'bestätigt' THEN 2
                WHEN 'erledigt' THEN 3
                WHEN 'storniert' THEN 4
                ELSE 5
            END,
            start_date ASC,
            id DESC
    """
    items = db.execute(sql, params).fetchall()
    vehicles = db.execute("SELECT name FROM vehicles ORDER BY name").fetchall()
    return render_template("reservations.html", title="Reservierungen", items=items, vehicles=vehicles, q=q, status_filter=status_filter)









@app.route("/calendar")
@login_required
def calendar():
    from datetime import datetime, timedelta

    db = get_db()
    vehicles = db.execute("SELECT * FROM vehicles ORDER BY name").fetchall()

    vehicle_id = request.args.get("vehicle_id")
    if not vehicle_id and vehicles:
        vehicle_id = str(vehicles[0]["id"])

    selected_vehicle = None
    if vehicle_id:
        selected_vehicle = db.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()

    start = request.args.get("start") or "2026-04-30"
    end = request.args.get("end") or "2026-05-14"

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    bookings = db.execute("SELECT * FROM bookings WHERE vehicle_id=?", (vehicle_id,)).fetchall()

    def val(row, keys):
        for k in keys:
            try:
                if row[k]:
                    return str(row[k])
            except Exception:
                pass
        return ""

    def booked_on(day):
        for b in bookings:
            s = val(b, ["start_date","start","pickup_date"])
            e = val(b, ["end_date","end","return_date"])
            if s and e and s <= day <= e:
                return "Gebucht"
        return "Frei"

    days = []
    tag = ["Mo","Di","Mi","Do","Fr","Sa","So"]
    d = start_dt

    while d <= end_dt:
        iso = d.strftime("%Y-%m-%d")
        days.append({
            "date": iso,
            "date_de": d.strftime("%d.%m.%Y"),
            "day_name": tag[d.weekday()],
            "status": booked_on(iso),
            "customer_name": ""
        })
        d += timedelta(days=1)

    return render_template("calendar.html", title="Kalender", vehicles=vehicles, selected_vehicle=selected_vehicle, days=days, start=start, end=end)



@app.route("/contracts/<int:contract_id>/pdf")
@login_required
def contract_pdf_auto(contract_id):
    import os
    import fitz
    from flask import send_file

    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id=?", (contract_id,)).fetchone()
    if not booking:
        return "Buchung nicht gefunden", 404

    customer = db.execute("SELECT * FROM customers WHERE id=?", (booking["customer_id"],)).fetchone()
    vehicle = db.execute("SELECT * FROM vehicles WHERE id=?", (booking["vehicle_id"],)).fetchone()

    template = "contracts/mietvertrag.pdf"
    if not os.path.exists(template):
        template = "contracts/fertig ccm.pdf"

    if not os.path.exists(template):
        return "Mietvertrag PDF nicht gefunden", 404

    output = f"/tmp/mietvertrag_{contract_id}.pdf"

    doc = fitz.open(template)
    page = doc[0]

    def get(row, names):
        for n in names:
            try:
                if row[n]:
                    return str(row[n])
            except Exception:
                pass
        return ""

    def write_label(label, text, dx=35):
        if not text:
            return
        hits = page.search_for(label)
        if not hits:
            return
        r = hits[0]
        page.insert_text(
            (r.x1 + dx, r.y1 - 3),
            str(text),
            fontsize=10,
            fontname="helv",
            color=(0,0,0)
        )

    customer_name = get(customer, ["name", "full_name"])
    if not customer_name:
        customer_name = (get(customer, ["first_name", "firstname", "vorname"]) + " " + get(customer, ["last_name", "lastname", "nachname"])).strip()

    write_label("Name:", customer_name)
    write_label("Adresse:", get(customer, ["address", "adresse", "street", "strasse"]))
    write_label("Geburtsdatum:", get(customer, ["birthdate", "birth_date", "geburtsdatum"]))
    write_label("Telefon:", get(customer, ["phone", "telefon", "mobile", "handy"]))
    write_label("E-Mail:", get(customer, ["email", "mail", "e_mail"]))
    write_label("Führerschein-Nr.:", get(customer, ["license_number", "license_no", "fuehrerschein", "führerschein"]))

    write_label("Fahrzeug:", get(vehicle, ["name", "vehicle_name", "fahrzeug"]))
    write_label("Kennzeichen:", get(vehicle, ["license_plate", "plate", "kennzeichen"]))

    write_label("Startdatum / Uhrzeit:", get(booking, ["start_date", "start", "pickup_date"]))
    write_label("Enddatum / Uhrzeit:", get(booking, ["end_date", "end", "return_date"]))
    write_label("Mietpreis gesamt:", get(booking, ["price", "total_price", "amount", "gesamtpreis"]))
    write_label("Kilometer:", get(booking, ["included_km", "km", "kilometer"]) or "350")
    write_label("Mehrkilometer Preis:", "1,00 €")
    write_label("Kaution:", get(booking, ["deposit", "kaution"]))

    doc.save(output)
    return send_file(output, mimetype="application/pdf", as_attachment=False)







@app.route("/settings")
@login_required
def settings_view():
    return "<h1 style='font-family:Arial;color:#ffd400;background:#050505;padding:40px'>Einstellungen</h1><p style='font-family:Arial;background:#050505;color:white;padding:40px'>Einstellungen aktiv.</p>"

@app.route("/vehicles/delete/<int:vehicle_id>", methods=["POST", "GET"])
@login_required
def vehicle_delete(vehicle_id):
    db = get_db()
    db.execute("DELETE FROM vehicles WHERE id=?", (vehicle_id,))
    db.commit()
    return redirect("/vehicles")

@app.route("/vehicles/edit/<int:vehicle_id>", methods=["GET", "POST"])
@login_required
def vehicle_edit(vehicle_id):
    db = get_db()
    vehicle = db.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()

    if request.method == "POST":
        cols = [r["name"] for r in db.execute("PRAGMA table_info(vehicles)").fetchall()]
        updates = []
        values = []

        for col in cols:
            if col != "id" and col in request.form:
                updates.append(f"{col}=?")
                values.append(request.form.get(col))

        if updates:
            values.append(vehicle_id)
            db.execute("UPDATE vehicles SET " + ", ".join(updates) + " WHERE id=?", values)
            db.commit()

        return redirect("/vehicles")

    return render_template("vehicles.html", title="Fahrzeuge", edit_item=vehicle)
@app.route("/invoice/<int:booking_id>")
def invoice_pdf(booking_id):
    db = get_db()

    booking = db.execute(
        "SELECT * FROM bookings WHERE id=?",
        (booking_id,)
    ).fetchone()

    customer = db.execute(
        "SELECT * FROM customers WHERE id=?",
        (booking["customer_id"],)
    ).fetchone()

    vehicle = db.execute(
        "SELECT * FROM vehicles WHERE id=?",
        (booking["vehicle_id"],)
    ).fetchone()

    template = "contracts/Rechnung.pdf"
    output = f"/tmp/Rechnung_{booking_id}.pdf"

    booking_data = dict(booking)

    brutto = float(
        booking_data.get("calc_total")
        or booking_data.get("total_price")
        or booking_data.get("price")
        or booking_data.get("special_price")
        or 0
    )

    netto = round(brutto / 1.19, 2)
    mwst = round(brutto - netto, 2)

    doc = fitz.open(template)
    page = doc[0]

    def write(x, y, text):
        page.insert_text((x, y), str(text), fontsize=10)

    name = f"{customer['first_name']} {customer['last_name']}"
    fahrzeug = f"{vehicle['name']} / {vehicle['plate']}"
    zeitraum = f"{booking['start_date']} bis {booking['end_date']}"

    write(150, 205, name)
    write(150, 225, customer["address"])
    write(150, 245, customer["phone"])
    write(150, 265, fahrzeug)
    write(150, 285, zeitraum)

    write(330, 410, f"{netto:.2f} Euro")
    write(330, 435, f"{mwst:.2f} Euro")
    write(330, 465, f"{brutto:.2f} Euro")

    doc.save(output)
    return send_file(output, as_attachment=False)

@app.route("/app")
def app_mobile():
    return render_template("app.html")

@app.route("/mobile")
def mobile():
    return render_template("mobile.html")
@app.route("/m/bookings")
def mobile_bookings():
    bookings = get_db().execute("""
        SELECT bookings.*, customers.first_name, customers.last_name, vehicles.name AS vehicle_name
        FROM bookings
        LEFT JOIN customers ON bookings.customer_id = customers.id
        LEFT JOIN vehicles ON bookings.vehicle_id = vehicles.id
        ORDER BY bookings.id DESC
    """).fetchall()

    return render_template("mobile_bookings.html", bookings=bookings)

with app.app_context():
    init_db()
if __name__ == "__main__":
    app.run(debug=True)

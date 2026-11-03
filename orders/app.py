"""Orders service: owns the order data and asks the Catalogue service about stock."""
import os
import sqlite3
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# Configuration comes from environment variables, with local defaults.
PORT = int(os.environ.get("PORT", 5002))
DB_PATH = os.environ.get("DB_PATH", "orders.db")
CATALOGUE_URL = os.environ.get("CATALOGUE_URL", "http://localhost:5001")
TIMEOUT = 2  # seconds - never wait forever for another service

# sql queries
sql_health_check = "SELECT 1"

sql_create_orders_tbl = """CREATE TABLE IF NOT EXISTS orders (
                   id         INTEGER PRIMARY KEY AUTOINCREMENT,
                   book_id    INTEGER NOT NULL,
                   quantity   INTEGER NOT NULL,
                   total      REAL NOT NULL,
                   created_at TEXT NOT NULL
               )"""

sql_list_orders = "SELECT * FROM orders ORDER BY id"
sql_get_order_by_id = "SELECT * FROM orders WHERE id = ?"
sql_insert_order = "INSERT INTO orders (book_id, quantity, total, created_at) VALUES (?, ?, ?, ?)"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    return conn

def init_db():
    with get_db() as conn:
        conn.execute(sql_create_orders_tbl)
    print(f"[orders] database ready at {DB_PATH}", flush=True)


@app.get("/health")
def health():
    try:
        with get_db() as conn:
            conn.execute(sql_health_check)
        return jsonify(status="ok", service="orders")
    except sqlite3.Error as e:
        return jsonify(status="error", service="orders", detail=str(e)), 500

@app.get("/orders")
def list_orders():
    with get_db() as conn:
        rows = conn.execute(sql_list_orders).fetchall()
    return jsonify([dict(r) for r in rows])

@app.get("/orders/<int:order_id>")
def get_order(order_id):
    with get_db() as conn:
        row = conn.execute(sql_get_order_by_id, (order_id,)).fetchone()
    if row is None:
        return jsonify(error="Order not found"), 404
    return jsonify(dict(row))

@app.post("/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    quantity = data.get("quantity")
    if not isinstance(book_id, int) or not isinstance(quantity, int) or quantity < 1:
        return jsonify(error="'book_id' and 'quantity' (>= 1) must be integers"), 400

    try:
        # 1. Ask the Catalogue service about the book (a network call!)
        r = requests.get(f"{CATALOGUE_URL}/books/{book_id}", timeout=TIMEOUT)
        if r.status_code == 404:
            return jsonify(error="Book does not exist"), 400
        r.raise_for_status()
        book = r.json()

        if book["stock"] < quantity:
            return jsonify(error="Insufficient stock", available=book["stock"]), 409

        # 2. Ask the Catalogue service to reduce the stock
        r = requests.put(
            f"{CATALOGUE_URL}/books/{book_id}/stock",
            json={"change": -quantity},
            timeout=TIMEOUT,
        )
        if r.status_code == 409:
            return jsonify(error="Insufficient stock", available=r.json()["available"]), 409
        r.raise_for_status()

    except requests.exceptions.RequestException as e:
        print(f"[orders] catalogue call failed: {e}", flush=True)
        return jsonify(error="Catalogue service unavailable, please try again later"), 503

    # 3. Save the order in OUR database
    total = round(book["price"] * quantity, 2)
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_db() as conn:
        cur = conn.execute(sql_insert_order, (book_id, quantity, total, created))
        order_id = cur.lastrowid

    print(f"[orders] order {order_id} created: book {book_id} x{quantity}", flush=True)
    return jsonify(id=order_id, book_id=book_id, quantity=quantity,
                   total=total, created_at=created), 201

if __name__ == "__main__":
    init_db()
    # 0.0.0.0 so the service is reachable from outside a container next week.
    app.run(host="0.0.0.0", port=PORT, debug=True)

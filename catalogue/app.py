"""Catalogue service: owns the book data and stock levels."""
import os
import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

# Configuration comes from environment variables, with local defaults.
PORT = int(os.environ.get("PORT", 5001))
DB_PATH = os.environ.get("DB_PATH", "catalogue.db")

# sql queries
sql_health_check = "SELECT 1"

sql_create_books_tbl = """CREATE TABLE IF NOT EXISTS books (
                   id     INTEGER PRIMARY KEY AUTOINCREMENT,
                   title  TEXT NOT NULL,
                   author TEXT NOT NULL,
                   price  REAL NOT NULL,
                   stock  INTEGER NOT NULL
               )"""

sql_count_books = "SELECT COUNT(*) FROM books"

sql_seed_books = "INSERT INTO books (title, author, price, stock) VALUES (?, ?, ?, ?)"

sql_list_books = "SELECT * FROM books ORDER BY id"
sql_get_book_by_id = "SELECT * FROM books WHERE id = ?"
sql_get_stock = "SELECT stock FROM books WHERE id = ?"
sql_update_stock = "UPDATE books SET stock = ? WHERE id = ?"

# seed data
books_seed =  [
                ("Designing Data-Intensive Applications", "Martin Kleppmann", 39.99, 5),
                ("Building Microservices", "Sam Newman", 34.50, 3),
                ("Flask Web Development", "Miguel Grinberg", 29.99, 10),
                ("Clean Code", "Robert C. Martin", 27.00, 0),
              ]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    return conn

def init_db():
    with get_db() as conn:
        conn.execute(sql_create_books_tbl)
        count = conn.execute(sql_count_books).fetchone()[0]
        if count == 0:
            conn.executemany(sql_seed_books, books_seed,)
    print(f"[catalogue] database ready at {DB_PATH}", flush=True)


@app.get("/health")
def health():
    try:
        with get_db() as conn:
            conn.execute(sql_health_check)
        return jsonify(status="ok", service="catalogue")
    except sqlite3.Error as e:
        return jsonify(status="error", service="catalogue", detail=str(e)), 500

@app.get("/books")
def list_books():
    with get_db() as conn:
        rows = conn.execute(sql_list_books).fetchall()
    return jsonify([dict(r) for r in rows])

@app.get("/books/<int:book_id>")
def get_book(book_id):
    with get_db() as conn:
        row = conn.execute(sql_get_book_by_id, (book_id,)).fetchone()
    if row is None:
        return jsonify(error="Book not found"), 404
    return jsonify(dict(row))

@app.put("/books/<int:book_id>/stock")
def change_stock(book_id):
    """Body: {"change": -2} to remove 2 from stock, {"change": 5} to add 5."""
    data = request.get_json(silent=True) or {}
    change = data.get("change")
    if not isinstance(change, int):
        return jsonify(error="'change' must be an integer"), 400

    with get_db() as conn:
        row = conn.execute(sql_get_stock, (book_id,)).fetchone()
        if row is None:
            return jsonify(error="Book not found"), 404
        new_stock = row["stock"] + change
        if new_stock < 0:
            return jsonify(error="Insufficient stock", available=row["stock"]), 409
        conn.execute(sql_update_stock, (new_stock, book_id))

    print(f"[catalogue] book {book_id} stock {row['stock']} -> {new_stock}", flush=True)
    return jsonify(id=book_id, stock=new_stock)

if __name__ == "__main__":
    init_db()
    # 0.0.0.0 so the service is reachable from outside a container next week.
    app.run(host="0.0.0.0", port=PORT, debug=True)

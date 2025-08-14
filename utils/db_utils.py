import sqlite3
import csv
import os

DB_PATH = "db/restaurant.db"
MENU_CSV_PATH = "db/menu.csv" 

def get_connection():
    return sqlite3.connect(DB_PATH)

def setup_tables():
    with get_connection() as conn:
        cursor = conn.cursor()

        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            price REAL NOT NULL,
            gst_percent REAL
        )
        """)

        
        cursor.execute("PRAGMA table_info(menu)")
        columns = [col[1] for col in cursor.fetchall()]
        if "available_today" not in columns:
            cursor.execute("ALTER TABLE menu ADD COLUMN available_today INTEGER DEFAULT 1")


        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_type TEXT,
            payment_method TEXT,
            total_amount REAL,
            gst_amount REAL,
            discount REAL,
            created_at TEXT
        )
        """)

        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            item_id INTEGER,
            quantity INTEGER,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(item_id) REFERENCES menu(id)
        )
        """)

        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)

        
        cursor.execute("SELECT COUNT(*) FROM staff")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO staff (username, password) VALUES (?, ?)",
                ("admin", "admin123")
            )

        conn.commit()

        
        seed_menu_from_csv_if_empty()


def seed_menu_from_csv_if_empty():
    """Seed the menu from CSV if menu table is empty."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM menu")
        if cursor.fetchone()[0] == 0:
            if os.path.exists(MENU_CSV_PATH):
                with open(MENU_CSV_PATH, "r", encoding="utf-8") as file:
                    reader = csv.DictReader(file)
                    rows = [
                        (
                            row["name"],
                            row.get("category", ""),
                            float(row["price"]),
                            float(row.get("gst_percent", 0)),
                            int(row.get("available_today", 1)) 
                        )
                        for row in reader
                    ]
                    cursor.executemany("""
                        INSERT INTO menu (name, category, price, gst_percent, available_today)
                        VALUES (?, ?, ?, ?, ?)
                    """, rows)
                    conn.commit()
            else:
                print(f"⚠ CSV file {MENU_CSV_PATH} not found. No menu items seeded.")


def add_staff(username, password):
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO staff (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def change_password(username, new_password):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE staff SET password = ? WHERE username = ?",
            (new_password, username)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_daily_sales():
    """Get total sales for today."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT IFNULL(SUM(total_amount), 0) 
            FROM orders 
            WHERE DATE(created_at) = DATE('now', 'localtime')
        """)
        return cursor.fetchone()[0]

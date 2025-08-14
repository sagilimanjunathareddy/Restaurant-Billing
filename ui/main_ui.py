import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import csv
import sqlite3
from datetime import datetime
import os
from utils.pdf_generator import generate_pdf_bill
from utils.calculator import calculate_bill

DB_PATH = "db/restaurant.db"
MENU_CSV = "data/menu.csv"

menu_items = []         
selected_items = []

# ---------------------- DB HELPERS ----------------------

def get_connection():
    return sqlite3.connect(DB_PATH)

def setup_tables():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()

        # staff
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)

        # menu - includes available_today flag
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            price REAL NOT NULL,
            gst_percent REAL,
            available_today INTEGER DEFAULT 0
        )
        """)

        # orders
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

        # order_items
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

        # default admin
        cursor.execute("SELECT COUNT(*) FROM staff")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO staff (username, password) VALUES (?, ?)", ("admin", "admin123"))

        conn.commit()

    # Seed menu from CSV if menu table is empty
    seed_menu_from_csv_if_empty()

def seed_menu_from_csv_if_empty():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM menu")
        if cursor.fetchone()[0] == 0:
            # if CSV exists, load rows
            if os.path.exists(MENU_CSV):
                with open(MENU_CSV, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = []
                    for row in reader:
                        try:
                            name = row['name'].strip()
                            category = row.get('category', '').strip()
                            price = float(row.get('price', 0))
                            gst = float(row.get('gst_percent', 0))
                        except Exception:
                            continue
                        rows.append((name, category, price, gst, 0))
                    if rows:
                        cursor.executemany(
                            "INSERT INTO menu (name, category, price, gst_percent, available_today) VALUES (?, ?, ?, ?, ?)",
                            rows
                        )
                        conn.commit()

# ---------------------- AUTH / STAFF ----------------------

def validate_login(username, password):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM staff WHERE username=? AND password=?", (username, password))
        return cursor.fetchone() is not None

def add_staff_db(username, password):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO staff (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def change_password_db(username, new_password):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE staff SET password=? WHERE username=?", (new_password, username))
        conn.commit()
        return cursor.rowcount > 0

# ---------------------- SALES & MENU DB QUERIES ----------------------

def get_daily_sales():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT IFNULL(SUM(total_amount), 0) FROM orders
            WHERE DATE(created_at) = DATE('now')
        """)
        res = cursor.fetchone()
        return res[0] if res else 0.0

def load_menu_for_billing():
    """Load only items that are available today"""
    global menu_items
    menu_items.clear()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, category, price, gst_percent FROM menu WHERE available_today=1 ORDER BY category, name")
        for row in cursor.fetchall():
            item = {'id': row[0], 'name': row[1], 'category': row[2], 'price': row[3], 'gst_percent': row[4]}
            menu_items.append(item)

# ---------------------- MENU MANAGEMENT (CRUD) ----------------------

def get_all_menu():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, category, price, gst_percent, available_today FROM menu ORDER BY id")
        return cursor.fetchall()

def add_menu_item_db(name, category, price, gst, available):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO menu (name, category, price, gst_percent, available_today) VALUES (?, ?, ?, ?, ?)",
                       (name, category, price, gst, 1 if available else 0))
        conn.commit()

def update_menu_item_db(item_id, name, category, price, gst, available):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE menu SET name=?, category=?, price=?, gst_percent=?, available_today=? WHERE id=?",
                       (name, category, price, gst, 1 if available else 0, item_id))
        conn.commit()

def delete_menu_item_db(item_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM menu WHERE id=?", (item_id,))
        conn.commit()

def set_available_today_db(item_id, available):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE menu SET available_today=? WHERE id=?", (1 if available else 0, item_id))
        conn.commit()

# ---------------------- ORDER LOGIC ----------------------

def add_item_to_order():
    selected_index = item_combo.current()
    quantity = quantity_var.get()

    if selected_index < 0 or quantity <= 0:
        messagebox.showwarning("Invalid", "Select an item and valid quantity.")
        return

    item = menu_items[selected_index]
    item_copy = {
        'id': item['id'],
        'name': item['name'],
        'price': item['price'],
        'gst_percent': item['gst_percent'],
        'quantity': quantity
    }
    selected_items.append(item_copy)
    update_order_display()

def update_order_display():
    order_listbox.delete(0, tk.END)
    for it in selected_items:
        order_listbox.insert(tk.END, f"{it['name']} x {it['quantity']} = ₹{it['price'] * it['quantity']:.2f}")

def show_total():
    gst = gst_var.get()
    discount = discount_var.get()
    bill = calculate_bill(selected_items, gst, discount)

    messagebox.showinfo("Final Bill", f"""
Subtotal: ₹{bill['subtotal']:.2f}
GST: ₹{bill['gst']:.2f}
Discount: ₹{bill['discount']:.2f}
---------------------------
Total: ₹{bill['total']:.2f}
""")
    save_order_to_db(bill)
    generate_pdf_bill(selected_items, bill)
    selected_items.clear()
    update_order_display()
    refresh_sales_label()

def save_order_to_db(bill):
    order_type = order_type_var.get()
    payment = payment_method_var.get()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO orders (order_type, payment_method, total_amount, gst_amount, discount, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (order_type, payment, bill['total'], bill['gst'], bill['discount'], now))
        order_id = cursor.lastrowid

        for it in selected_items:
            cursor.execute("INSERT INTO order_items (order_id, item_id, quantity) VALUES (?, ?, ?)",
                           (order_id, it['id'], it['quantity']))
        conn.commit()

# ---------------------- UI: Menu Management Window ----------------------

def manage_menu_window(parent):
    win = tk.Toplevel(parent)
    win.title("Manage Menu")
    win.geometry("800x500")

    # Treeview
    cols = ("ID", "Name", "Category", "Price", "GST%", "Available Today")
    tree = ttk.Treeview(win, columns=cols, show="headings", selectmode="browse")
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=120 if c != "Name" else 200, anchor="center")
    tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # Load menu rows
    def load_tree():
        for r in tree.get_children():
            tree.delete(r)
        for row in get_all_menu():
            # row = (id, name, category, price, gst, available)
            row_list = list(row)
            row_list[5] = "Yes" if row_list[5] == 1 else "No"
            tree.insert("", tk.END, values=row_list)

    # Form frame
    form = tk.Frame(win)
    form.pack(fill=tk.X, padx=8, pady=6)

    tk.Label(form, text="Name").grid(row=0, column=0, padx=4, pady=4)
    name_e = tk.Entry(form, width=30); name_e.grid(row=0, column=1, padx=4, pady=4)

    tk.Label(form, text="Category").grid(row=0, column=2, padx=4, pady=4)
    category_e = tk.Entry(form, width=20); category_e.grid(row=0, column=3, padx=4, pady=4)

    tk.Label(form, text="Price").grid(row=1, column=0, padx=4, pady=4)
    price_e = tk.Entry(form, width=10); price_e.grid(row=1, column=1, padx=4, pady=4)

    tk.Label(form, text="GST%").grid(row=1, column=2, padx=4, pady=4)
    gst_e = tk.Entry(form, width=10); gst_e.grid(row=1, column=3, padx=4, pady=4)

    avail_var = tk.IntVar()
    tk.Checkbutton(form, text="Available Today", variable=avail_var).grid(row=2, column=0, columnspan=2, pady=6)

    # CRUD ops
    def on_select(event):
        sel = tree.selection()
        if not sel:
            return
        vals = tree.item(sel[0])['values']
        # vals: ID, Name, Category, Price, GST%, Available
        name_e.delete(0, tk.END); name_e.insert(0, vals[1])
        category_e.delete(0, tk.END); category_e.insert(0, vals[2])
        price_e.delete(0, tk.END); price_e.insert(0, vals[3])
        gst_e.delete(0, tk.END); gst_e.insert(0, vals[4])
        avail_var.set(1 if vals[5] == "Yes" else 0)

    tree.bind("<<TreeviewSelect>>", on_select)

    def clear_form():
        name_e.delete(0, tk.END)
        category_e.delete(0, tk.END)
        price_e.delete(0, tk.END)
        gst_e.delete(0, tk.END)
        avail_var.set(0)
        tree.selection_remove(tree.selection())

    def add_item():
        name = name_e.get().strip()
        cat = category_e.get().strip()
        try:
            price = float(price_e.get())
            gst = float(gst_e.get())
        except:
            messagebox.showerror("Error", "Price and GST must be numeric.")
            return
        if not name:
            messagebox.showerror("Error", "Name required.")
            return
        add_menu_item_db(name, cat, price, gst, avail_var.get())
        load_tree()
        clear_form()

    def edit_item():
        sel = tree.selection()
        if not sel:
            messagebox.showerror("Error", "Select an item to edit.")
            return
        item_id = tree.item(sel[0])['values'][0]
        name = name_e.get().strip()
        cat = category_e.get().strip()
        try:
            price = float(price_e.get())
            gst = float(gst_e.get())
        except:
            messagebox.showerror("Error", "Price and GST must be numeric.")
            return
        update_menu_item_db(item_id, name, cat, price, gst, avail_var.get())
        load_tree()
        clear_form()

    def delete_item():
        sel = tree.selection()
        if not sel:
            messagebox.showerror("Error", "Select an item to delete.")
            return
        item_id = tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Confirm", "Delete selected item?"):
            delete_menu_item_db(item_id)
            load_tree()
            clear_form()

    btns = tk.Frame(win)
    btns.pack(fill=tk.X, padx=8, pady=6)
    tk.Button(btns, text="Add Item", command=add_item).pack(side=tk.LEFT, padx=6)
    tk.Button(btns, text="Edit Item", command=edit_item).pack(side=tk.LEFT, padx=6)
    tk.Button(btns, text="Delete Item", command=delete_item).pack(side=tk.LEFT, padx=6)
    tk.Button(btns, text="Clear", command=clear_form).pack(side=tk.LEFT, padx=6)
    tk.Button(btns, text="Refresh", command=load_tree).pack(side=tk.RIGHT, padx=6)

    load_tree()

# ---------------------- UI: Daily Menu Quick Update ----------------------

def update_daily_menu_window(parent):
    win = tk.Toplevel(parent)
    win.title("Update Today's Menu")
    win.geometry("400x500")

    rows = get_all_menu()
    vars_map = {}
    canvas = tk.Canvas(win)
    scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
    frame = tk.Frame(canvas)
    frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0,0), window=frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    for r in rows:
        item_id, name, cat, price, gst, avail = r
        v = tk.IntVar(value=1 if avail==1 else 0)
        chk = tk.Checkbutton(frame, text=f"{name} ({cat}) - ₹{price}", variable=v, anchor="w")
        chk.pack(fill=tk.X, padx=6, pady=2)
        vars_map[item_id] = v

    def save():
        for item_id, var in vars_map.items():
            set_available_today_db(item_id, var.get())
        messagebox.showinfo("Saved", "Today's menu updated.")
        win.destroy()
        refresh_menu_and_ui()

    tk.Button(win, text="Save Today's Menu", command=save, bg="green", fg="white").pack(pady=8)

# ---------------------- UI: Billing ----------------------

def refresh_menu_and_ui():
    # reload menu items for billing and refresh combo
    load_menu_for_billing()
    if 'item_combo' in globals():
        item_combo['values'] = [it['name'] for it in menu_items]

def add_new_staff_ui():
    username = simpledialog.askstring("Add Staff", "Enter new username:")
    if not username:
        return
    password = simpledialog.askstring("Add Staff", "Enter password:", show="*")
    if not password:
        return
    if add_staff_db(username, password):
        messagebox.showinfo("Success", "Staff added.")
    else:
        messagebox.showerror("Error", "Username exists.")

def update_password_ui():
    username = simpledialog.askstring("Change Password", "Enter username:")
    if not username:
        return
    new_pwd = simpledialog.askstring("Change Password", "Enter new password:", show="*")
    if not new_pwd:
        return
    if change_password_db(username, new_pwd):
        messagebox.showinfo("Success", "Password updated.")
    else:
        messagebox.showerror("Error", "User not found.")

def show_daily_sales():
    sales = get_daily_sales()
    messagebox.showinfo("Daily Sales", f"Today's Sales: ₹{sales:.2f}")

def refresh_sales_label():
    if 'daily_sales_label' in globals():
        daily_sales_label.config(text=f"Today's Sales: ₹{get_daily_sales():.2f}")

def run_billing_ui():
    setup_tables()
    refresh_menu_and_ui()

    global item_combo, quantity_var, order_listbox, gst_var, discount_var, order_type_var, payment_method_var, daily_sales_label

    root = tk.Tk()
    root.title("Restaurant Billing System")
    root.geometry("900x700")

    # Top: Daily sales label + Manage buttons
    top_frame = tk.Frame(root)
    top_frame.pack(fill=tk.X, pady=6)

    daily_sales_label = tk.Label(top_frame, text=f"Today's Sales: ₹{get_daily_sales():.2f}", font=("Arial", 14), fg="blue")
    daily_sales_label.pack(side=tk.LEFT, padx=10)

    tk.Button(top_frame, text="Manage Menu", command=lambda: manage_menu_window(root)).pack(side=tk.RIGHT, padx=6)
    tk.Button(top_frame, text="Update Today's Menu", command=lambda: update_daily_menu_window(root)).pack(side=tk.RIGHT, padx=6)

    # Main frames
    left = tk.Frame(root)
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=8)

    right = tk.Frame(root)
    right.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=8)

    # Left: order entry
    tk.Label(left, text="Order Type").pack(anchor="w")
    order_type_var = tk.StringVar(value="Dine-In")
    tk.Radiobutton(left, text="Dine-In", variable=order_type_var, value="Dine-In").pack(anchor="w")
    tk.Radiobutton(left, text="Takeaway", variable=order_type_var, value="Takeaway").pack(anchor="w")

    tk.Label(left, text="Select Item").pack(anchor="w", pady=(8,0))
    item_combo = ttk.Combobox(left, values=[it['name'] for it in menu_items], width=40)
    item_combo.pack(anchor="w")

    tk.Label(left, text="Quantity").pack(anchor="w", pady=(8,0))
    quantity_var = tk.IntVar(value=1)
    tk.Entry(left, textvariable=quantity_var, width=10).pack(anchor="w")

    tk.Button(left, text="Add to Order", command=add_item_to_order).pack(anchor="w", pady=6)

    tk.Label(left, text="Order Summary").pack(anchor="w", pady=(8,0))
    order_listbox = tk.Listbox(left, width=60, height=15)
    order_listbox.pack(anchor="w")

    tk.Label(left, text="GST (%)").pack(anchor="w", pady=(8,0))
    gst_var = tk.DoubleVar(value=5.0)
    tk.Entry(left, textvariable=gst_var, width=10).pack(anchor="w")

    tk.Label(left, text="Discount (%)").pack(anchor="w", pady=(8,0))
    discount_var = tk.DoubleVar(value=0.0)
    tk.Entry(left, textvariable=discount_var, width=10).pack(anchor="w")

    tk.Label(left, text="Payment Method").pack(anchor="w", pady=(8,0))
    payment_method_var = tk.StringVar(value="Cash")
    ttk.Combobox(left, textvariable=payment_method_var, values=["Cash", "Card", "UPI"], width=20).pack(anchor="w")

    tk.Button(left, text="Show Final Bill", bg="green", fg="white", command=show_total).pack(anchor="w", pady=10)

    # Right: utility buttons
    tk.Button(right, text="View Daily Sales", command=show_daily_sales, width=20).pack(pady=6)
    tk.Button(right, text="Add Staff", command=add_new_staff_ui, width=20).pack(pady=6)
    tk.Button(right, text="Change Password", command=update_password_ui, width=20).pack(pady=6)
    tk.Button(right, text="Logout", command=lambda: logout(root), bg="red", fg="white", width=20).pack(pady=20)

    root.mainloop()

# ---------------------- LOGIN & LAUNCH ----------------------

def logout(window):
    window.destroy()
    show_login_window()

def show_login_window():
    setup_tables()  # ensure DB and seed run before UI
    login = tk.Tk()
    login.title("Login")
    login.geometry("320x220")

    tk.Label(login, text="Username").pack(pady=6)
    username_var = tk.StringVar()
    tk.Entry(login, textvariable=username_var, width=30).pack()

    tk.Label(login, text="Password").pack(pady=6)
    password_var = tk.StringVar()
    tk.Entry(login, textvariable=password_var, show="*", width=30).pack()

    def do_login():
        username = username_var.get()
        password = password_var.get()
        if validate_login(username, password):
            login.destroy()
            run_billing_ui()
        else:
            messagebox.showerror("Login Failed", "Invalid credentials.")

    tk.Button(login, text="Login", command=do_login, width=20).pack(pady=12)

    # quick admin helpers
    tk.Button(login, text="Manage Menu", command=lambda: [login.destroy(), run_billing_ui(), manage_menu_window(None)], width=20).pack(pady=4)

    login.mainloop()

# ---------------------- MAIN ----------------------

if __name__ == "__main__":
    show_login_window()

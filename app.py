from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "CHANGE_ME_TO_SOMETHING_RANDOM" 

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "kanael.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Menu items 
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT,
            image_filename TEXT
        );
        """
    )

    # Orders table, extended with notes, address and created_at
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            notes TEXT,
            total REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    # Order items table  (to properly store multiple items per order).
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        );
        """
    )

    # contact messages table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


    cur.execute("SELECT COUNT(*) AS c FROM menu_items")
    count = cur.fetchone()["c"]
    if count == 0:
        demo_items = [
            # Desserts
            ("Signature Chocolate Cake", "Rich dark chocolate sponge layered with silky ganache.", 7.99, "Dessert", None),
            ("Strawberry Cheesecake", "Creamy vanilla base with biscuit crust and fresh strawberry topping.", 6.50, "Dessert", None),
            ("Vanilla Ice Cream", "Madagascan vanilla bean ice cream, smooth and classic.", 3.50, "Dessert", None),
            ("Luxury Chocolate Mousse", "Light, airy chocolate mousse with a dark chocolate finish.", 5.80, "Dessert", None),
            ("Caramel Pudding", "Soft, silky custard topped with warm caramel.", 4.90, "Dessert", None),
            # Drinks
            ("Iced Caramel Latte", "Smooth espresso shaken with cold milk and caramel drizzle.", 4.25, "Drink", None),
            ("Caramel Latte (Hot)", "Velvety espresso with steamed milk and caramel syrup.", 4.10, "Drink", None),
            ("Iced Vanilla Latte", "Cold milk, espresso and vanilla syrup over ice.", 4.30, "Drink", None),
            ("Matcha Latte", "Japanese matcha whisked with warm milk.", 4.80, "Drink", None),
            ("Hot Chocolate", "Creamy cocoa topped with fresh whipped cream.", 3.90, "Drink", None),
            ("Berry Iced Tea", "Refreshing iced tea infused with berry flavours.", 3.20, "Drink", None),
            ("Espresso Shot", "Strong, bold, classic espresso.", 2.20, "Drink", None),
            # Brunch
            ("Kanael Brunch Waffle", "Crispy golden waffle topped with fresh berries and maple syrup.", 9.50, "Brunch", None),
            ("Avocado Toast", "Smashed avocado on toasted sourdough with chilli flakes.", 7.50, "Brunch", None),
            ("Breakfast Granola Cup", "Honey granola layered with yogurt and seasonal berries.", 5.00, "Brunch", None),
            ("Croissant & Jam", "Flaky butter croissant served with strawberry jam.", 4.20, "Brunch", None),
            ("Pancake Stack", "Fluffy pancakes drizzled with maple syrup.", 7.80, "Brunch", None),
            ("Banana & Nutella Waffle", "Warm waffle topped with sliced banana and Nutella drizzle.", 8.90, "Brunch", None),
        ]
        cur.executemany(
            "INSERT INTO menu_items (name, description, price, category, image_filename) VALUES (?, ?, ?, ?, ?)",
            demo_items,
        )

    conn.commit()
    conn.close()


# Initialize the database at startup
with app.app_context():
    init_db()


# Helper functions 

def _get_cart():
    return session.get("cart", {})


def _save_cart(cart):
    session["cart"] = cart
    session.modified = True


def _calculate_cart_details(cart):
    """Return a list of items with name, price, qty and total, plus grand_total."""
    if not cart:
        return [], 0.0

    conn = get_db_connection()
    cur = conn.cursor()
    items = []
    grand_total = 0.0

    for item_id, qty in cart.items():
        cur.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if row:
            line_total = row["price"] * qty
            grand_total += line_total
            items.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "price": row["price"],
                    "quantity": qty,
                    "line_total": line_total,
                }
            )
    conn.close()
    return items, grand_total


#  Public routes 

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/menu")
def menu():
    conn = get_db_connection()
    cur = conn.cursor()
    category = request.args.get("category")
    search = request.args.get("q")

    query = "SELECT * FROM menu_items"
    params = []

    conditions = []
    if category:
        conditions.append("category = ?")
        params.append(category)
    if search:
        conditions.append("(name LIKE ? OR description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY category, name"
    cur.execute(query, params)
    items = cur.fetchall()
    conn.close()

    return render_template("menu.html", desserts=items, selected_category=category, search=search)


@app.route("/add_to_cart/<int:item_id>", methods=["POST"])
def add_to_cart(item_id):
    cart = _get_cart()
    cart[str(item_id)] = cart.get(str(item_id), 0) + 1
    _save_cart(cart)
    flash("Item added to your order.", "success")
    return redirect(url_for("menu"))


@app.route("/cart", methods=["GET", "POST"])
def cart():
    cart = _get_cart()

    if request.method == "POST":
        # Update quantities or clear
        if "clear" in request.form:
            cart = {}
        else:
            for key, value in request.form.items():
                if key.startswith("qty_"):
                    item_id = key.replace("qty_", "")
                    try:
                        qty = int(value)
                        if qty <= 0:
                            cart.pop(item_id, None)
                        else:
                            cart[item_id] = qty
                    except ValueError:
                        continue
        _save_cart(cart)
        return redirect(url_for("cart"))

    items, grand_total = _calculate_cart_details({int(k): v for k, v in cart.items()})
    return render_template("cart.html", items=items, total=grand_total)


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = _get_cart()
    if not cart:
        flash("Your cart is empty. Please add some items first.", "warning")
        return redirect(url_for("menu"))

    items, grand_total = _calculate_cart_details({int(k): v for k, v in cart.items()})

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name or not phone:
            flash("Name and phone are required.", "danger")
            return render_template("checkout.html", items=items, total=grand_total)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO orders (customer_name, phone, address, notes, total, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, phone, address, notes, grand_total, datetime.now().isoformat(timespec="seconds")),
        )
        order_id = cur.lastrowid

        # Insert order items
        for item in items:
            cur.execute(
                """
                INSERT INTO order_items (order_id, item_name, quantity, price)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, item["name"], item["quantity"], item["price"]),
            )

        conn.commit()
        conn.close()

        # Clear cart
        session["cart"] = {}
        flash("Thank you! Your order has been placed.", "success")
        return redirect(url_for("confirm", order_id=order_id))

    return render_template("checkout.html", items=items, total=grand_total)


@app.route("/confirm/<int:order_id>")
def confirm(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()
    cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items = cur.fetchall()
    conn.close()
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("index"))
    return render_template("confirm.html", order=order, items=items)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not message:
            flash("Name and message are required.", "danger")
            return redirect(url_for("contact"))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO messages (name, email, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, email, message, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        conn.close()

        flash("Thank you for contacting us. We'll get back to you soon.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


# Simple admin area (no full auth, just a basic “hidden” area) 

@app.route("/admin")
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM menu_items")
    menu_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM orders")
    order_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM messages")
    message_count = cur.fetchone()["c"]
    conn.close()

    return render_template(
        "admin_dashboard.html",
        menu_count=menu_count,
        order_count=order_count,
        message_count=message_count,
    )


@app.route("/admin/menu", methods=["GET", "POST"])
def admin_menu():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        price_raw = request.form.get("price", "").strip()
        try:
            price = float(price_raw)
        except ValueError:
            price = None

        if not name or price is None:
            flash("Name and valid price are required.", "danger")
        else:
            cur.execute(
                """
                INSERT INTO menu_items (name, description, price, category)
                VALUES (?, ?, ?, ?)
                """,
                (name, description, price, category),
            )
            conn.commit()
            flash("Menu item added.", "success")

    cur.execute("SELECT * FROM menu_items ORDER BY category, name")
    items = cur.fetchall()
    conn.close()
    return render_template("admin_menu.html", items=items)


@app.route("/admin/menu/<int:item_id>/delete", methods=["POST"])
def delete_menu_item(item_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    flash("Menu item deleted.", "info")
    return redirect(url_for("admin_menu"))


@app.route("/admin/orders")
def admin_orders():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
    orders = cur.fetchall()
    conn.close()
    return render_template("admin_orders.html", orders=orders)


if __name__ == "__main__":
    app.run(debug=True)
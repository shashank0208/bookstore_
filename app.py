import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# Email(s) allowed to access the "Add Book" admin page.
# Set this to your own email so only you can add books.
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}

# anon client: respects Row Level Security, safe for per-user reads
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# admin client: bypasses RLS, used only for catalog writes (add book / stock updates)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------
def get_current_user():
    """Return dict with id/email if logged in, else None."""
    if "access_token" not in session:
        return None
    try:
        resp = supabase.auth.get_user(session["access_token"])
        if resp and resp.user:
            return {"id": resp.user.id, "email": resp.user.email}
    except Exception:
        return None
    return None


@app.context_processor
def inject_user():
    user = get_current_user()
    is_admin = bool(user and user['email'].lower() in ADMIN_EMAILS)
    return {"current_user": user, "is_admin": is_admin}


# ----------------------------------------------------------------
# Pages
# ----------------------------------------------------------------
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/books')
def books():
    resp = supabase.table('books').select(
        'id, title, author, price, description, cover_image, genre'
    ).execute()
    return render_template('books.html', books=resp.data)


@app.route('/topseller')
def topseller():
    resp = supabase.table('books').select(
        'id, title, author, price, description, cover_image, genre'
    ).eq('top_seller', True).execute()
    return render_template('topseller.html', books=resp.data)


@app.route('/get_books')
def get_books():
    order = request.args.get('order', 'asc')
    ascending = (order == 'asc')

    resp = supabase.table('books').select(
        'id, title, author, price, description, cover_image, genre'
    ).order('price', desc=not ascending).execute()

    return jsonify(resp.data)


@app.route('/authors')
def authors():
    return render_template('aurthors.html')


@app.route('/genre')
def genre():
    resp = supabase.table('books').select(
        'id, title, author, price, cover_image, genre'
    ).execute()

    # group by genre for display
    genres = {}
    for b in resp.data:
        g = b.get('genre') or 'Other'
        genres.setdefault(g, []).append(b)

    return render_template('genre.html', genres=genres)


@app.route('/audiobooks')
def audiobooks():
    return render_template('audiobooks.html')


@app.route('/addbooks')
def addbooks():
    user = get_current_user()
    if not user or user['email'].lower() not in ADMIN_EMAILS:
        return redirect(url_for('home'))
    return render_template('add_books.html')


@app.route('/cart')
def view_cart():
    return render_template('cart.html')


@app.route('/orders')
def orders():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    orders_resp = supabase.table('orders').select(
        'id, total, status, created_at, order_items(title, price, quantity, subtotal)'
    ).eq('user_id', user['id']).order('created_at', desc=True).execute()

    return render_template('orders.html', orders=orders_resp.data)


# ----------------------------------------------------------------
# Auth (Supabase Auth - email/password)
# ----------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email')
    password = request.form.get('password')

    try:
        resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
        session['access_token'] = resp.session.access_token
        session['refresh_token'] = resp.session.refresh_token
        return redirect(url_for('home'))
    except Exception as e:
        return render_template('login.html', error=str(e))


@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email')
    password = request.form.get('password')

    try:
        resp = supabase.auth.sign_up({"email": email, "password": password})
        # If email confirmation is OFF in Supabase settings, session is returned immediately
        if resp.session:
            session['access_token'] = resp.session.access_token
            session['refresh_token'] = resp.session.refresh_token
            return redirect(url_for('home'))
        else:
            return render_template('login.html', message="Check your email to confirm your account, then log in.")
    except Exception as e:
        return render_template('login.html', error=str(e))


@app.route('/logout')
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    session.clear()
    return redirect(url_for('home'))


# ----------------------------------------------------------------
# Add book (admin) - uses service role client to bypass RLS
# ----------------------------------------------------------------
@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    user = get_current_user()
    if not user or user['email'].lower() not in ADMIN_EMAILS:
        return redirect(url_for('home'))

    if request.method == 'GET':
        return render_template('add_books.html')

    title = request.form['title']
    author = request.form['author']
    price = float(request.form['price'])
    description = request.form['description']
    cover_image = request.form['cover_image'].strip()
    genre = request.form['genre']
    top_seller = bool(request.form.get('top_seller'))
    stock = int(request.form['stock'])

    book_resp = supabase_admin.table('books').insert({
        "title": title,
        "author": author,
        "price": price,
        "description": description,
        "cover_image": cover_image,
        "genre": genre,
        "top_seller": top_seller,
    }).execute()

    book_id = book_resp.data[0]['id']

    supabase_admin.table('inventory').insert({
        "book_id": book_id,
        "stock": stock,
    }).execute()

    return redirect(url_for('books'))


# ----------------------------------------------------------------
# Place order (checkout)
# cart items from the frontend look like:
#   { "id": <book_id>, "title": ..., "price": ..., "quantity": <int> }
# ----------------------------------------------------------------
@app.route('/place_order', methods=['POST'])
def place_order():
    user = get_current_user()
    if not user:
        return jsonify({"error": "You must be logged in to place an order."}), 401

    data = request.get_json()
    cart = data.get('cart', [])

    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    line_items = []
    total = 0.0

    # Validate stock for every item first
    for item in cart:
        book_id = item['id']
        qty = int(item['quantity'])

        inv_resp = supabase_admin.table('inventory').select('stock').eq('book_id', book_id).single().execute()
        available = inv_resp.data['stock'] if inv_resp.data else 0

        if available < qty:
            return jsonify({"error": f"Not enough stock for '{item.get('title', book_id)}' (only {available} left)"}), 400

        subtotal = round(float(item['price']) * qty, 2)
        total += subtotal
        line_items.append({
            "book_id": book_id,
            "title": item['title'],
            "price": item['price'],
            "quantity": qty,
            "subtotal": subtotal,
        })

    total = round(total, 2)

    # Create the order
    order_resp = supabase_admin.table('orders').insert({
        "user_id": user['id'],
        "total": total,
        "status": "placed",
    }).execute()
    order_id = order_resp.data[0]['id']

    # Insert order items and decrement stock
    for li in line_items:
        supabase_admin.table('order_items').insert({
            "order_id": order_id,
            "book_id": li['book_id'],
            "title": li['title'],
            "price": li['price'],
            "quantity": li['quantity'],
            "subtotal": li['subtotal'],
        }).execute()

        inv_resp = supabase_admin.table('inventory').select('stock').eq('book_id', li['book_id']).single().execute()
        new_stock = inv_resp.data['stock'] - li['quantity']
        supabase_admin.table('inventory').update({"stock": new_stock}).eq('book_id', li['book_id']).execute()

    return jsonify({"message": "Order placed successfully", "order_id": order_id, "total": total}), 200


# ----------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)

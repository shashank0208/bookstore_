# Bookstore — Supabase Setup Guide

## 1. Create Supabase project
1. Go to https://supabase.com -> New Project
2. Wait ~2 min for provisioning
3. Go to **Settings -> API**, copy:
   - Project URL -> `SUPABASE_URL`
   - `anon` `public` key -> `SUPABASE_ANON_KEY`
   - `service_role` key -> `SUPABASE_SERVICE_KEY` (keep secret, never expose to browser)

## 2. Set up the database
1. Go to **SQL Editor -> New query**
2. Paste the contents of `schema.sql` and run it
   - This creates `books`, `inventory`, `orders`, `order_items` tables, RLS policies, and seeds your 4 books (with placeholder image URLs)

## 3. Configure environment
1. Copy `.env.example` to `.env`
2. Fill in `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`
3. Set `FLASK_SECRET_KEY` to any random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)

## 4. Install dependencies
```bash
pip install -r requirements.txt
```

## 5. Migrate cover images to Supabase Storage
```bash
python migrate_images.py
```
This uploads the 4 images in `static/images/` to a new public `book-covers`
bucket and updates each book's `cover_image` URL in the database.

## 6. Enable email/password auth (default is usually already on)
1. Go to **Authentication -> Providers -> Email**
2. Make sure it's enabled
3. For testing, you may want to disable "Confirm email" under
   **Authentication -> Settings** so signup logs you in immediately.
   (Re-enable for production.)

## 7. Run the app
```bash
python app.py
```
Visit http://127.0.0.1:5000

## How it works now
- **Catalog (books, topseller, genre)**: read from Supabase Postgres via the
  anon client (public read access via RLS).
- **Cart**: stored in browser `localStorage`, shared schema
  `{ id, title, price, quantity }` used consistently across all pages
  (`static/js/cart.js`).
- **Login/Signup**: handled by Supabase Auth. Session tokens stored in
  Flask's signed session cookie.
- **Checkout (`/place_order`)**: requires login. Validates stock, creates an
  `orders` row + `order_items` rows, decrements `inventory.stock`, returns
  the total. Uses the service-role client so it can write regardless of RLS.
- **My Orders (`/orders`)**: shows order history for the logged-in user.
- **Add Book (`/add_book`)**: admin-style insert using the service-role
  client (bypasses RLS) — anyone can currently access this page; if you want
  to restrict it, add an admin check using `current_user['email']`.

## Notes / things you may want to improve later
- `/add_book` has no auth check — add one if this goes public.
- Cart is per-browser (localStorage), not per-account — fine for a college
  project, but won't sync across devices.
- Consider adding a `quantity` cap based on live `inventory.stock` when
  rendering the cart, so users can't order more than available.

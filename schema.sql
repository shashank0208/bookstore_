-- ============================================================
-- Bookstore schema for Supabase (Postgres)
-- Run this in Supabase Dashboard -> SQL Editor -> New query
-- ============================================================

-- Drop old tables if re-running during development
drop table if exists order_items cascade;
drop table if exists orders cascade;
drop table if exists inventory cascade;
drop table if exists books cascade;

-- ------------------------------------------------------------
-- BOOKS
-- ------------------------------------------------------------
create table books (
    id            bigint generated always as identity primary key,
    title         text not null,
    author        text not null,
    price         numeric(10, 2) not null check (price >= 0),
    description   text,
    cover_image   text,           -- public URL from Supabase Storage
    genre         text,
    top_seller    boolean not null default false,
    created_at    timestamptz not null default now()
);

-- ------------------------------------------------------------
-- INVENTORY (1:1 with books)
-- ------------------------------------------------------------
create table inventory (
    book_id  bigint primary key references books(id) on delete cascade,
    stock    integer not null default 0 check (stock >= 0)
);

-- ------------------------------------------------------------
-- ORDERS  (one row per checkout)
-- user_id references Supabase Auth's auth.users table
-- ------------------------------------------------------------
create table orders (
    id          bigint generated always as identity primary key,
    user_id     uuid not null references auth.users(id) on delete cascade,
    total       numeric(10, 2) not null default 0,
    status      text not null default 'placed',
    created_at  timestamptz not null default now()
);

-- ------------------------------------------------------------
-- ORDER ITEMS (line items per order)
-- ------------------------------------------------------------
create table order_items (
    id          bigint generated always as identity primary key,
    order_id    bigint not null references orders(id) on delete cascade,
    book_id     bigint not null references books(id),
    title       text not null,       -- snapshot at time of purchase
    price       numeric(10, 2) not null,  -- snapshot at time of purchase
    quantity    integer not null check (quantity > 0),
    subtotal    numeric(10, 2) not null
);

-- ------------------------------------------------------------
-- INDEXES
-- ------------------------------------------------------------
create index idx_books_genre on books(genre);
create index idx_books_top_seller on books(top_seller);
create index idx_orders_user on orders(user_id);
create index idx_order_items_order on order_items(order_id);

-- ------------------------------------------------------------
-- ROW LEVEL SECURITY
-- books & inventory: readable by everyone (public catalog)
-- orders & order_items: only visible to the owning user
-- ------------------------------------------------------------
alter table books enable row level security;
alter table inventory enable row level security;
alter table orders enable row level security;
alter table order_items enable row level security;

-- Public read access to catalog
create policy "Books are viewable by everyone"
    on books for select using (true);

create policy "Inventory is viewable by everyone"
    on inventory for select using (true);

-- Orders: users can see/insert only their own
create policy "Users can view own orders"
    on orders for select using (auth.uid() = user_id);

create policy "Users can insert own orders"
    on orders for insert with check (auth.uid() = user_id);

create policy "Users can view own order items"
    on order_items for select using (
        order_id in (select id from orders where user_id = auth.uid())
    );

create policy "Users can insert own order items"
    on order_items for insert with check (
        order_id in (select id from orders where user_id = auth.uid())
    );

-- NOTE: writes to books/inventory (admin add-book, stock updates)
-- are done via the backend using the SERVICE ROLE key, which
-- bypasses RLS. Do not expose the service key to the browser.

-- ------------------------------------------------------------
-- SEED DATA - your existing 4 books
-- Replace cover_image URLs after uploading images to Supabase
-- Storage bucket "book-covers" (see migration instructions).
-- ------------------------------------------------------------
insert into books (title, author, price, description, cover_image, genre, top_seller) values
('Ikigai', 'Héctor García & Francesc Miralles', 399.00, 'A Japanese concept meaning "a reason for being" — explores the secret to a long, happy, purposeful life.', 'REPLACE_WITH_SUPABASE_URL/ikigai.jpg', 'Self-Help', true),
('Thinking, Fast and Slow', 'Daniel Kahneman', 599.00, 'A groundbreaking exploration of the two systems that drive the way we think and make decisions.', 'REPLACE_WITH_SUPABASE_URL/thinking_fast_slow.jpg', 'Psychology', true),
('The Psychology of Money', 'Morgan Housel', 349.00, 'Timeless lessons on wealth, greed, and happiness, and how we think about money.', 'REPLACE_WITH_SUPABASE_URL/the_psychology_of_money.jpg', 'Finance', true),
('Rom Com Collection', 'Various Authors', 299.00, 'A delightful collection of romantic comedy stories.', 'REPLACE_WITH_SUPABASE_URL/rom_com.jpg', 'Romance', false);

-- Seed matching inventory rows
insert into inventory (book_id, stock)
select id, 25 from books;

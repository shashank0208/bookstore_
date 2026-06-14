"""
One-time migration script.

What it does:
1. Uploads the 4 cover images from static/images/ to a Supabase Storage
   bucket called "book-covers" (creates the bucket if missing, sets it public).
2. Updates the `books.cover_image` column for each book with the new
   public URL.

Run this AFTER:
- You've created your Supabase project
- You've run schema.sql in the SQL editor
- You've filled in your .env file (see .env.example)

Usage:
    python migrate_images.py
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

BUCKET = "book-covers"

IMAGE_DIR = os.path.join(os.path.dirname(__file__), "static", "images")

# filename -> book title (must match titles inserted by schema.sql)
IMAGE_TO_BOOK = {
    "ikigai.jpg": "Ikigai",
    "thinking_fast_slow.jpg": "Thinking, Fast and Slow",
    "the_psychology_of_money.jpg": "The Psychology of Money",
    "rom_com.jpg": "Rom Com Collection",
}


def ensure_bucket():
    buckets = supabase.storage.list_buckets()
    names = [b.name for b in buckets]
    if BUCKET not in names:
        print(f"Creating bucket '{BUCKET}'...")
        supabase.storage.create_bucket(BUCKET, options={"public": True})
    else:
        print(f"Bucket '{BUCKET}' already exists.")


def upload_images():
    for filename, title in IMAGE_TO_BOOK.items():
        path = os.path.join(IMAGE_DIR, filename)
        if not os.path.exists(path):
            print(f"  SKIP (file not found): {filename}")
            continue

        with open(path, "rb") as f:
            data = f.read()

        print(f"  Uploading {filename}...")
        try:
            supabase.storage.from_(BUCKET).upload(
                path=filename,
                file=data,
                file_options={"content-type": "image/jpeg", "upsert": "true"},
            )
        except Exception as e:
            print(f"    upload error (continuing): {e}")

        public_url = supabase.storage.from_(BUCKET).get_public_url(filename)
        print(f"    URL: {public_url}")

        # update the matching book row
        resp = (
            supabase.table("books")
            .update({"cover_image": public_url})
            .eq("title", title)
            .execute()
        )
        if resp.data:
            print(f"    Updated book '{title}'")
        else:
            print(f"    WARNING: no book found with title '{title}'")


if __name__ == "__main__":
    print("Ensuring storage bucket exists...")
    ensure_bucket()
    print("Uploading images and updating book records...")
    upload_images()
    print("Done.")

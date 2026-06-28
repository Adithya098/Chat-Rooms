"""One-time migration: add edited_at column to messages table.

edited_at is set when a sender edits their own message; NULL means never edited.
It drives the "(edited)" label in the UI. Existing messages default to NULL."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'messages' AND column_name = 'edited_at'"
    ))
    if result.fetchone():
        print("Column edited_at already exists, skipping.")
    else:
        conn.execute(text(
            "ALTER TABLE messages ADD COLUMN edited_at TIMESTAMPTZ NULL"
        ))
        conn.commit()
        print("Added edited_at column to messages table.")

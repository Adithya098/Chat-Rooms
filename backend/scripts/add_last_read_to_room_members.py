"""One-time migration: add last_read_message_id column to room_members table.

Backs the per-room unread badge. The column stores each member's read
watermark (the newest message id they've seen); unread counts are derived
from it, so no separate counter or reads table is needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Check if column already exists
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'room_members' AND column_name = 'last_read_message_id'"
    ))
    if result.fetchone():
        print("Column last_read_message_id already exists, skipping.")
    else:
        conn.execute(text(
            "ALTER TABLE room_members ADD COLUMN last_read_message_id INTEGER DEFAULT NULL"
        ))
        conn.commit()
        print("Added last_read_message_id column to room_members table.")

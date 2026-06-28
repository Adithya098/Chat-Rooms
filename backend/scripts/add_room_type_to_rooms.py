"""One-time migration: add room_type column to rooms and relax name to nullable.

room_type distinguishes 'group' channels (join/approve/admin workflow) from 'direct'
1:1 personal chats. Existing rooms are all channels, so they default to 'group'.
Direct rooms carry no stored name, so the NOT NULL constraint on name is dropped."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'rooms' AND column_name = 'room_type'"
    ))
    if result.fetchone():
        print("Column room_type already exists, skipping add.")
    else:
        conn.execute(text(
            "ALTER TABLE rooms "
            "ADD COLUMN room_type VARCHAR(20) NOT NULL DEFAULT 'group'"
        ))
        conn.commit()
        print("Added room_type column to rooms table (existing rooms backfilled to 'group').")

    # Direct rooms have no stored name; allow NULL. Idempotent — re-running is harmless.
    conn.execute(text("ALTER TABLE rooms ALTER COLUMN name DROP NOT NULL"))
    conn.commit()
    print("Relaxed rooms.name to nullable.")

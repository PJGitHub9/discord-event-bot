import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict
import os

# Use data directory for database if it exists (for Docker)
DATA_DIR = "/app/data" if os.path.exists("/app/data") else "."
DATABASE_PATH = os.path.join(DATA_DIR, "events.db")


async def init_database():
    """Initialize the database and create tables if they don't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER UNIQUE NOT NULL,
                event_name TEXT NOT NULL,
                event_date TEXT NOT NULL,
                author_id INTEGER NOT NULL,
                author_role_id INTEGER,
                event_role_id INTEGER,
                reminder_days INTEGER DEFAULT 0,
                reminder_sent BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL,
                archived BOOLEAN DEFAULT 0
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                response TEXT NOT NULL,
                plus_one BOOLEAN DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(thread_id, user_id)
            )
        """)
        
        await db.commit()


async def add_event(
    thread_id: int,
    event_name: str,
    event_date: datetime,
    author_id: int,
    author_role_id: int,
    event_role_id: Optional[int] = None,
    reminder_days: int = 0
):
    """Add a new event to the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO events 
            (thread_id, event_name, event_date, author_id, author_role_id, 
             event_role_id, reminder_days, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            thread_id,
            event_name,
            event_date.isoformat(),
            author_id,
            author_role_id,
            event_role_id,
            reminder_days,
            datetime.now().isoformat()
        ))
        await db.commit()


async def get_event_by_thread_id(thread_id: int) -> Optional[Dict]:
    """Get event information by thread ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM events WHERE thread_id = ?", (thread_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def get_events_needing_reminders() -> List[Dict]:
    """Get events that need reminders sent."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM events 
            WHERE reminder_days > 0 
            AND reminder_sent = 0 
            AND archived = 0
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def mark_reminder_sent(thread_id: int):
    """Mark that a reminder has been sent for an event."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE events SET reminder_sent = 1 WHERE thread_id = ?",
            (thread_id,)
        )
        await db.commit()


async def archive_event(thread_id: int):
    """Mark an event as archived."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE events SET archived = 1 WHERE thread_id = ?",
            (thread_id,)
        )
        await db.commit()


async def get_past_events() -> List[Dict]:
    """Get events that have passed their event date."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.now().isoformat()
        async with db.execute("""
            SELECT * FROM events 
            WHERE event_date < ? 
            AND archived = 0
        """, (now,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def delete_event(thread_id: int):
    """Delete an event from the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM events WHERE thread_id = ?",
            (thread_id,)
        )
        await db.commit()

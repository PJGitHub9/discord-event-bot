import aiosqlite
from datetime import datetime, timedelta
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
                archived BOOLEAN DEFAULT 0,
                close_prompt_count INTEGER DEFAULT 0,
                last_close_prompt TEXT
            )
        """)
        
        # Add new columns if they don't exist (for existing databases)
        try:
            await db.execute("ALTER TABLE events ADD COLUMN close_prompt_count INTEGER DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE events ADD COLUMN last_close_prompt TEXT")
        except:
            pass
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                response TEXT NOT NULL,
                plus_one BOOLEAN DEFAULT 0,
                baby BOOLEAN DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(thread_id, user_id)
            )
        """)

        # Ensure schema for older DBs
        try:
            await db.execute("ALTER TABLE attendance ADD COLUMN baby BOOLEAN DEFAULT 0")
        except:
            pass

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


async def get_active_events() -> List[Dict]:
    """Get all non-archived events."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM events WHERE archived = 0"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


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
        await db.execute("DELETE FROM events WHERE thread_id = ?", (thread_id,))
        await db.execute("DELETE FROM attendance WHERE thread_id = ?", (thread_id,))
        await db.commit()


async def record_attendance(thread_id: int, user_id: int, response: str):
    """Record or update a user's attendance response."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO attendance (thread_id, user_id, response, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(thread_id, user_id) 
            DO UPDATE SET response = ?, updated_at = ?
        """, (
            thread_id,
            user_id,
            response,
            datetime.now().isoformat(),
            response,
            datetime.now().isoformat()
        ))
        await db.commit()


async def toggle_plus_one(thread_id: int, user_id: int) -> bool:
    """Toggle plus one status for a user. Returns new plus_one status."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get current plus_one status
        async with db.execute(
            "SELECT plus_one FROM attendance WHERE thread_id = ? AND user_id = ?",
            (thread_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            current_status = row[0] if row else 0
        
        # Toggle it
        new_status = 0 if current_status else 1
        
        # Update or insert
        await db.execute("""
            INSERT INTO attendance (thread_id, user_id, response, plus_one, updated_at)
            VALUES (?, ?, 'yes', ?, ?)
            ON CONFLICT(thread_id, user_id) 
            DO UPDATE SET plus_one = ?, updated_at = ?
        """, (
            thread_id,
            user_id,
            new_status,
            datetime.now().isoformat(),
            new_status,
            datetime.now().isoformat()
        ))
        await db.commit()
        return bool(new_status)


    async def toggle_baby(thread_id: int, user_id: int) -> bool:
        """Toggle baby status for a user. Returns new baby status."""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Get current baby status
            async with db.execute(
                "SELECT baby FROM attendance WHERE thread_id = ? AND user_id = ?",
                (thread_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                current_status = row[0] if row else 0
        
            # Toggle it
            new_status = 0 if current_status else 1
        
            # Update or insert
            await db.execute("""
                INSERT INTO attendance (thread_id, user_id, response, baby, updated_at)
                VALUES (?, ?, 'yes', ?, ?)
                ON CONFLICT(thread_id, user_id) 
                DO UPDATE SET baby = ?, updated_at = ?
            """, (
                thread_id,
                user_id,
                new_status,
                datetime.now().isoformat(),
                new_status,
                datetime.now().isoformat()
            ))
            await db.commit()
            return bool(new_status)


async def get_attendance_stats(thread_id: int) -> List[Dict]:
    """Get attendance statistics for an event."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM attendance WHERE thread_id = ? ORDER BY response, user_id",
            (thread_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_events_needing_close_prompt() -> List[Dict]:
    """Get events that ended 24+ hours ago and need close prompt."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Get events that:
        # 1. Are not archived
        # 2. Event date has passed by 24+ hours
        # 3. close_prompt_count < 2
        # 4. Either never prompted OR last prompt was 24+ hours ago
        twenty_four_hours_ago = (datetime.now() - timedelta(hours=24)).isoformat()
        
        async with db.execute("""
            SELECT * FROM events 
            WHERE archived = 0
            AND event_date < ?
            AND (close_prompt_count IS NULL OR close_prompt_count < 2)
            AND (last_close_prompt IS NULL OR last_close_prompt < ?)
        """, (twenty_four_hours_ago, twenty_four_hours_ago)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_close_prompt(thread_id: int):
    """Update close prompt tracking."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE events 
            SET close_prompt_count = COALESCE(close_prompt_count, 0) + 1,
                last_close_prompt = ?
            WHERE thread_id = ?
        """, (datetime.now().isoformat(), thread_id))
        await db.commit()

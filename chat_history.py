import sqlite3
from datetime import datetime

DB_FILE = "data/chat_history.db"


# Initialize DB
def init_db():
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute("""
       CREATE TABLE IF NOT EXISTS chats (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           session_id TEXT,
           role TEXT,
           content TEXT,
           timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
       )
   """)
   conn.commit()
   conn.close()


def save_message(session_id, role, content):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       "INSERT INTO chats (session_id, role, content) VALUES (?, ?, ?)",
       (session_id, role, content),
   )
   conn.commit()
   conn.close()


def load_messages(session_id):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       "SELECT role, content FROM chats WHERE session_id=? ORDER BY id ASC",
       (session_id,),
   )
   rows = c.fetchall()
   conn.close()
   return [{"role": r, "content": c} for r, c in rows]


def list_sessions():
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute("""
       SELECT session_id, MIN(timestamp)
       FROM chats
       GROUP BY session_id
       ORDER BY MIN(timestamp) DESC
   """)
   rows = c.fetchall()
   conn.close()
   return [sid for sid, _ in rows]


# Optional: get a short preview of each session
def list_sessions_with_preview(limit=30):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute("""
       SELECT session_id, MIN(timestamp),
              SUBSTR(MAX(CASE WHEN role='user' THEN content END), 1, ?) as preview
       FROM chats
       GROUP BY session_id
       ORDER BY MIN(timestamp) DESC
   """, (limit,))
   rows = c.fetchall()
   conn.close()
   return [{"session_id": sid, "started": ts, "preview": preview or ""} for sid, ts, preview in rows]
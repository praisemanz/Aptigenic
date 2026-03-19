import sqlite3
import json
import os
from datetime import datetime

IS_VERCEL = os.environ.get('VERCEL', '') == '1'
if IS_VERCEL:
    DB_PATH = '/tmp/aptigenic.db'
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), 'aptigenic.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            resume_text TEXT,
            target_role TEXT,
            timeline TEXT,
            work_preference TEXT,
            interests TEXT,
            education TEXT,
            experience_summary TEXT,
            analysis_json TEXT,
            onboarded INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT DEFAULT 'New Chat',
            active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            week INTEGER DEFAULT 1,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            completed INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id INTEGER,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        );
    """)
    conn.commit()
    conn.close()


# --- Users ---

def get_or_create_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO users (id, created_at, updated_at) VALUES (?, ?, ?)",
            (user_id, now, now)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row)


def update_user(user_id, **fields):
    conn = get_db()
    fields['updated_at'] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [user_id]
    conn.execute(f"UPDATE users SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_analysis(user_id, analysis_dict):
    update_user(user_id, analysis_json=json.dumps(analysis_dict))


def get_analysis(user_id):
    user = get_user(user_id)
    if user and user.get('analysis_json'):
        return json.loads(user['analysis_json'])
    return None


# --- Chat Sessions ---

def create_chat_session(user_id, title='New Chat'):
    conn = get_db()
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO chat_sessions (user_id, title, active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
        (user_id, title, now, now)
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_chat_sessions(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_session(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM chat_sessions WHERE user_id = ? AND active = 1 ORDER BY updated_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def set_active_session(user_id, session_id):
    conn = get_db()
    conn.execute("UPDATE chat_sessions SET active = 0 WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE chat_sessions SET active = 1 WHERE id = ? AND user_id = ?", (session_id, user_id))
    conn.commit()
    conn.close()


def update_session_title(session_id, title):
    conn = get_db()
    conn.execute("UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
                 (title, datetime.utcnow().isoformat(), session_id))
    conn.commit()
    conn.close()


def delete_chat_session(session_id, user_id):
    conn = get_db()
    conn.execute("DELETE FROM conversations WHERE session_id = ? AND user_id = ?", (session_id, user_id))
    conn.execute("DELETE FROM chat_sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
    conn.commit()
    conn.close()


# --- Actions ---

def add_actions(user_id, actions_list, week=1):
    conn = get_db()
    now = datetime.utcnow().isoformat()
    for a in actions_list:
        conn.execute(
            "INSERT INTO actions (user_id, week, title, description, category, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, week, a.get('title', ''), a.get('description', ''), a.get('category', ''), now)
        )
    conn.commit()
    conn.close()


def get_actions(user_id, week=None):
    conn = get_db()
    if week is not None:
        rows = conn.execute(
            "SELECT * FROM actions WHERE user_id = ? AND week = ? ORDER BY id", (user_id, week)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM actions WHERE user_id = ? ORDER BY week, id", (user_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_action(action_id, user_id):
    conn = get_db()
    conn.execute(
        "UPDATE actions SET completed = CASE WHEN completed = 1 THEN 0 ELSE 1 END WHERE id = ? AND user_id = ?",
        (action_id, user_id)
    )
    conn.commit()
    conn.close()


def clear_actions(user_id):
    conn = get_db()
    conn.execute("DELETE FROM actions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# --- Conversations ---

def save_message(user_id, role, content, session_id=None):
    conn = get_db()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO conversations (user_id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, session_id, role, content, now)
    )
    if session_id:
        conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    conn.commit()
    conn.close()


def get_conversation(user_id, session_id=None, limit=50):
    conn = get_db()
    if session_id:
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE user_id = ? AND session_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, session_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def clear_conversation(user_id, session_id=None):
    conn = get_db()
    if session_id:
        conn.execute("DELETE FROM conversations WHERE user_id = ? AND session_id = ?", (user_id, session_id))
    else:
        conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

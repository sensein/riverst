"""SQLite storage for the teacher dashboard.

The database lives outside ``sessions/`` on purpose: that folder is served
publicly through a static mount, and the dashboard database holds the roster.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SERVER_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = "data/dashboard.db"
SCHEMA_VERSION = 1

STEP_RESULT = "('completed', 'attempted_not_completed', 'not_reached')"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS teacher (
    email TEXT PRIMARY KEY,
    display_name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS class (
    id TEXT PRIMARY KEY,
    teacher_email TEXT NOT NULL UNIQUE REFERENCES teacher(email),
    name TEXT NOT NULL DEFAULT 'My class'
);

CREATE TABLE IF NOT EXISTS student (
    id TEXT PRIMARY KEY,
    class_id TEXT NOT NULL REFERENCES class(id),
    display_name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    user_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    reading_level_override INTEGER CHECK (reading_level_override BETWEEN 3 AND 8),
    override_set_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_student_class ON student(class_id);

CREATE TABLE IF NOT EXISTS session_record (
    id TEXT PRIMARY KEY,
    session_dir_id TEXT NOT NULL UNIQUE,
    student_id TEXT NOT NULL REFERENCES student(id),
    started_at TEXT NOT NULL,
    duration_seconds INTEGER,
    activity TEXT NOT NULL,
    book_id TEXT,
    book_title TEXT,
    chapter INTEGER,
    completion TEXT CHECK (completion IN ('completed', 'ended_early')),
    vocab_override_used INTEGER NOT NULL DEFAULT 0,
    analysis_status TEXT NOT NULL
        CHECK (analysis_status IN ('pending', 'running', 'ready', 'failed', 'not_applicable')),
    analysis_attempts INTEGER NOT NULL DEFAULT 0,
    analysis_error TEXT,
    summary_status TEXT NOT NULL DEFAULT 'pending' CHECK (summary_status IN ('pending', 'running', 'ready', 'failed')),
    summary_text TEXT,
    summary_json TEXT,
    ingested_at TEXT,
    analyzed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_session_student_started ON session_record(student_id, started_at DESC);

CREATE TABLE IF NOT EXISTS word_outcome (
    session_record_id TEXT NOT NULL REFERENCES session_record(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    grade_band INTEGER CHECK (grade_band IN (4, 5, 6)),
    teacher_selected INTEGER NOT NULL DEFAULT 0,
    disposition TEXT NOT NULL CHECK (disposition IN ('known', 'taught')),
    step_definition TEXT CHECK (step_definition IN {STEP_RESULT}),
    step_story_context TEXT CHECK (step_story_context IN {STEP_RESULT}),
    step_personal_connection TEXT CHECK (step_personal_connection IN {STEP_RESULT}),
    step_own_sentence TEXT CHECK (step_own_sentence IN {STEP_RESULT}),
    review_result TEXT CHECK (review_result IN ('mastered', 'not_mastered', 'not_reached')),
    position INTEGER NOT NULL,
    PRIMARY KEY (session_record_id, word)
);
CREATE INDEX IF NOT EXISTS idx_word_outcome_word ON word_outcome(word);

CREATE TABLE IF NOT EXISTS student_summary (
    student_id TEXT PRIMARY KEY REFERENCES student(id),
    text TEXT,
    strengths TEXT,
    difficulties TEXT,
    suggested_focus TEXT,
    based_on_sessions INTEGER NOT NULL DEFAULT 0,
    generated_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ready', 'failed'))
);

CREATE TABLE IF NOT EXISTS teacher_note (
    id TEXT PRIMARY KEY,
    teacher_email TEXT NOT NULL REFERENCES teacher(email),
    target_type TEXT NOT NULL CHECK (target_type IN ('student', 'session')),
    target_id TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_note_target ON teacher_note(teacher_email, target_type, target_id);
"""


def get_db_path() -> Path:
    """Resolve the database path from ``DASHBOARD_DB_PATH`` and make sure its folder exists.

    Returns:
        Path: Absolute path to the SQLite file. Relative settings resolve against ``src/server``.
    """
    path = Path(os.getenv("DASHBOARD_DB_PATH") or DEFAULT_DB_PATH)
    if not path.is_absolute():
        path = SERVER_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    """Open a connection with row access by name, foreign keys and WAL enabled.

    Returns:
        sqlite3.Connection: A new connection. Callers close it (``transaction`` does this).
    """
    conn = sqlite3.connect(get_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Run a block in a single transaction, committing on success and rolling back on error.

    Yields:
        sqlite3.Connection: The open connection.
    """
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    """Create all tables and indexes if missing, and record the schema version. Safe to call repeatedly."""
    with transaction() as conn:
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )

"""Database queries for the teacher dashboard.

Every teacher-facing read is scoped by ``class_id``. A record outside the class is treated as missing.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import codes
from .db import transaction

# Sessions that were created but never connected are hidden once they are this old.
NEVER_STARTED_AFTER = timedelta(hours=6)
MAX_NAME_LENGTH = 40
MAX_NOTE_LENGTH = 2000
STEP_COLUMNS = {
    "definition": "step_definition",
    "story_context": "step_story_context",
    "personal_connection": "step_personal_connection",
    "own_sentence": "step_own_sentence",
}
SESSION_FIELDS = {
    "duration_seconds",
    "completion",
    "analysis_status",
    "analysis_attempts",
    "analysis_error",
    "summary_status",
    "summary_text",
    "summary_json",
    "ingested_at",
    "analyzed_at",
}


def now_iso() -> str:
    """Current UTC time as ISO-8601 text."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def clean_display_name(raw: Any) -> str:
    """Validate a student display name.

    Args:
        raw: The submitted name.

    Returns:
        str: The trimmed name.

    Raises:
        ValueError: If the name is empty or longer than 40 characters.
    """
    name = " ".join(str(raw or "").split())
    if not name or len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Student name must be 1–{MAX_NAME_LENGTH} characters.")
    return name


# ---------- Teachers and students ----------


def ensure_teacher(email: str, name: Optional[str]) -> str:
    """Create the teacher and their default class on first visit.

    Args:
        email: Teacher's email (JWT ``sub``).
        name: Teacher's display name.

    Returns:
        str: The teacher's class ID.
    """
    with transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO teacher (email, display_name, created_at) VALUES (?, ?, ?)",
            (email, name, now_iso()),
        )
        row = conn.execute(
            "SELECT id FROM class WHERE teacher_email = ?", (email,)
        ).fetchone()
        if row:
            return row["id"]
        class_id = codes.new_id("c")
        conn.execute(
            "INSERT INTO class (id, teacher_email) VALUES (?, ?)", (class_id, email)
        )
        return class_id


def get_class(class_id: str) -> Dict[str, Any]:
    """Return the class row."""
    with transaction() as conn:
        return _dict(
            conn.execute(
                "SELECT id, name FROM class WHERE id = ?", (class_id,)
            ).fetchone()
        )


def _unique_code(conn: sqlite3.Connection) -> str:
    for _ in range(20):
        code = codes.generate_code()
        if not conn.execute("SELECT 1 FROM student WHERE code = ?", (code,)).fetchone():
            return code
    raise RuntimeError("Could not generate a unique student code")


def create_student(class_id: str, display_name: Any) -> Dict[str, Any]:
    """Add a student to a class with a new code and a stable ``user_key``.

    Args:
        class_id: The teacher's class.
        display_name: First name or nickname.

    Returns:
        Dict[str, Any]: The new student row.
    """
    name = clean_display_name(display_name)
    with transaction() as conn:
        student_id = codes.new_id("s")
        stamp = now_iso()
        conn.execute(
            "INSERT INTO student (id, class_id, display_name, code, user_key, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                student_id,
                class_id,
                name,
                _unique_code(conn),
                codes.generate_user_key(),
                stamp,
                stamp,
            ),
        )
        return dict(
            conn.execute("SELECT * FROM student WHERE id = ?", (student_id,)).fetchone()
        )


def get_student_by_code(code: str) -> Optional[Dict[str, Any]]:
    """Find an active student by code (already normalized)."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM student WHERE code = ? AND status = 'active'", (code,)
        ).fetchone()
        return _dict(row)


def get_student(class_id: str, student_id: str) -> Optional[Dict[str, Any]]:
    """Return a student only if they belong to the class."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM student WHERE id = ? AND class_id = ?",
            (student_id, class_id),
        ).fetchone()
        return _dict(row)


def update_student(
    class_id: str, student_id: str, changes: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Rename, archive/restore, or set/clear the reading-level override.

    Args:
        class_id: The teacher's class.
        student_id: The student to change.
        changes: Any of ``display_name``, ``status``, ``reading_level_override`` (only keys present are applied).

    Returns:
        Optional[Dict[str, Any]]: The updated row, or None if the student isn't in the class.
    """
    if get_student(class_id, student_id) is None:
        return None
    sets, values = [], []
    if "display_name" in changes:
        sets.append("display_name = ?")
        values.append(clean_display_name(changes["display_name"]))
    if "status" in changes:
        sets.append("status = ?")
        values.append(changes["status"])
    if "reading_level_override" in changes:
        sets += ["reading_level_override = ?", "override_set_at = ?"]
        override = changes["reading_level_override"]
        values += [override, now_iso() if override is not None else None]
    with transaction() as conn:
        if sets:
            conn.execute(
                f"UPDATE student SET {', '.join(sets)}, updated_at = ? WHERE id = ?",
                (*values, now_iso(), student_id),
            )
        return dict(
            conn.execute("SELECT * FROM student WHERE id = ?", (student_id,)).fetchone()
        )


def regenerate_code(class_id: str, student_id: str) -> Optional[Dict[str, Any]]:
    """Give a student a new code; the old one stops working immediately."""
    if get_student(class_id, student_id) is None:
        return None
    with transaction() as conn:
        conn.execute(
            "UPDATE student SET code = ?, updated_at = ? WHERE id = ?",
            (_unique_code(conn), now_iso(), student_id),
        )
        return dict(
            conn.execute("SELECT * FROM student WHERE id = ?", (student_id,)).fetchone()
        )


# ---------- Session records ----------


def create_session_record(
    session_dir_id: str,
    student_id: str,
    started_at: str,
    activity: str,
    book_id: Optional[str],
    book_title: Optional[str],
    chapter: Optional[int],
    vocab_override_used: bool,
    analysis_status: str,
) -> str:
    """Index a new student session.

    Returns:
        str: The opaque session record ID shown to teachers.
    """
    record_id = codes.new_id("r")
    with transaction() as conn:
        conn.execute(
            "INSERT INTO session_record (id, session_dir_id, student_id, started_at, activity, book_id, book_title,"
            " chapter, vocab_override_used, analysis_status, summary_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record_id,
                session_dir_id,
                student_id,
                started_at,
                activity,
                book_id,
                book_title,
                chapter,
                int(bool(vocab_override_used)),
                analysis_status,
                "pending" if analysis_status != "not_applicable" else "failed",
            ),
        )
    return record_id


def get_session_record_by_dir(session_dir_id: str) -> Optional[Dict[str, Any]]:
    """Look up a session record by its session folder name."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM session_record WHERE session_dir_id = ?", (session_dir_id,)
        ).fetchone()
        return _dict(row)


def get_session_record(record_id: str) -> Optional[Dict[str, Any]]:
    """Look up a session record by ID (internal use, not class-scoped)."""
    with transaction() as conn:
        return _dict(
            conn.execute(
                "SELECT * FROM session_record WHERE id = ?", (record_id,)
            ).fetchone()
        )


def update_session_fields(record_id: str, **fields: Any) -> None:
    """Update whitelisted columns of a session record."""
    unknown = set(fields) - SESSION_FIELDS
    if unknown:
        raise ValueError(f"Unknown session fields: {sorted(unknown)}")
    if not fields:
        return
    assignments = ", ".join(f"{name} = ?" for name in fields)
    with transaction() as conn:
        conn.execute(
            f"UPDATE session_record SET {assignments} WHERE id = ?",
            (*fields.values(), record_id),
        )


def claim_for_analysis(record_id: str) -> bool:
    """Atomically move a record from ``pending`` to ``running``.

    Returns:
        bool: True if this caller now owns the analysis run.
    """
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE session_record SET analysis_status = 'running' WHERE id = ? AND analysis_status = 'pending'",
            (record_id,),
        )
        return cur.rowcount == 1


def records_awaiting_analysis() -> List[Dict[str, Any]]:
    """Records left ``pending`` or ``running`` (for example after a restart)."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM session_record WHERE analysis_status IN ('pending', 'running')"
            " OR (analysis_status = 'ready' AND summary_status IN ('pending', 'running'))"
        ).fetchall()
        return [dict(r) for r in rows]


def replace_word_outcomes(record_id: str, outcomes: List[Dict[str, Any]]) -> None:
    """Replace all word outcomes of a session.

    Args:
        record_id: The session record.
        outcomes: Dicts with ``word``, ``grade_band``, ``teacher_selected``, ``disposition``,
            ``review_result``, ``position`` and an optional ``steps`` dict keyed by step name.
    """
    with transaction() as conn:
        conn.execute(
            "DELETE FROM word_outcome WHERE session_record_id = ?", (record_id,)
        )
        for o in outcomes:
            steps = o.get("steps") or {}
            conn.execute(
                "INSERT INTO word_outcome (session_record_id, word, grade_band, teacher_selected, disposition,"
                " step_definition, step_story_context, step_personal_connection, step_own_sentence, review_result,"
                " position) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id,
                    o["word"],
                    o.get("grade_band"),
                    int(bool(o.get("teacher_selected"))),
                    o["disposition"],
                    *(steps.get(step) for step in STEP_COLUMNS),
                    o.get("review_result"),
                    o["position"],
                ),
            )


def _outcome_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "word": row["word"],
        "grade_band": row["grade_band"],
        "teacher_selected": bool(row["teacher_selected"]),
        "disposition": row["disposition"],
        "review_result": row["review_result"],
        "position": row["position"],
        "steps": {step: row[col] for step, col in STEP_COLUMNS.items()},
    }


def get_word_outcomes(record_id: str) -> List[Dict[str, Any]]:
    """Word outcomes of one session in the order they came up."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM word_outcome WHERE session_record_id = ? ORDER BY position",
            (record_id,),
        ).fetchall()
        return [_outcome_from_row(r) for r in rows]


def _session_view(
    record: Dict[str, Any], words: List[Dict[str, Any]]
) -> Dict[str, Any]:
    return {**record, "ingested": record.get("ingested_at") is not None, "words": words}


def _sessions_for_students(
    conn: sqlite3.Connection, student_ids: List[str]
) -> Dict[str, List[Dict[str, Any]]]:
    by_student: Dict[str, List[Dict[str, Any]]] = {sid: [] for sid in student_ids}
    if not student_ids:
        return by_student
    marks = ",".join("?" * len(student_ids))
    cutoff = (datetime.now(timezone.utc) - NEVER_STARTED_AFTER).isoformat(
        timespec="seconds"
    )
    records = conn.execute(
        f"SELECT * FROM session_record WHERE student_id IN ({marks})"
        " AND NOT (ingested_at IS NULL AND completion IS NULL"
        " AND analysis_status = 'pending' AND started_at < ?)"
        " ORDER BY started_at DESC",
        [*student_ids, cutoff],
    ).fetchall()
    words: Dict[str, List[Dict[str, Any]]] = {r["id"]: [] for r in records}
    if records:
        rows = conn.execute(
            f"SELECT w.* FROM word_outcome w JOIN session_record r ON r.id = w.session_record_id"
            f" WHERE r.student_id IN ({marks}) ORDER BY w.position",
            student_ids,
        ).fetchall()
        for row in rows:
            words[row["session_record_id"]].append(_outcome_from_row(row))
    for record in records:
        by_student[record["student_id"]].append(
            _session_view(dict(record), words[record["id"]])
        )
    return by_student


def list_class_students(
    class_id: str, status: Optional[str] = "active"
) -> List[Dict[str, Any]]:
    """All students of a class with their sessions and word outcomes, in three queries.

    Args:
        class_id: The teacher's class.
        status: ``active``, ``archived``, or None for both.

    Returns:
        List[Dict[str, Any]]: Student rows, each with a ``sessions`` list (newest first).
    """
    with transaction() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM student WHERE class_id = ? AND status = ? ORDER BY display_name",
                (class_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM student WHERE class_id = ? ORDER BY display_name",
                (class_id,),
            ).fetchall()
        students = [dict(r) for r in rows]
        sessions = _sessions_for_students(conn, [s["id"] for s in students])
    for student in students:
        student["sessions"] = sessions[student["id"]]
    return students


def get_student_detail(class_id: str, student_id: str) -> Optional[Dict[str, Any]]:
    """A student with their sessions, word outcomes and stored progress summary."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM student WHERE id = ? AND class_id = ?",
            (student_id, class_id),
        ).fetchone()
        if row is None:
            return None
        student = dict(row)
        student["sessions"] = _sessions_for_students(conn, [student_id])[student_id]
        student["summary"] = _dict(
            conn.execute(
                "SELECT * FROM student_summary WHERE student_id = ?", (student_id,)
            ).fetchone()
        )
    return student


def get_student_sessions(student_id: str) -> List[Dict[str, Any]]:
    """A student's sessions with word outcomes (internal use, not class-scoped)."""
    with transaction() as conn:
        return _sessions_for_students(conn, [student_id])[student_id]


def get_session_for_class(class_id: str, record_id: str) -> Optional[Dict[str, Any]]:
    """A session record with its student and word outcomes, only if the student is in the class."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT r.*, s.display_name AS student_name FROM session_record r JOIN student s ON s.id = r.student_id"
            " WHERE r.id = ? AND s.class_id = ?",
            (record_id, class_id),
        ).fetchone()
        if row is None:
            return None
        record = dict(row)
    record["words"] = get_word_outcomes(record_id)
    return record


def save_student_summary(
    student_id: str, summary: Optional[Dict[str, Any]], based_on: int
) -> None:
    """Store a generated progress summary, or a failed marker when ``summary`` is None."""
    fields = summary or {}
    with transaction() as conn:
        conn.execute(
            "INSERT INTO student_summary (student_id, text, strengths, difficulties, suggested_focus,"
            " based_on_sessions, generated_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(student_id) DO UPDATE SET text = excluded.text, strengths = excluded.strengths,"
            " difficulties = excluded.difficulties, suggested_focus = excluded.suggested_focus,"
            " based_on_sessions = excluded.based_on_sessions, generated_at = excluded.generated_at,"
            " status = excluded.status",
            (
                student_id,
                fields.get("text"),
                fields.get("strengths"),
                fields.get("difficulties"),
                fields.get("suggested_focus"),
                based_on,
                now_iso(),
                "ready" if summary else "failed",
            ),
        )


# ---------- Notes ----------


def clean_note_body(raw: Any) -> str:
    """Validate a note body (1–2,000 characters after trimming)."""
    body = str(raw or "").strip()
    if not body or len(body) > MAX_NOTE_LENGTH:
        raise ValueError(f"Notes must be 1–{MAX_NOTE_LENGTH} characters.")
    return body


def note_target_in_class(class_id: str, target_type: str, target_id: str) -> bool:
    """Whether a note target (student or session) belongs to the class."""
    if target_type == "student":
        return get_student(class_id, target_id) is not None
    if target_type == "session":
        with transaction() as conn:
            row = conn.execute(
                "SELECT 1 FROM session_record r JOIN student s ON s.id = r.student_id"
                " WHERE r.id = ? AND s.class_id = ?",
                (target_id, class_id),
            ).fetchone()
            return row is not None
    return False


def list_notes(
    teacher_email: str, target_type: str, target_id: str
) -> List[Dict[str, Any]]:
    """The teacher's own notes on one target, newest first."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT id, body, created_at, updated_at FROM teacher_note"
            " WHERE teacher_email = ? AND target_type = ? AND target_id = ? ORDER BY created_at DESC",
            (teacher_email, target_type, target_id),
        ).fetchall()
        return [dict(r) for r in rows]


def create_note(
    teacher_email: str, target_type: str, target_id: str, body: Any
) -> Dict[str, Any]:
    """Add a private note."""
    note_id = codes.new_id("n")
    stamp = now_iso()
    with transaction() as conn:
        conn.execute(
            "INSERT INTO teacher_note (id, teacher_email, target_type, target_id, body, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                note_id,
                teacher_email,
                target_type,
                target_id,
                clean_note_body(body),
                stamp,
                stamp,
            ),
        )
    return {
        "id": note_id,
        "body": clean_note_body(body),
        "created_at": stamp,
        "updated_at": stamp,
    }


def update_note(
    teacher_email: str, note_id: str, body: Any
) -> Optional[Dict[str, Any]]:
    """Edit one of the teacher's own notes."""
    clean = clean_note_body(body)
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE teacher_note SET body = ?, updated_at = ? WHERE id = ? AND teacher_email = ?",
            (clean, now_iso(), note_id, teacher_email),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, body, created_at, updated_at FROM teacher_note WHERE id = ?",
            (note_id,),
        )
        return dict(row.fetchone())


def delete_note(teacher_email: str, note_id: str) -> bool:
    """Delete one of the teacher's own notes."""
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM teacher_note WHERE id = ? AND teacher_email = ?",
            (note_id, teacher_email),
        )
        return cur.rowcount == 1

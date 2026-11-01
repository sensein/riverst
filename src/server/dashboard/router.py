"""Teacher dashboard API (``/api/teacher``). See ``specs/010-teacher-dashboard/contracts/rest-api.md``.

Responses never include session folder IDs, student ``user_key``s, transcripts, the student's own
words, audio paths or internal errors. Anything outside the caller's class is a 404.
"""

import json
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from authorization.auth import require_teacher

from . import analysis, metrics, repository

router = APIRouter(prefix="/api/teacher")

ACTIVITY_LABELS = {analysis.VOCAB_ACTIVITY: "Child vocabulary training"}
STUDENT_NOT_FOUND = "Student not found."
SESSION_NOT_FOUND = "Session not found."
NOTE_NOT_FOUND = "Note not found."


class Teacher(BaseModel):
    """The signed-in teacher and their class."""

    email: str
    class_id: str


def current_teacher(user: dict = Depends(require_teacher)) -> Teacher:
    """Resolve the signed-in teacher, creating their class on first visit."""
    return Teacher(
        email=user["sub"],
        class_id=repository.ensure_teacher(user["sub"], user.get("name")),
    )


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
    )


# ---------- Shaping helpers ----------


def student_link(code: str) -> str:
    """Relative link a student opens to start KIVA with their code."""
    return f"/kiva?code={code}"


def _student_base(student: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": student["id"],
        "display_name": student["display_name"],
        "code": student["code"],
        "link": student_link(student["code"]),
        "status": student["status"],
    }


def _levels(student: Dict[str, Any], sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    estimate = metrics.reading_level_estimate(sessions)
    return {
        "reading_level": metrics.display_reading_level(
            estimate, student.get("reading_level_override")
        ),
        "reading_level_estimate": metrics.display_reading_level(estimate),
    }


def _detail_state(record: Dict[str, Any]) -> str:
    state = record["analysis_status"]
    if state == "ready":
        return "ready"
    if state in ("pending", "running"):
        return "pending"
    if state == "not_applicable":
        return "not_applicable"
    return "unavailable"


def _summary_block(record: Dict[str, Any]) -> Dict[str, Any]:
    state = record["summary_status"]
    if record["analysis_status"] == "failed" and state != "ready":
        state = "failed"
    block: Dict[str, Any] = {"status": "pending" if state == "running" else state}
    if state == "ready" and record.get("summary_json"):
        data = json.loads(record["summary_json"])
        block.update(
            text=data.get("text"),
            engagement=data.get("engagement"),
            words_went_well=data.get("words_went_well", []),
            words_hard=data.get("words_hard", []),
            notable_moments=data.get("notable_moments", []),
            suggestions=data.get("suggestions", []),
        )
    return block


def _session_list_item(record: Dict[str, Any]) -> Dict[str, Any]:
    taught = [w for w in record["words"] if w["disposition"] == "taught"]
    return {
        "id": record["id"],
        "started_at": record["started_at"],
        "book_title": record["book_title"],
        "chapter": record["chapter"],
        "completion": record["completion"],
        "detail": _detail_state(record),
        "words_taught": len(taught),
        "words_mastered": sum(
            1 for w in taught if w.get("review_result") == "mastered"
        ),
    }


def _class_row(student: Dict[str, Any]) -> Dict[str, Any]:
    sessions = student["sessions"]
    counts = metrics.cumulative_counts(sessions)
    return {
        **_student_base(student),
        "status": (
            metrics.student_status(sessions)
            if student["status"] == "active"
            else "archived"
        ),
        "last_session_at": sessions[0]["started_at"] if sessions else None,
        "sessions_completed": sum(
            1 for s in sessions if s.get("completion") == "completed"
        ),
        "words_mastered": counts["mastered"],
        "reading_level": _levels(student, sessions)["reading_level"],
    }


def _student_detail(student: Dict[str, Any]) -> Dict[str, Any]:
    sessions = student["sessions"]
    summary = student.get("summary")
    return {
        "student": {
            **_student_base(student),
            "class_status": (
                metrics.student_status(sessions)
                if student["status"] == "active"
                else "archived"
            ),
            "reading_level_override": student.get("reading_level_override"),
            **_levels(student, sessions),
        },
        "counts": metrics.cumulative_counts(sessions),
        "reading_level_trend": metrics.reading_level_trend(sessions),
        "summary": {
            "status": summary["status"] if summary else "none",
            "text": summary.get("text") if summary else None,
            "generated_at": summary.get("generated_at") if summary else None,
        },
        "words": [
            {
                k: w[k]
                for k in (
                    "word",
                    "status",
                    "grade_band",
                    "last_seen_session_id",
                    "last_seen_at",
                    "history",
                )
            }
            for w in metrics.word_statuses(sessions)
        ],
        "sessions": [_session_list_item(s) for s in sessions],
    }


# ---------- Class & students ----------


class NewStudent(BaseModel):
    """Body of ``POST /students``."""

    display_name: str = Field(..., min_length=1, max_length=40)


class StudentChanges(BaseModel):
    """Body of ``PATCH /students/{id}``; only fields sent are changed."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=40)
    status: Optional[Literal["active", "archived"]] = None
    reading_level_override: Optional[int] = Field(None, ge=3, le=8)


@router.get("/class")
def get_class(
    teacher: Teacher = Depends(current_teacher),
    student_status: Literal["active", "archived"] = Query("active", alias="status"),
    sort: Literal["name", "last_session", "words_mastered"] = "name",
    order: Literal["asc", "desc"] = "asc",
) -> JSONResponse:
    """The class list with each student's status, last session, reading level and words mastered."""
    rows = [
        _class_row(s)
        for s in repository.list_class_students(teacher.class_id, student_status)
    ]
    keys = {
        "name": lambda r: r["display_name"].lower(),
        "last_session": lambda r: r["last_session_at"] or "",
        "words_mastered": lambda r: r["words_mastered"],
    }
    rows.sort(key=keys[sort], reverse=order == "desc")
    return JSONResponse(
        {"class": repository.get_class(teacher.class_id), "students": rows}
    )


@router.post("/students", status_code=status.HTTP_201_CREATED)
def add_student(
    body: NewStudent, teacher: Teacher = Depends(current_teacher)
) -> JSONResponse:
    """Add a student; the response includes their code and link."""
    try:
        student = repository.create_student(teacher.class_id, body.display_name)
    except ValueError as e:
        raise _bad_request(str(e))
    return JSONResponse(_student_base(student), status_code=status.HTTP_201_CREATED)


@router.patch("/students/{student_id}")
def change_student(
    student_id: str, body: StudentChanges, teacher: Teacher = Depends(current_teacher)
) -> JSONResponse:
    """Rename, archive/restore, or set/clear the reading-level override."""
    try:
        student = repository.update_student(
            teacher.class_id, student_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise _bad_request(str(e))
    if student is None:
        raise _not_found(STUDENT_NOT_FOUND)
    return JSONResponse(
        _student_base(student)
        | {"reading_level_override": student["reading_level_override"]}
    )


@router.post("/students/{student_id}/code")
def new_code(
    student_id: str, teacher: Teacher = Depends(current_teacher)
) -> JSONResponse:
    """Give the student a new code. The old code stops working; past sessions stay linked."""
    student = repository.regenerate_code(teacher.class_id, student_id)
    if student is None:
        raise _not_found(STUDENT_NOT_FOUND)
    return JSONResponse(
        {"code": student["code"], "link": student_link(student["code"])}
    )


@router.get("/students/{student_id}")
def student_detail(
    student_id: str, teacher: Teacher = Depends(current_teacher)
) -> JSONResponse:
    """The student page: reading level, counts, words, sessions and progress summary."""
    student = repository.get_student_detail(teacher.class_id, student_id)
    if student is None:
        raise _not_found(STUDENT_NOT_FOUND)
    return JSONResponse(_student_detail(student))


@router.get("/students/{student_id}/report")
def student_report(
    student_id: str, teacher: Teacher = Depends(current_teacher)
) -> JSONResponse:
    """Everything for the printable progress report, including the teacher's notes on the student."""
    student = repository.get_student_detail(teacher.class_id, student_id)
    if student is None:
        raise _not_found(STUDENT_NOT_FOUND)
    return JSONResponse(
        _student_detail(student)
        | {
            "notes": repository.list_notes(teacher.email, "student", student_id),
            "generated_at": repository.now_iso(),
        }
    )


# ---------- Sessions ----------


@router.get("/sessions/{record_id}")
def session_detail(
    record_id: str, teacher: Teacher = Depends(current_teacher)
) -> JSONResponse:
    """Per-word outcomes and the summary of one session. No raw session content."""
    record = repository.get_session_for_class(teacher.class_id, record_id)
    if record is None:
        raise _not_found(SESSION_NOT_FOUND)
    words = record["words"]
    return JSONResponse(
        {
            "session": {
                "id": record["id"],
                "student_id": record["student_id"],
                "student_name": record["student_name"],
                "started_at": record["started_at"],
                "duration_seconds": record["duration_seconds"],
                "activity_label": ACTIVITY_LABELS.get(
                    record["activity"], record["activity"]
                ),
                "book_title": record["book_title"],
                "chapter": record["chapter"],
                "completion": record["completion"],
                "teacher_selected_words": bool(record["vocab_override_used"]),
            },
            "detail": _detail_state(record),
            "already_knew": [
                {"word": w["word"], "grade_band": w["grade_band"]}
                for w in words
                if w["disposition"] == "known"
            ],
            "taught": [
                {
                    "word": w["word"],
                    "grade_band": w["grade_band"],
                    "teacher_selected": w["teacher_selected"],
                    "steps": w["steps"],
                    "review": w["review_result"],
                }
                for w in words
                if w["disposition"] == "taught"
            ],
            "summary": _summary_block(record),
        }
    )


@router.post("/sessions/{record_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_session(
    record_id: str, teacher: Teacher = Depends(current_teacher)
) -> Response:
    """Redo a failed analysis or summary."""
    record = repository.get_session_for_class(teacher.class_id, record_id)
    if record is None:
        raise _not_found(SESSION_NOT_FOUND)
    if "running" in (record["analysis_status"], record["summary_status"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already working on it."
        )
    if record["analysis_status"] == "not_applicable":
        raise _bad_request("This session has no vocabulary results to prepare.")
    if "failed" not in (record["analysis_status"], record["summary_status"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Nothing to retry."
        )
    analysis.reset_for_retry(record)
    analysis.schedule_post_session(record["session_dir_id"])
    return Response(status_code=status.HTTP_202_ACCEPTED)


# ---------- Class insights ----------


@router.get("/insights/words")
def word_insights(
    teacher: Teacher = Depends(current_teacher),
    sort: Literal["mastery_rate", "taught", "word"] = "mastery_rate",
) -> JSONResponse:
    """Per-word results across the class."""
    words = metrics.class_word_insights(
        repository.list_class_students(teacher.class_id, "active")
    )
    if sort == "mastery_rate":
        words.sort(
            key=lambda w: (w["mastery_rate"] is None, w["mastery_rate"] or 0, w["word"])
        )
    elif sort == "taught":
        words.sort(key=lambda w: (-w["taught"], w["word"]))
    return JSONResponse({"words": words})


# ---------- Notes ----------


class NewNote(BaseModel):
    """Body of ``POST /notes``."""

    target_type: Literal["student", "session"]
    target_id: str
    body: str = Field(..., min_length=1, max_length=2000)


class NoteChanges(BaseModel):
    """Body of ``PATCH /notes/{id}``."""

    body: str = Field(..., min_length=1, max_length=2000)


@router.get("/notes")
def get_notes(
    target_type: Literal["student", "session"],
    target_id: str,
    teacher: Teacher = Depends(current_teacher),
) -> JSONResponse:
    """The teacher's own notes on a student or session."""
    if not repository.note_target_in_class(teacher.class_id, target_type, target_id):
        raise _not_found(NOTE_NOT_FOUND)
    return JSONResponse(
        {"notes": repository.list_notes(teacher.email, target_type, target_id)}
    )


@router.post("/notes", status_code=status.HTTP_201_CREATED)
def add_note(
    body: NewNote, teacher: Teacher = Depends(current_teacher)
) -> JSONResponse:
    """Add a private note."""
    if not repository.note_target_in_class(
        teacher.class_id, body.target_type, body.target_id
    ):
        raise _not_found(NOTE_NOT_FOUND)
    try:
        note = repository.create_note(
            teacher.email, body.target_type, body.target_id, body.body
        )
    except ValueError as e:
        raise _bad_request(str(e))
    return JSONResponse(note, status_code=status.HTTP_201_CREATED)


@router.patch("/notes/{note_id}")
def edit_note(
    note_id: str, body: NoteChanges, teacher: Teacher = Depends(current_teacher)
) -> JSONResponse:
    """Edit one of the teacher's own notes."""
    try:
        note = repository.update_note(teacher.email, note_id, body.body)
    except ValueError as e:
        raise _bad_request(str(e))
    if note is None:
        raise _not_found(NOTE_NOT_FOUND)
    return JSONResponse(note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_note(note_id: str, teacher: Teacher = Depends(current_teacher)) -> Response:
    """Delete one of the teacher's own notes."""
    if not repository.delete_note(teacher.email, note_id):
        raise _not_found(NOTE_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

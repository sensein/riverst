"""Pure progress calculations for the teacher dashboard (no database or I/O).

Sessions are plain dicts::

    {
        "id": "r_x", "started_at": "2026-10-07T14:02:00+00:00", "completion": "completed" | "ended_early" | None,
        "ingested": True,
        "words": [{"word", "grade_band", "disposition", "review_result",
                   "steps": {"definition", "story_context", "personal_connection", "own_sentence"}}],
    }
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Union

STEPS = ("definition", "story_context", "personal_connection", "own_sentence")
GRADE_BANDS = (4, 5, 6)
LEVEL_WINDOW = 5
LEVEL_THRESHOLD = 2 / 3
LEVEL_MIN_WORDS = 2
MIN_SESSIONS_FOR_LEVEL = 2
INACTIVE_AFTER = timedelta(days=7)

LevelEstimate = Union[int, str, None]  # 4/5/6, "below_4", or None (not enough sessions)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _chronological(sessions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(sessions, key=lambda s: s["started_at"])


def _word_result(outcome: Dict[str, Any]) -> str:
    if outcome["disposition"] == "known":
        return "known"
    return outcome.get("review_result") or "not_reached"


def _latest_status(result: str) -> str:
    if result == "known":
        return "already_knew"
    if result == "mastered":
        return "mastered"
    return "still_learning"


def word_statuses(sessions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Latest status and history for every word a student has met.

    Args:
        sessions: The student's sessions with their word outcomes.

    Returns:
        List[Dict[str, Any]]: One entry per word, ordered by word, with ``status``
        (``already_knew`` / ``mastered`` / ``still_learning``), ``grade_band``,
        ``last_seen_session_id``, ``last_seen_at`` and ``history`` (oldest first).
    """
    words: Dict[str, Dict[str, Any]] = {}
    for session in _chronological(sessions):
        for outcome in session.get("words", []):
            result = _word_result(outcome)
            entry = words.setdefault(
                outcome["word"], {"word": outcome["word"], "history": []}
            )
            entry["history"].append({"session_id": session["id"], "result": result})
            entry["status"] = _latest_status(result)
            entry["grade_band"] = outcome.get("grade_band") or entry.get("grade_band")
            entry["last_seen_session_id"] = session["id"]
            entry["last_seen_at"] = session["started_at"]
    return [words[w] for w in sorted(words)]


def cumulative_counts(sessions: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Totals shown on the student page and the class list.

    Args:
        sessions: The student's sessions with their word outcomes.

    Returns:
        Dict[str, int]: ``already_knew``, ``mastered`` and ``still_learning`` by latest word status,
        and ``taught``, the number of distinct words ever taught.
    """
    sessions = list(sessions)
    statuses = word_statuses(sessions)
    taught = {
        o["word"]
        for s in sessions
        for o in s.get("words", [])
        if o["disposition"] == "taught"
    }
    return {
        "already_knew": sum(1 for w in statuses if w["status"] == "already_knew"),
        "taught": len(taught),
        "mastered": sum(1 for w in statuses if w["status"] == "mastered"),
        "still_learning": sum(1 for w in statuses if w["status"] == "still_learning"),
    }


def reading_level_estimate(sessions: Iterable[Dict[str, Any]]) -> LevelEstimate:
    """Estimate reading level from the grade bands of words the student mastered or already knew.

    Uses the last 5 sessions with word outcomes. A band qualifies when the student met at least
    2 of its words there and mastered or already knew at least two-thirds of them. The highest
    qualifying band wins.

    Args:
        sessions: The student's sessions with their word outcomes.

    Returns:
        LevelEstimate: 4, 5 or 6; ``"below_4"`` if no band qualifies; None with fewer than 2 sessions.
    """
    recent = [s for s in _chronological(sessions) if s.get("ingested")][-LEVEL_WINDOW:]
    if len(recent) < MIN_SESSIONS_FOR_LEVEL:
        return None
    best: LevelEstimate = "below_4"
    for band in GRADE_BANDS:
        outcomes = [
            o for s in recent for o in s.get("words", []) if o.get("grade_band") == band
        ]
        if len(outcomes) < LEVEL_MIN_WORDS:
            continue
        good = sum(1 for o in outcomes if _word_result(o) in ("known", "mastered"))
        if good / len(outcomes) >= LEVEL_THRESHOLD - 1e-9:
            best = band
    return best


def level_number(level: LevelEstimate) -> Optional[int]:
    """Numeric form of a level for trends, with ``below_4`` as 3.

    Args:
        level: A reading-level estimate.

    Returns:
        Optional[int]: The grade number, or None when there is no estimate.
    """
    if level == "below_4":
        return 3
    return level if isinstance(level, int) else None


def reading_level_trend(sessions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reading-level estimate after each session, oldest first.

    Args:
        sessions: The student's sessions with their word outcomes.

    Returns:
        List[Dict[str, Any]]: ``{session_id, date, level}`` from the second ingested session on.
    """
    ingested = [s for s in _chronological(sessions) if s.get("ingested")]
    trend = []
    for i in range(MIN_SESSIONS_FOR_LEVEL - 1, len(ingested)):
        level = level_number(reading_level_estimate(ingested[: i + 1]))
        if level is not None:
            trend.append(
                {
                    "session_id": ingested[i]["id"],
                    "date": ingested[i]["started_at"],
                    "level": level,
                }
            )
    return trend


def display_reading_level(
    estimate: LevelEstimate, override: Optional[int] = None
) -> Dict[str, Any]:
    """The reading level as shown to the teacher.

    Args:
        estimate: The automatic estimate.
        override: A teacher-set grade (3–8), or None.

    Returns:
        Dict[str, Any]: ``{value, source, label}`` where source is ``teacher`` or ``estimate``.
    """
    if override is not None:
        return {"value": override, "source": "teacher", "label": f"Grade {override}"}
    if estimate == "below_4":
        return {"value": 3, "source": "estimate", "label": "Below grade-4 words"}
    if isinstance(estimate, int):
        return {
            "value": estimate,
            "source": "estimate",
            "label": f"Grade {estimate} words",
        }
    return {"value": None, "source": "estimate", "label": "Not enough sessions yet"}


def _mostly_not_mastered(session: Dict[str, Any]) -> bool:
    taught = [o for o in session.get("words", []) if o["disposition"] == "taught"]
    if not taught:
        return False
    not_mastered = sum(1 for o in taught if o.get("review_result") != "mastered")
    return not_mastered * 2 >= len(taught)


def student_status(
    sessions: Iterable[Dict[str, Any]], now: Optional[datetime] = None
) -> str:
    """Class-list status for a student. The first matching rule wins.

    Args:
        sessions: The student's sessions with their word outcomes.
        now: Current time (defaults to now, UTC).

    Returns:
        str: ``no_sessions``, ``inactive`` (no session in more than 7 days), ``needs_attention``
        (each of the last 2 completed sessions taught at least 1 word and at least half were not
        mastered) or ``on_track``.
    """
    ordered = _chronological(sessions)
    if not ordered:
        return "no_sessions"
    now = now or datetime.now(timezone.utc)
    if now - _parse_time(ordered[-1]["started_at"]) > INACTIVE_AFTER:
        return "inactive"
    completed = [s for s in ordered if s.get("completion") == "completed"][-2:]
    if len(completed) == 2 and all(_mostly_not_mastered(s) for s in completed):
        return "needs_attention"
    return "on_track"


def class_word_insights(students: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-word results across a class, using each student's latest result for the word.

    Args:
        students: ``{id, display_name, sessions}`` for each active student.

    Returns:
        List[Dict[str, Any]]: One entry per word with ``already_knew``, ``taught``, ``mastered``,
        ``still_learning``, ``mastery_rate`` (None when never taught), ``hardest_step`` (the step most
        often tried but not completed, or None) and ``still_learning_students``.
    """
    words: Dict[str, Dict[str, Any]] = {}
    for student in students:
        latest: Dict[str, Dict[str, Any]] = {}
        for session in _chronological(student.get("sessions", [])):
            for outcome in session.get("words", []):
                latest[outcome["word"]] = outcome
        for word, outcome in latest.items():
            entry = words.setdefault(
                word,
                {
                    "word": word,
                    "grade_band": outcome.get("grade_band"),
                    "already_knew": 0,
                    "taught": 0,
                    "mastered": 0,
                    "still_learning": 0,
                    "step_misses": {step: 0 for step in STEPS},
                    "still_learning_students": [],
                },
            )
            entry["grade_band"] = entry["grade_band"] or outcome.get("grade_band")
            status = _latest_status(_word_result(outcome))
            entry[status] += 1
            if outcome["disposition"] == "taught":
                entry["taught"] += 1
                for step in STEPS:
                    if (outcome.get("steps") or {}).get(
                        step
                    ) == "attempted_not_completed":
                        entry["step_misses"][step] += 1
            if status == "still_learning":
                entry["still_learning_students"].append(
                    {"id": student["id"], "display_name": student["display_name"]}
                )

    results = []
    for entry in words.values():
        misses = entry.pop("step_misses")
        top = max(misses.values())
        leaders = [step for step, count in misses.items() if count == top]
        entry["hardest_step"] = leaders[0] if top > 0 and len(leaders) == 1 else None
        entry["mastery_rate"] = (
            round(entry["mastered"] / entry["taught"], 2) if entry["taught"] else None
        )
        results.append(entry)
    return sorted(results, key=lambda e: e["word"])

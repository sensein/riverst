"""Post-session analysis for the teacher dashboard.

1. ``ingest_flow_state`` stores the tutor's own decisions (known / taught / mastered) from ``flow_state.json``.
2. ``run_post_session`` asks an LLM to classify each taught word's four teaching steps from the transcript,
   then writes a session summary that is checked against the outcomes and for quotes.
3. ``generate_student_summary`` refreshes the student's progress summary from aggregates only.

See ``specs/010-teacher-dashboard/contracts/session-analysis.md``.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from . import metrics, repository, validators
from .db import SERVER_DIR
from .flow_snapshot import read_snapshot

SESSIONS_ROOT = SERVER_DIR / "sessions"
AUDIOBOOK_RESOURCES = SERVER_DIR / "activities" / "audiobook" / "resources"
VOCAB_ACTIVITY = "vocab-tutoring"
REPORT_FILE = "learning_report.json"
MAX_ATTEMPTS = 2
STEP_VALUES = ["completed", "attempted_not_completed", "not_reached"]
COMPLETED_NODES = {"closing", "end"}
WORD_NODES = {"vocab", "review"}

STEP_GUIDE = """KIVA teaches each new word in four steps:
1. definition: KIVA explains the word in simple, child-friendly language.
2. story_context: KIVA reads the sentence from the book and asks the student what the word means there.
3. personal_connection: KIVA asks the student to relate the word to their own life.
4. own_sentence: KIVA asks the student to make up a new sentence using the word.

Classify each step for each word:
- "completed": KIVA did the step and the student made a relevant, correct attempt
  (for definition: KIVA gave the definition and the student stayed engaged).
- "attempted_not_completed": KIVA asked, but the student's answer was missing, off-topic or still incorrect
  after KIVA's help.
- "not_reached": KIVA never got to this step for this word."""


class AnalysisUnavailable(Exception):
    """The session lacks what analysis needs (no flow state, no transcript). Retrying won't help."""


# ---------- Session config helpers ----------


def session_dir(session_dir_id: str) -> Path:
    """Folder of a session."""
    return SESSIONS_ROOT / session_dir_id


def activity_name(config: Dict[str, Any]) -> Optional[str]:
    """Name of the activity a session config belongs to.

    The settings form doesn't send the activity name, so it is inferred from the flow config path.
    """
    flow_path = config.get("advanced_flows_config_path") or ""
    if config.get("advanced_flows") and f"{VOCAB_ACTIVITY}/" in flow_path:
        return VOCAB_ACTIVITY
    for part in Path(flow_path or config.get("activity_variables_path") or "").parts:
        if (
            part.endswith("-tutoring")
            or part.endswith("-demo")
            or part.endswith("-interaction")
        ):
            return part
    return None


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else (SERVER_DIR / candidate).resolve()


def book_info(
    activity_variables_path: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Book ID (resource file stem) and a readable title for a session's book.

    Resource files have no title field, so the audiobook metadata is used when it has the same book,
    otherwise a readable form of the file name.
    """
    if not activity_variables_path:
        return None, None
    book_id = Path(activity_variables_path).stem
    first_chapter = AUDIOBOOK_RESOURCES / book_id / "1.json"
    try:
        title = json.loads(first_chapter.read_text(encoding="utf-8")).get("title")
        if title:
            return book_id, title
    except Exception:
        pass
    return book_id, book_id.replace("_", " ").strip().title()


def grade_bands(
    activity_variables_path: Optional[str], chapter: Optional[int]
) -> Dict[str, int]:
    """Map each curated word of a chapter (lowercase) to its grade band (4, 5 or 6)."""
    if not activity_variables_path or not chapter:
        return {}
    try:
        data = json.loads(_resolve(activity_variables_path).read_text(encoding="utf-8"))
        words = data["vocab"]["chapters"][int(chapter) - 1]["vocab_words"]
    except Exception as e:
        logger.warning(
            f"Could not read grade lists for {activity_variables_path} chapter {chapter}: {e}"
        )
        return {}
    bands = {}
    for band in metrics.GRADE_BANDS:
        for entry in words.get(f"grade_{band}", []) or []:
            word = entry.get("word") if isinstance(entry, dict) else entry
            if word:
                bands.setdefault(str(word).strip().lower(), band)
    return bands


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _duration_seconds(transcript: List[Dict[str, Any]]) -> Optional[int]:
    stamps = []
    for entry in transcript:
        try:
            stamps.append(
                datetime.fromisoformat(
                    str(entry.get("timestamp")).replace("Z", "+00:00")
                )
            )
        except (TypeError, ValueError):
            continue
    if len(stamps) < 2:
        return None
    try:
        return max(0, int((max(stamps) - min(stamps)).total_seconds()))
    except TypeError:
        return None


def _user_turns(transcript: List[Dict[str, Any]]) -> List[str]:
    return [
        e.get("content") or ""
        for e in transcript
        if e.get("role") == "user" and e.get("content")
    ]


def _format_transcript(transcript: List[Dict[str, Any]]) -> str:
    speaker = {"user": "Student", "assistant": "KIVA"}
    lines = [
        f"{speaker.get(e.get('role'), e.get('role'))}: {e.get('content')}"
        for e in transcript
        if e.get("content")
    ]
    return "\n".join(lines)


def _clean_words(values: Any) -> List[str]:
    seen, words = set(), []
    for value in values or []:
        word = str(value).strip().lower()
        if word and word not in seen:
            seen.add(word)
            words.append(word)
    return words


# ---------- Step 1: flow-state ingestion (no LLM) ----------


def ingest_flow_state(session_dir_id: str) -> Optional[Dict[str, Any]]:
    """Store disposition, review result, completion and duration for a session from ``flow_state.json``.

    Args:
        session_dir_id: The session folder name.

    Returns:
        Optional[Dict[str, Any]]: The updated session record, or None if the session isn't indexed.
    """
    record = repository.get_session_record_by_dir(session_dir_id)
    if record is None:
        return None
    folder = session_dir(session_dir_id)
    config = _read_json(folder / "config.json") or {}
    snapshot = read_snapshot(folder)
    transcript = _read_json(folder / "transcript.json") or []
    if snapshot is None:
        repository.update_session_fields(
            record["id"],
            completion="ended_early",
            duration_seconds=_duration_seconds(transcript),
            analysis_status="failed",
            summary_status="failed",
            analysis_error="flow_state.json missing",
        )
        return repository.get_session_record(record["id"])

    user = snapshot.get("user", {})
    taught = _clean_words(user.get("vocab_words_taught"))
    known = [w for w in _clean_words(user.get("vocab_words_known")) if w not in taught]
    mastered = set(_clean_words(user.get("vocab_words_taught+mastered")))
    not_mastered = set(_clean_words(user.get("vocab_words_taught+not_mastered")))
    override = set(
        _clean_words(snapshot.get("vocab_override") or config.get("vocab_override"))
    )
    bands = grade_bands(config.get("activity_variables_path"), config.get("index"))

    outcomes = []
    for word in known + taught:
        is_taught = word in taught
        review = None
        if is_taught:
            review = (
                "mastered"
                if word in mastered
                else "not_mastered" if word in not_mastered else "not_reached"
            )
        outcomes.append(
            {
                "word": word,
                "grade_band": bands.get(word),
                "teacher_selected": word in override,
                "disposition": "taught" if is_taught else "known",
                "review_result": review,
                "position": len(outcomes),
            }
        )
    repository.replace_word_outcomes(record["id"], outcomes)
    repository.update_session_fields(
        record["id"],
        completion=(
            "completed"
            if snapshot.get("current_node") in COMPLETED_NODES
            else "ended_early"
        ),
        duration_seconds=_duration_seconds(transcript),
        ingested_at=repository.now_iso(),
    )
    return repository.get_session_record(record["id"])


# ---------- LLM calls ----------


def _model() -> str:
    return os.getenv("DASHBOARD_ANALYSIS_MODEL") or "gpt-4.1"


async def _structured_call(
    system: str, user: str, name: str, schema: Dict[str, Any]
) -> Dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=_model(),
        temperature=0.2,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        },
    )
    return json.loads(response.choices[0].message.content)


def _steps_schema(with_disposition: bool) -> Dict[str, Any]:
    properties = {
        "word": {"type": "string"},
        **{step: {"type": "string", "enum": STEP_VALUES} for step in metrics.STEPS},
    }
    if with_disposition:
        properties["disposition"] = {"type": "string", "enum": ["known", "taught"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["words"],
        "properties": {
            "words": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(properties),
                    "properties": properties,
                },
            }
        },
    }


async def classify_steps(
    transcript: List[Dict[str, Any]], taught_words: List[str]
) -> Dict[str, Dict[str, str]]:
    """Classify the four teaching steps for each taught word (contract § Call 1).

    Args:
        transcript: The session transcript.
        taught_words: Words the tutor taught, in order.

    Returns:
        Dict[str, Dict[str, str]]: Step results per word (lowercase).

    Raises:
        ValueError: If the model's word list doesn't match the taught words after one retry.
    """
    system = (
        "You review a recorded vocabulary tutoring session between KIVA (an AI tutor) and a child.\n\n"
        + STEP_GUIDE
        + "\n\nReturn exactly one entry per listed word, using the word exactly as listed."
    )
    user = f"Taught words, in order: {', '.join(taught_words)}\n\nTranscript:\n{_format_transcript(transcript)}"
    expected = set(taught_words)
    for _ in range(2):
        result = await _structured_call(
            system, user, "step_outcomes", _steps_schema(False)
        )
        steps = {
            e["word"].strip().lower(): {s: e[s] for s in metrics.STEPS}
            for e in result.get("words", [])
        }
        if set(steps) == expected:
            return steps
        user += (
            "\n\nYour previous answer had the wrong words. Return exactly these words: "
            + ", ".join(taught_words)
        )
    raise ValueError("Step classification returned the wrong set of words")


async def discover_words(transcript: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find words when the session ended before the tutor recorded them (left during the vocab stage).

    Returns:
        List[Dict[str, Any]]: ``{word, disposition, steps}`` in the order the words came up.
    """
    system = (
        "You review a recorded vocabulary tutoring session between KIVA (an AI tutor) and a child that ended early.\n"
        "List every vocabulary word KIVA asked the child about, in order. Use disposition 'known' if the child "
        "correctly explained the word so KIVA skipped it, otherwise 'taught'.\n\n"
        + STEP_GUIDE
        + "\nFor 'known' words, set every step to 'not_reached'."
    )
    result = await _structured_call(
        system, _format_transcript(transcript), "discovered_words", _steps_schema(True)
    )
    words, seen = [], set()
    for entry in result.get("words", []):
        word = entry["word"].strip().lower()
        if word and word not in seen:
            seen.add(word)
            words.append(
                {
                    "word": word,
                    "disposition": entry["disposition"],
                    "steps": {s: entry[s] for s in metrics.STEPS},
                }
            )
    return words


SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "text",
        "engagement",
        "words_went_well",
        "words_hard",
        "notable_moments",
        "suggestions",
    ],
    "properties": {
        "text": {"type": "string"},
        "engagement": {"type": "string", "enum": ["high", "mixed", "low"]},
        "words_went_well": {"type": "array", "items": {"type": "string"}},
        "words_hard": {"type": "array", "items": {"type": "string"}},
        "notable_moments": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
    },
}


def _outcome_lines(outcomes: List[Dict[str, Any]]) -> str:
    lines = []
    for o in outcomes:
        if o["disposition"] == "known":
            lines.append(f"- {o['word']}: already knew it (skipped)")
        else:
            steps = ", ".join(
                f"{s}={(o.get('steps') or {}).get(s)}" for s in metrics.STEPS
            )
            lines.append(
                f"- {o['word']}: taught; {steps}; review={o.get('review_result')}"
            )
    return "\n".join(lines) or "- (no words)"


def _no_words_summary(completion: Optional[str]) -> Dict[str, Any]:
    text = (
        "This session ended before any vocabulary words came up."
        if completion == "ended_early"
        else "No vocabulary words were covered in this session."
    )
    return {
        "text": text,
        "engagement": "mixed",
        "words_went_well": [],
        "words_hard": [],
        "notable_moments": [],
        "suggestions": ["Encourage the student to complete a full session next time."],
    }


async def summarize_session(
    transcript: List[Dict[str, Any]],
    outcomes: List[Dict[str, Any]],
    completion: Optional[str],
    duration: Optional[int],
) -> Optional[Dict[str, Any]]:
    """Write the session summary and check it (contract § Call 2).

    Returns:
        Optional[Dict[str, Any]]: The validated summary, or None if it still failed validation after one retry.
    """
    if not outcomes:
        return _no_words_summary(completion)
    system = (
        "You write short notes for a classroom teacher about one vocabulary tutoring session between KIVA "
        "(an AI tutor) and their student.\n"
        "- At most 120 words in `text`, plain classroom language, no technical terms.\n"
        "- Cover engagement, which words went well and which were hard, one notable moment, and 1–2 suggestions.\n"
        "- NEVER quote the student. Never include personal details the student shared; describe them generally "
        "(for example 'connected the word to a family trip').\n"
        "- `words_went_well` and `words_hard` may only contain taught words, and must agree with the outcomes.\n"
        "- At most 2 notable_moments and 1–2 suggestions."
    )
    minutes = f"{round(duration / 60)} minutes" if duration else "unknown length"
    user = (
        f"Session: {completion or 'unknown'} ({minutes}).\nRecorded word outcomes:\n{_outcome_lines(outcomes)}\n\n"
        f"Transcript:\n{_format_transcript(transcript)}"
    )
    user_turns = _user_turns(transcript)
    for _ in range(2):
        summary = await _structured_call(
            system, user, "session_summary", SUMMARY_SCHEMA
        )
        summary["notable_moments"] = summary.get("notable_moments", [])[:2]
        summary["suggestions"] = summary.get("suggestions", [])[:2]
        problems = (
            validators.check_length(summary["text"])
            + validators.check_word_consistency(summary, outcomes)
            + validators.check_no_quotes(
                [summary["text"], *summary["notable_moments"], *summary["suggestions"]],
                user_turns,
            )
        )
        if not problems:
            return summary
        logger.info(f"Session summary failed checks, regenerating: {problems}")
        user += (
            "\n\nYour previous summary had these problems; fix all of them:\n- "
            + "\n- ".join(problems)
        )
    return None


# ---------- Student progress summary ----------


def student_aggregates(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate figures for the student summary prompt. Contains no transcript content."""
    with_words = [s for s in sessions if s.get("ingested")]
    taught = [o for s in with_words for o in s["words"] if o["disposition"] == "taught"]
    step_misses = {}
    for step in metrics.STEPS:
        judged = [o for o in taught if (o.get("steps") or {}).get(step)]
        misses = sum(1 for o in judged if o["steps"][step] == "attempted_not_completed")
        step_misses[step] = (
            f"{misses} of {len(judged)}" if judged else "not analyzed yet"
        )
    recent = sorted(with_words, key=lambda s: s["started_at"])[-5:]
    mastery = []
    for s in recent:
        words = [o for o in s["words"] if o["disposition"] == "taught"]
        mastered = sum(1 for o in words if o.get("review_result") == "mastered")
        mastery.append(f"{mastered}/{len(words)}" if words else "no new words")
    return {
        "sessions": len(with_words),
        "counts": metrics.cumulative_counts(with_words),
        "steps_tried_not_completed": step_misses,
        "mastered_per_recent_session": mastery,
        "reading_level_trend": [
            t["level"] for t in metrics.reading_level_trend(with_words)
        ],
        "still_learning_words": [
            w["word"]
            for w in metrics.word_statuses(with_words)
            if w["status"] == "still_learning"
        ],
    }


STUDENT_SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["text", "strengths", "difficulties", "suggested_focus"],
    "properties": {
        "text": {"type": "string"},
        "strengths": {"type": "string"},
        "difficulties": {"type": "string"},
        "suggested_focus": {"type": "string"},
    },
}


async def generate_student_summary(student_id: str) -> None:
    """Refresh a student's progress summary from aggregated outcomes only (never the transcript)."""
    sessions = repository.get_student_sessions(student_id)
    aggregates = student_aggregates(sessions)
    if aggregates["sessions"] == 0:
        return
    system = (
        "You write a 2–4 sentence progress note for a classroom teacher about one student's vocabulary practice "
        "with KIVA, an AI tutor. Use plain classroom language. Cover strengths, recurring difficulties and one "
        "suggested focus. Base it only on the figures given. Steps: definition (heard a simple definition), "
        "story_context (explained the word in the story), personal_connection (related it to their life), "
        "own_sentence (used it in their own sentence)."
    )
    try:
        summary = await _structured_call(
            system,
            json.dumps(aggregates, indent=2),
            "student_summary",
            STUDENT_SUMMARY_SCHEMA,
        )
        repository.save_student_summary(student_id, summary, aggregates["sessions"])
    except Exception as e:
        logger.error(f"Student summary failed for {student_id}: {e}")
        repository.save_student_summary(student_id, None, aggregates["sessions"])


# ---------- Orchestration ----------


async def _analyze_steps(
    record: Dict[str, Any], transcript: List[Dict[str, Any]], snapshot: Dict[str, Any]
) -> None:
    outcomes = repository.get_word_outcomes(record["id"])
    taught = [o["word"] for o in outcomes if o["disposition"] == "taught"]
    if taught:
        steps = await classify_steps(transcript, taught)
        for o in outcomes:
            if o["disposition"] == "taught":
                o["steps"] = steps[o["word"]]
        repository.replace_word_outcomes(record["id"], outcomes)
    elif not outcomes and snapshot.get("current_node") in WORD_NODES:
        config = _read_json(session_dir(record["session_dir_id"]) / "config.json") or {}
        bands = grade_bands(config.get("activity_variables_path"), config.get("index"))
        override = set(_clean_words(snapshot.get("vocab_override")))
        found = await discover_words(transcript)
        repository.replace_word_outcomes(
            record["id"],
            [
                {
                    "word": w["word"],
                    "grade_band": bands.get(w["word"]),
                    "teacher_selected": w["word"] in override,
                    "disposition": w["disposition"],
                    "review_result": (
                        "not_reached" if w["disposition"] == "taught" else None
                    ),
                    "steps": w["steps"] if w["disposition"] == "taught" else None,
                    "position": i,
                }
                for i, w in enumerate(found)
            ],
        )


async def _summarize(record: Dict[str, Any], transcript: List[Dict[str, Any]]) -> None:
    repository.update_session_fields(record["id"], summary_status="running")
    try:
        outcomes = repository.get_word_outcomes(record["id"])
        summary = await summarize_session(
            transcript,
            outcomes,
            record.get("completion"),
            record.get("duration_seconds"),
        )
    except Exception as e:
        logger.error(f"Session summary failed for {record['id']}: {e}")
        summary = None
    if summary is None:
        repository.update_session_fields(record["id"], summary_status="failed")
        return
    repository.update_session_fields(
        record["id"],
        summary_status="ready",
        summary_text=summary["text"],
        summary_json=json.dumps(summary),
    )


def _write_report(record_id: str) -> None:
    record = repository.get_session_record(record_id)
    report = {
        "session_record_id": record_id,
        "completion": record["completion"],
        "duration_seconds": record["duration_seconds"],
        "analysis_status": record["analysis_status"],
        "words": repository.get_word_outcomes(record_id),
        "summary": (
            json.loads(record["summary_json"]) if record.get("summary_json") else None
        ),
        "generated_at": repository.now_iso(),
    }
    try:
        _write_json_atomic(session_dir(record["session_dir_id"]) / REPORT_FILE, report)
    except Exception as e:
        logger.error(f"Could not write {REPORT_FILE} for {record_id}: {e}")


async def run_post_session(session_dir_id: str) -> None:
    """Analyze a finished session end to end. Safe to call more than once; never raises.

    Args:
        session_dir_id: The session folder name.
    """
    try:
        record = repository.get_session_record_by_dir(session_dir_id)
        if record is None or record["analysis_status"] == "not_applicable":
            return
        if record.get("ingested_at") is None and record["analysis_status"] != "failed":
            record = ingest_flow_state(session_dir_id)
        if record["analysis_status"] == "ready":
            if record["summary_status"] in ("pending", "running"):
                transcript = (
                    _read_json(session_dir(session_dir_id) / "transcript.json") or []
                )
                await _summarize(record, transcript)
                _write_report(record["id"])
            return
        if not repository.claim_for_analysis(record["id"]):
            return
        folder = session_dir(session_dir_id)
        try:
            snapshot = read_snapshot(folder)
            transcript = _read_json(folder / "transcript.json") or []
            if snapshot is None or not _user_turns(transcript):
                raise AnalysisUnavailable("flow state or transcript missing")
            await _analyze_steps(record, transcript, snapshot)
            repository.update_session_fields(
                record["id"],
                analysis_status="ready",
                analysis_error=None,
                analyzed_at=repository.now_iso(),
            )
        except AnalysisUnavailable as e:
            repository.update_session_fields(
                record["id"],
                analysis_status="failed",
                summary_status="failed",
                analysis_error=str(e),
            )
            return
        except Exception as e:
            attempts = record["analysis_attempts"] + 1
            logger.error(
                f"Analysis attempt {attempts} failed for {session_dir_id}: {e}"
            )
            retry = attempts < MAX_ATTEMPTS
            repository.update_session_fields(
                record["id"],
                analysis_status="pending" if retry else "failed",
                summary_status="pending" if retry else "failed",
                analysis_attempts=attempts,
                analysis_error=str(e)[:500],
            )
            if retry:
                await run_post_session(session_dir_id)
            else:
                await generate_student_summary(record["student_id"])
            return
        record = repository.get_session_record(record["id"])
        await _summarize(record, transcript)
        _write_report(record["id"])
        await generate_student_summary(record["student_id"])
    except Exception as e:
        logger.error(f"Post-session analysis crashed for {session_dir_id}: {e}")


def schedule_post_session(session_dir_id: str) -> None:
    """Start ``run_post_session`` in the background on the running event loop."""
    asyncio.create_task(run_post_session(session_dir_id))


def requeue_pending() -> int:
    """Restart analysis for sessions left unfinished (for example by a server restart).

    Returns:
        int: Number of sessions scheduled.
    """
    count = 0
    for record in repository.records_awaiting_analysis():
        if record["analysis_status"] == "running":
            repository.update_session_fields(record["id"], analysis_status="pending")
        if record["summary_status"] == "running":
            repository.update_session_fields(record["id"], summary_status="pending")
        if (session_dir(record["session_dir_id"]) / "flow_state.json").exists():
            schedule_post_session(record["session_dir_id"])
            count += 1
    return count


def reset_for_retry(record: Dict[str, Any]) -> None:
    """Set failed parts of a session back to pending so ``run_post_session`` redoes them."""
    fields: Dict[str, Any] = {"analysis_attempts": 0}
    if record["analysis_status"] == "failed":
        fields.update(
            analysis_status="pending", summary_status="pending", analysis_error=None
        )
    elif record["summary_status"] == "failed":
        fields["summary_status"] = "pending"
    repository.update_session_fields(record["id"], **fields)

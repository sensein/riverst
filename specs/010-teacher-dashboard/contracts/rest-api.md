# Contract: Teacher Dashboard REST API

All teacher endpoints:
- live under `/api/teacher`
- require `Authorization: Bearer <jwt>`, where the JWT has `"teacher"` in `roles` (`require_teacher`)
- are scoped to the caller's class

**Error responses**:
- Resources outside the caller's class return `404`, never `403`, so their existence isn't revealed.
- Error bodies are `{ "detail": "<plain message>" }`. They never include stack traces or internal IDs (Constitution III).

**Never returned by any teacher endpoint**: `session_dir_id`, `user_key`, transcripts, the student's raw responses, audio paths, `analysis_error`.

## Auth changes (existing endpoints)

| Endpoint | Change |
|---|---|
| `POST /api/auth/google` | Also accepts emails in `teacher_emails`. The JWT gains `roles: ["researcher"? , "teacher"?]`. |
| `POST /api/auth/bypass` | The bypass token gets `roles: ["researcher", "teacher"]`, for local development. |
| `GET /api/auth/me` | Response adds `roles: string[]`. |
| `GET /api/sessions`, `GET /api/session/{id}` | Now require the `researcher` role (`403` for teacher-only accounts). |
| `POST /api/session` | Accepts an optional `student_code`. See below. |

### `POST /api/session` with `student_code`

Request body: the existing settings, plus `"student_code": "K7MPQ4"`. The code is case-insensitive and whitespace is stripped.

| Case | Result |
|---|---|
| Valid code, active student | `user_id` is replaced by the student's `user_key`. `student_id` is written to `config.json`. A `session_record` is created (`analysis_status = pending` for vocabulary activities, otherwise `not_applicable`). The response is unchanged. |
| Unknown, regenerated or archived-student code | `422 {"detail": "We didn't recognize that student code. Check with your teacher."}` and no session is created. |
| No `student_code` | Behaves exactly as today. Not indexed. |

`GET /api/student-code/{code}` (authenticated, any role) returns `{ "display_name": "Maya" }` or `404`. The settings form uses it to confirm "Hi, Maya!" before starting.

## Class & students

### `GET /api/teacher/class`

Query parameters:
- `status=active|archived` (default `active`)
- `sort=name|last_session|words_mastered` (default `name`)
- `order=asc|desc`

```json
{
  "class": { "id": "c_x", "name": "My class" },
  "students": [
    {
      "id": "s_abc",
      "display_name": "Maya",
      "code": "K7MPQ4",
      "status": "on_track | needs_attention | inactive | no_sessions",
      "last_session_at": "2026-10-07T14:02:00Z | null",
      "sessions_completed": 6,
      "words_mastered": 14,
      "reading_level": { "value": 5, "source": "estimate | teacher", "label": "Grade 5 words" }
    }
  ]
}
```

Status filtering is done on the client (FR-011), because the whole class is returned.

### `POST /api/teacher/students`

Body: `{ "display_name": "Maya" }`. Returns `201` with the student, including `code` and `link` (`/kiva?code=K7MPQ4`).

### `PATCH /api/teacher/students/{id}`

Body (all optional): `{ "display_name", "status": "active|archived", "reading_level_override": 3..8 | null }`. Returns the updated student.

### `POST /api/teacher/students/{id}/code`

Regenerates the code. Returns `{ "code", "link" }`. The old code is invalid immediately.

## Student detail

### `GET /api/teacher/students/{id}`

```json
{
  "student": { "id", "display_name", "code", "status", "reading_level": {...}, "reading_level_estimate": {...} },
  "counts": { "already_knew": 5, "taught": 18, "mastered": 14, "still_learning": 4 },
  "reading_level_trend": [ { "session_id": "r_1", "date": "...", "level": 4 } ],
  "summary": { "status": "ready | failed | none", "text": "...", "generated_at": "..." },
  "words": [
    { "word": "reluctant", "status": "mastered | still_learning | already_knew",
      "grade_band": 5, "last_seen_session_id": "r_9", "last_seen_at": "...",
      "history": [ { "session_id": "r_3", "result": "not_mastered" }, { "session_id": "r_9", "result": "mastered" } ] }
  ],
  "sessions": [
    { "id": "r_9", "started_at": "...", "book_title": "...", "chapter": 3, "completion": "completed | ended_early | null",
      "detail": "ready | pending | unavailable", "words_taught": 3, "words_mastered": 2 }
  ]
}
```

## Session detail

### `GET /api/teacher/sessions/{id}`

```json
{
  "session": { "id", "student_id", "student_name", "started_at", "duration_seconds", "activity_label",
               "book_title", "chapter", "completion", "teacher_selected_words": true },
  "detail": "ready | pending | unavailable | not_applicable",
  "already_knew": [ { "word": "brave", "grade_band": 4 } ],
  "taught": [
    { "word": "reluctant", "grade_band": 5, "teacher_selected": false,
      "steps": { "definition": "completed", "story_context": "completed",
                 "personal_connection": "attempted_not_completed", "own_sentence": "not_reached" },
      "review": "mastered | not_mastered | not_reached" }
  ],
  "summary": { "status": "ready | pending | failed",
               "text": "...", "words_went_well": [], "words_hard": [], "suggestions": [] }
}
```

### `POST /api/teacher/sessions/{id}/retry`

Sets `failed` analysis and/or summary back to `pending` and starts the analysis again. Returns `202`. Returns `409` if the analysis is already running.

## Class insights (P3)

### `GET /api/teacher/insights/words`

Query parameter: `sort=mastery_rate|taught|word` (default `mastery_rate` ascending).

```json
{ "words": [ { "word": "reluctant", "grade_band": 5, "already_knew": 2, "taught": 7, "mastered": 3,
               "still_learning": 4, "mastery_rate": 0.43, "hardest_step": "own_sentence",
               "still_learning_students": [ { "id": "s_abc", "display_name": "Maya" } ] } ] }
```

## Notes (P3)

| Method & path | Body / result |
|---|---|
| `GET /api/teacher/notes?target_type=student\|session&target_id=` | `{ "notes": [ { "id", "body", "created_at", "updated_at" } ] }` |
| `POST /api/teacher/notes` | `{ target_type, target_id, body }` → `201` note |
| `PATCH /api/teacher/notes/{id}` | `{ body }` → note |
| `DELETE /api/teacher/notes/{id}` | `204`. Only the teacher's own notes can be deleted. |

## Report (P3)

`GET /api/teacher/students/{id}/report` returns the student-detail payload plus `notes` (student-level) and the `generated_at` time. The client renders it as a print-styled page.

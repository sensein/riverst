# Data Model: Teacher Monitoring Dashboard

**Feature**: 010-teacher-dashboard | **Date**: 2026-10-08

**Store**: SQLite at `src/server/data/dashboard.db` (see research R2). The schema is created on startup and versioned through a `schema_version` table.

**Conventions**:
- Timestamps are ISO-8601 UTC text.
- Enums are stored as `TEXT` with a `CHECK` constraint.
- IDs are random URL-safe strings: `secrets.token_urlsafe(9)`, or 16 hex characters for `student.user_key`.

## Entities

### teacher
| Field | Type | Rules |
|---|---|---|
| email | TEXT PK | Taken from the JWT `sub`. A row is created on the teacher's first dashboard visit. |
| display_name | TEXT | Taken from the JWT `name`. |
| created_at | TEXT | |

### class
v1 has one class per teacher, created automatically with the teacher row.

| Field | Type | Rules |
|---|---|---|
| id | TEXT PK | |
| teacher_email | TEXT FK → teacher | UNIQUE (one class per teacher in v1) |
| name | TEXT | Default "My class" |

### student
| Field | Type | Rules |
|---|---|---|
| id | TEXT PK | Opaque. This is what the dashboard API uses. |
| class_id | TEXT FK → class | |
| display_name | TEXT | 1–40 characters, trimmed. A first name or nickname. No other personal information is stored. |
| code | TEXT UNIQUE | 6 characters from `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, unique across all students. |
| user_key | TEXT UNIQUE | `stu_<16 hex>`. Becomes the session `user_id` (R3). Never changes. |
| status | TEXT | `active` \| `archived` |
| reading_level_override | INTEGER NULL | 3–8 (grade). NULL means use the automatic estimate. |
| override_set_at | TEXT NULL | |
| created_at, updated_at | TEXT | |

**State transitions**:
- `active ⇄ archived` (archive / restore).
- "Unlink" means archive. Data is never deleted (spec edge case).
- Regenerating a code replaces `code`. The old value stops resolving immediately.

### session_record
One row per student-attributed session. Sessions without a student code are never indexed.

| Field | Type | Rules |
|---|---|---|
| id | TEXT PK | Opaque record ID exposed to teachers. Never the session folder name. |
| session_dir_id | TEXT UNIQUE | Internal `session_id` (folder). Never returned by teacher endpoints. |
| student_id | TEXT FK → student | |
| started_at | TEXT | From the session ID timestamp. |
| duration_seconds | INTEGER NULL | First to last transcript timestamp. |
| activity | TEXT | `vocab-tutoring` in v1 |
| book_id | TEXT | Resource file stem |
| book_title | TEXT | |
| chapter | INTEGER | The 1-based `index` |
| completion | TEXT NULL | `completed` \| `ended_early` (R7). NULL until the session ends. |
| vocab_override_used | INTEGER | 0 or 1 |
| analysis_status | TEXT | `pending` \| `running` \| `ready` \| `failed` \| `not_applicable` |
| analysis_attempts | INTEGER | Starts at 0 |
| analysis_error | TEXT NULL | Internal only. Never shown to teachers. |
| summary_status | TEXT | `pending` \| `running` \| `ready` \| `failed` |
| summary_text | TEXT NULL | About 120 words or fewer |
| summary_json | TEXT NULL | `{engagement, words_went_well[], words_hard[], notable_moments[], suggestions[]}` |
| ingested_at | TEXT NULL | Set when the flow-state outcomes are stored (enough for counts and reading level). |
| analyzed_at | TEXT NULL | |

**State transitions** (`analysis_status`):

```text
(session created with code) → pending
pending → running        analysis task starts (on disconnect, or re-queued at startup)
running → ready          outcomes stored
running → pending        first failure: automatic retry, attempts += 1
running → failed         attempts reach 2
failed  → pending        teacher presses Retry
(non-vocabulary activity) → not_applicable
```

`summary_status` follows the same pattern but is independent. Outcomes can be `ready` while the summary is `failed` (FR-020).

Index: `(student_id, started_at DESC)`.

### word_outcome
| Field | Type | Rules |
|---|---|---|
| session_record_id | TEXT FK → session_record | Composite PK with `word` |
| word | TEXT | Lowercased |
| grade_band | INTEGER NULL | 4, 5 or 6. NULL if the word isn't in the book's grade lists (for example, override words). |
| teacher_selected | INTEGER | 1 if the word came from `vocab_override` |
| disposition | TEXT | `known` \| `taught` (from the flow state) |
| step_definition | TEXT NULL | `completed` \| `attempted_not_completed` \| `not_reached`. NULL when disposition is `known`. |
| step_story_context | TEXT NULL | same |
| step_personal_connection | TEXT NULL | same |
| step_own_sentence | TEXT NULL | same |
| review_result | TEXT NULL | `mastered` \| `not_mastered` \| `not_reached`. NULL when disposition is `known`. |
| position | INTEGER | Order the word came up in the session |

**Validation**:
- `disposition = known` ⇒ all step fields and `review_result` are NULL.
- `disposition = taught` ⇒ all four steps are non-NULL once `analysis_status = ready`. While the analysis is pending, the rows are inserted from the flow state alone, with the steps NULL.
- `review_result` comes from the flow state:
  - in `taught+mastered` → `mastered`
  - in `taught+not_mastered` → `not_mastered`
  - in neither → `not_reached`

Index: `(word)`, used for class word insights.

### student_summary
| Field | Type | Rules |
|---|---|---|
| student_id | TEXT PK FK → student | |
| text | TEXT | 2–4 sentences, generated from aggregates only (R6) |
| strengths, difficulties, suggested_focus | TEXT | Structured parts |
| based_on_sessions | INTEGER | Number of `ready` sessions used |
| generated_at | TEXT | |
| status | TEXT | `ready` \| `failed` |

### teacher_note
| Field | Type | Rules |
|---|---|---|
| id | TEXT PK | |
| teacher_email | TEXT FK → teacher | Only the author can see or edit it. |
| target_type | TEXT | `student` \| `session` |
| target_id | TEXT | `student.id` or `session_record.id`. Must belong to the teacher's class. |
| body | TEXT | 1–2,000 characters |
| created_at, updated_at | TEXT | |

## Derived (not stored)

These are computed per request in `dashboard/metrics.py`:

- **Student word status**: for each word, the latest record by `started_at`.
  - `known` → "Already knew it"
  - `mastered` → "Mastered"
  - otherwise → "Still learning"
  - The history is the list of `(session, result)`.
- **Cumulative counts**: distinct words in each latest status, plus the total number of words taught.
- **Reading level estimate and trend**: the R7 rule, evaluated after each `ready` session, giving the series for the sparkline.
- **Status**: `on_track` \| `needs_attention` \| `inactive` (R7).
- **Class word insights**: for each word across the class's active students: known, taught, mastered and still-learning counts; mastery rate; and the step most often `attempted_not_completed`.

## Session-folder files (written by the bot; researcher-facing)

| File | Written when | Contents |
|---|---|---|
| `flow_state.json` | On every `general_handler` call and on disconnect. Atomic: tmp file + `os.replace`. | `{current_node, user: {vocab_words_known, vocab_words_taught, ...}, vocab_override, updated_at}` |
| `learning_report.json` | When analysis finishes | The same outcomes and summary as stored in SQLite |
| `config.json` (existing) | At session creation | Gains `student_id`. `user_id` becomes the student's `user_key`. |

## Relationships

```text
teacher 1─1 class 1─* student 1─* session_record 1─* word_outcome
student 1─0..1 student_summary
teacher 1─* teacher_note *─1 (student | session_record)
```

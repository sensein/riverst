---

description: "Task list for the Teacher Monitoring Dashboard"
---

# Tasks: Teacher Monitoring Dashboard

**Input**: Design documents from `specs/010-teacher-dashboard/`
**Prerequisites**:
- [plan.md](./plan.md)
- [spec.md](./spec.md)
- [research.md](./research.md)
- [data-model.md](./data-model.md)
- [contracts/rest-api.md](./contracts/rest-api.md)
- [contracts/session-analysis.md](./contracts/session-analysis.md)
- [quickstart.md](./quickstart.md)

**Tests**:
- The plan asks for `unittest` coverage of pure server logic only: metrics, validators, codes and roles. Those test tasks are included, written to match the existing `src/server/tests/test_device_utils.py` style, and run with `cd src/server && python -m unittest discover -s tests`.
- Everything else is checked manually per `quickstart.md` (Constitution II). Each story phase ends with a manual verification task.

**Organization**: One phase per user story. Both US1 and US2 are P1. US2 (linking) is built first because the class overview needs students to exist.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: The user story the task belongs to (US1–US7)

## Path Conventions

The existing monorepo layout, per plan.md:
- **Server**: `src/server/` (new package `src/server/dashboard/`)
- **Client**: `src/client/react/src/` (new `pages/teacher/` and `components/teacher/`)

## Conventions for every task

- **Python**: Black and Flake8 at 120 characters. Google-style docstrings on public functions. No TODOs.
- **TypeScript**: ESLint and Prettier. JSDoc on exported non-obvious functions. antd primitives only.
- **Teacher endpoints** (contracts/rest-api.md):
  - Never return `session_dir_id`, `user_key`, transcripts, the student's raw responses, audio paths or `analysis_error`.
  - Return `404` for resources outside the caller's class.
  - Error bodies are `{"detail": "<plain message>"}`.
- **Teacher-facing text** comes from `components/teacher/labels.ts`.

---

## Phase 1: Setup

**Purpose**: Dependencies, the storage location and package scaffolding.

- [X] T001 [P] Add `data/` under the "Audio and session data" section of `src/server/.gitignore`.
- [X] T002 [P] Add a volume `./src/server/data:/app/data` to the `server` service in `docker-compose.yaml`, and the same line to the server service in `docker-compose.gpu.yaml` if it defines its own volumes.
- [X] T003 [P] Declare `openai` explicitly in `src/server/requirements.txt`, pinned to the version pipecat-ai 0.0.89 installs. Find it with `pip show openai` in the server environment.
- [X] T004 [P] Add `DASHBOARD_DB_PATH` (default `data/dashboard.db`, relative to `src/server`) and `DASHBOARD_ANALYSIS_MODEL=gpt-4.1` with explanatory comments to `src/server/env.example`.
- [X] T005 Create the package `src/server/dashboard/` with an `__init__.py` whose module docstring states its purpose ("teacher dashboard: storage, metrics, post-session analysis, API").

**Checkpoint**: `docker compose up --build` still starts. `src/server/data/` exists on the host.

---

## Phase 2: Foundational (blocks all user stories)

**Purpose**: The SQLite store, roles, flow-state snapshots and session indexing. No teacher UI yet.

### Storage

- [X] T006 Implement `src/server/dashboard/db.py`:
  - `get_db_path()` reads `DASHBOARD_DB_PATH` and creates the parent directory.
  - `connect()` returns `sqlite3.Connection` with `row_factory=sqlite3.Row`, `PRAGMA foreign_keys=ON` and `journal_mode=WAL`.
  - `transaction()` is a context manager.
  - `init_schema()` creates the tables `schema_version`, `teacher`, `class`, `student`, `session_record`, `word_outcome`, `student_summary` and `teacher_note`, with the columns, `CHECK` enums, `UNIQUE` constraints and indexes `(student_id, started_at DESC)` and `word_outcome(word)` exactly as in `specs/010-teacher-dashboard/data-model.md`. It is idempotent and records schema version 1.
- [X] T007 [P] Implement `src/server/dashboard/codes.py`:
  - `ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"`.
  - `generate_code()` returns 6 characters from `secrets.choice`.
  - `normalize_code(raw)` uppercases and strips whitespace; it returns None if the result isn't 6 characters from the alphabet.
  - `generate_user_key()` returns `"stu_" + secrets.token_hex(8)`.
  - `new_id(prefix)` returns `f"{prefix}_{secrets.token_urlsafe(9)}"`.
- [X] T008 [P] Write `src/server/tests/test_dashboard_codes.py` (`unittest`):
  - code length and alphabet;
  - `normalize_code` handles lowercase, spaces and invalid characters;
  - `user_key` format and uniqueness across 1,000 calls.

### Repository (shared queries)

- [X] T009 Implement in `src/server/dashboard/repository.py`, using `db.transaction()`:
  - **Teachers**: `ensure_teacher(email, name)` creates the teacher plus a default "My class" class if missing, and returns the class ID.
  - **Students**:
    - `create_student(class_id, display_name)` trims and validates 1–40 characters, generates a unique code (retrying on a `UNIQUE` collision) and a `user_key`.
    - `get_student_by_code(code)` returns active students only.
    - `get_student(class_id, student_id)` returns None when the student isn't in the class.
    - `update_student(...)`.
    - `regenerate_code(...)`.
  - **Session records**:
    - `create_session_record(session_dir_id, student_id, started_at, activity, book_id, book_title, chapter, vocab_override_used, analysis_status)`.
    - `get_session_record_by_dir(session_dir_id)`.
    - `set_analysis_status(record_id, status, error=None)`.
    - `replace_word_outcomes(record_id, outcomes)`.
    - `update_session_fields(record_id, **fields)`.

### Roles

- [X] T010 Update `src/server/authorization/auth.py`:
  - Load the optional `teacher_emails` list from `authorized_users.json`, keeping the auto-created default file working.
  - Add `get_roles(email) -> list[str]`: `researcher` if the email is in `authorized_emails`, `teacher` if it is in `teacher_emails`.
  - An email counts as authorized if it is in either list.
  - Add a `roles` claim to the token-creation function.
  - Add the FastAPI dependencies `require_teacher` and `require_researcher`. Each wraps `get_current_user` and raises `403 {"detail": "This page isn't available for your account."}` when the role is missing.
  - A bypass token (`bypass: True`) has both roles.
- [X] T011 [P] Write `src/server/tests/test_dashboard_roles.py` (`unittest`): `get_roles` for researcher-only, teacher-only, both, and neither. Use a temporary allowlist file by patching the allowlist path.
- [X] T012 Update the auth routes in `src/server/main.py`:
  - `/api/auth/google`: the authorization check uses the auth.py helper (either list) and the issued JWT includes `roles`.
  - `/api/auth/bypass`: the JWT includes both roles.
  - `/api/auth/me`: the response includes `roles`.
- [X] T013 Switch `GET /api/sessions` (main.py ~:697) and `GET /api/session/{id}` (main.py ~:942) in `src/server/main.py` from `get_current_user` to `require_researcher`.
- [X] T014 [P] Add `roles: string[]` to the user type in `src/client/react/src/contexts/AuthContext.tsx`, populated from `/api/auth/me` and the login response. Export the helper `hasRole(user, role)`.
- [X] T015 [P] Create `src/client/react/src/components/TeacherRoute.tsx`, modelled on `components/ProtectedRoute.tsx`:
  - While loading, show the same loader.
  - When unauthenticated, redirect to `/login` with `state.from`.
  - When authenticated without the `teacher` role, show an antd `Result status="403"` with the title "This page is for teachers" and a "Go home" button.
- [X] T016 In `src/client/react/src/components/homepage/UserProfileDropdown.tsx`, skip the `/api/sessions` fetch (~:24) and hide the `/sessions` link (~:70) for users without the `researcher` role, so teacher-only accounts don't trigger a 403. Add a "Teacher dashboard" link (to `/teacher`) for users with the `teacher` role.

### Student code on session creation

- [X] T017 Update `POST /api/session` in `src/server/main.py`:
  - If the body has `student_code`, run `normalize_code` and `get_student_by_code`. If either fails, return `422 {"detail": "We didn't recognize that student code. Check with your teacher."}` before creating any folder.
  - On success, replace `body["user_id"]` with the student's `user_key`, set `body["student_id"]`, and remove `student_code` before writing `config.json`.
  - After the folder is created, call `create_session_record`:
    - `started_at` from the session ID timestamp;
    - `activity` from the body's activity name;
    - `book_id` = the stem of `activity_variables_path`;
    - `book_title`: resource files have no title field, so use the matching title from the `/api/audiobooks` metadata (main.py ~:849) when the book is found there, otherwise a readable form of the file stem (underscores to spaces, title case);
    - `chapter` = `index`;
    - `vocab_override_used` = whether `vocab_override` is non-empty;
    - `analysis_status = "pending"` if the activity is `vocab-tutoring`, otherwise `"not_applicable"`. ESL and ISL are out of scope for v1, because they run without a flow.
  - With no `student_code`, the behavior is unchanged.
- [X] T018 Add `GET /api/student-code/{code}` (requires `get_current_user`) to `src/server/main.py`. It returns `{"display_name"}` for an active student, or `404 {"detail": "We didn't recognize that student code."}`.
- [X] T019 Call `dashboard.db.init_schema()` at startup in `src/server/main.py`, as an `@app.on_event("startup")` handler or by attaching the existing unused `lifespan` at main.py ~:984 to the app and calling it there. Keep the existing peer-connection cleanup.

### Flow-state snapshots and ingestion

- [X] T020 [P] Implement `src/server/dashboard/flow_snapshot.py`:
  - `write_snapshot(session_dir: Path, flow_manager)` writes `flow_state.json` with `{current_node, user: <flow_manager.state["user"] filtered to the vocab_* keys and index>, vocab_override, updated_at}`.
  - The write is atomic: write `flow_state.json.tmp`, then `os.replace`.
  - Exceptions are logged with loguru and never raised (the conversation must not break).
- [X] T021 Call `flow_snapshot.write_snapshot(...)` at the end of `general_handler` in `src/server/bot/flows/handlers.py` (~:284), after the user fields are updated. Get the session folder from what the handler already has access to, or pass it via `flow_manager.state` at flow creation in `src/server/bot/flows/flow_factory.py` (for example `state["session_dir"]`).
- [X] T022 Implement `ingest_flow_state(session_dir_id)` in `src/server/dashboard/analysis.py`:
  - Read `flow_state.json`.
  - Build word rows:
    - `vocab_words_known` → `disposition=known`;
    - `vocab_words_taught` → `disposition=taught` with steps NULL;
    - `review_result` from `taught+mastered` / `taught+not_mastered`, otherwise `not_reached`;
    - `position` = the order seen;
    - `teacher_selected` = the word is in `vocab_override`;
    - `grade_band` from the book resource file's chapter `vocab.grade_4/5/6` lists (lowercase match, otherwise NULL).
  - Set `completion` (`completed` if `current_node` is in `{"closing", "end"}`, otherwise `ended_early`) and `duration_seconds` (first to last `transcript.json` timestamp).
  - Persist with `replace_word_outcomes` and `update_session_fields`.
  - If `flow_state.json` is missing, set `analysis_status=failed`.
- [X] T023 Update `on_client_disconnected` in `src/server/bot/core/event_manager.py` (~:97–131):
  - Before teardown, call `write_snapshot` one last time.
  - Then, if `get_session_record_by_dir(session_id)` exists, call `ingest_flow_state` and schedule `asyncio.create_task(analysis.run_post_session(session_id))`.
  - `run_post_session` is a no-op stub until Phase 6.
  - All of it is wrapped so that failures are logged and never block teardown.

### Metrics (pure)

- [X] T024 [P] Implement `src/server/dashboard/metrics.py` as pure functions over plain dicts/rows (no database access):
  - `word_statuses(outcomes_by_session)` returns the latest status per word and its history;
  - `cumulative_counts(...)`;
  - `reading_level_estimate(last_sessions)`, using the R7 rule: last 5 sessions with ingested word outcomes (flow state is enough; AI analysis not required), ratio ≥ ⅔ and ≥ 2 words per band, highest band wins, `"below_4"` if no band qualifies, `None` with fewer than 2 sessions;
  - `reading_level_trend(sessions)`;
  - `display_reading_level(estimate, override)` returns `{value, source, label}`;
  - `student_status(sessions, now)`: `inactive` (> 7 days), then `needs_attention` (last 2 completed sessions, each with ≥ 1 taught word and ≥ 50% `not_mastered`), otherwise `on_track`; `no_sessions` when there are none.
- [X] T025 [P] Write `src/server/tests/test_dashboard_metrics.py` (`unittest`):
  - reading level with each band, the threshold boundary (exactly ⅔), fewer than 2 sessions, override precedence;
  - status boundaries at 7 days, ended-early sessions excluded, exactly 50% not mastered;
  - latest-status-wins for a word seen twice.

**Checkpoint**:
- Unit tests pass.
- A session started with a valid code via the API creates a `session_record`. After disconnect it has `word_outcome` rows (steps NULL) and a `completion` value.
- A teacher-only token gets 403 on `/api/sessions`.

---

## Phase 3: User Story 2 — Link students to my class (P1)

**Goal**: A teacher adds students, gets codes and links, and sessions started with a code are attributed automatically.

**Independent Test**: Add a student. Start KIVA via `/kiva?code=…`. Complete a session. It appears under the student (quickstart §2–3).

- [X] T026 [US2] Create `src/server/dashboard/router.py` with `APIRouter(prefix="/api/teacher")`. Add a dependency `current_class(user=Depends(require_teacher))` that calls `ensure_teacher(user["sub"], user.get("name"))` and returns the class ID. Mount it in `src/server/main.py` with `app.include_router(...)`.
- [X] T027 [US2] Add to `src/server/dashboard/router.py`:
  - `POST /students` (`201`, returns the student with `code` and `link`: `/kiva?code=XXXXXX`);
  - `PATCH /students/{id}` (`display_name`, `status` active|archived, `reading_level_override` 3–8 or null, which also sets `override_set_at`);
  - `POST /students/{id}/code` (regenerate; returns `{code, link}`).
  - Use Pydantic request models with validation, and return `404` when the student isn't in the class.
- [X] T028 [P] [US2] Create `src/client/react/src/components/teacher/labels.ts`, exporting plain-language maps:
  - **status**: on_track "On track", needs_attention "Needs attention", inactive "Inactive", no_sessions "No sessions yet".
  - **word status**: mastered "Mastered", still_learning "Still learning", already_knew "Already knew it".
  - **step names**: definition "Heard a simple definition", story_context "Explained it in the story", personal_connection "Connected it to their life", own_sentence "Used it in their own sentence".
  - **step results**: completed "Done", attempted_not_completed "Tried, not yet", not_reached "Not reached".
  - **review**: mastered "Mastered", not_mastered "Still learning", not_reached "Not reviewed".
  - **completion**: completed "Completed", ended_early "Ended early".
- [X] T029 [P] [US2] Create `src/client/react/src/components/teacher/AddStudentModal.tsx`:
  - An antd `Modal` + `Form` with a "Student name" field (required, at most 40 characters, helper text "First name or nickname only").
  - On submit it calls `POST /api/teacher/students`, then shows the new code (large, monospace) with "Copy link" and "Copy code" buttons (`navigator.clipboard`, antd `message.success`).
- [X] T030 [P] [US2] Create `src/client/react/src/pages/KivaCodeEntry.tsx` at the route `/kiva`:
  - Read `?code=` via `useSearchParams` and save it to `sessionStorage['kiva_student_code']`.
  - Navigate to the home page with the KIVA activity group visible. Use the homepage anchor or route the activity cards use, per `src/server/assets/activity_groups.json` and `components/homepage`.
  - With no code, show a small antd form "Enter your student code" that does the same.
- [X] T031 [US2] Update `src/client/react/src/components/SettingsForm.tsx`:
  - When the activity name is `vocab-tutoring`, show a "Student code" `Input` above the existing USER ID field. Prefill it from `sessionStorage['kiva_student_code']` and uppercase it.
  - When the code has 6 characters, call `GET /api/student-code/{code}`. Show "Hi, {name}!" (antd `Alert type="success"`) or "We didn't recognize that code — check with your teacher." (`type="warning"`).
  - If the code is valid, hide the USER ID field and include `student_code` in the submitted payload (~:487).
  - If submission returns 422, show the server's `detail` and don't navigate.
- [X] T032 [US2] Register the routes in `src/client/react/src/App.tsx`: `/kiva` (inside the authenticated routes, wrapped in `ProtectedRoute`) only. Teacher pages are imported in the phase that creates them (T039, T047, T055, T068, T076), so the build never references files that don't exist yet.
- [ ] T033 [US2] Manual verification per quickstart §2, §3.1–3.2 and the edge rows "invalid code", "regenerated code" and "second teacher account". Record the results in the PR description.

**Checkpoint**: Students can be created and linked, and coded sessions are indexed.

---

## Phase 4: User Story 1 — See my class at a glance (P1) 🎯 MVP

**Goal**: The class list with name, last session, sessions completed, reading level, words mastered and status. Sortable and filterable.

**Independent Test**: Three students with different histories show correct values and statuses with no clicks (quickstart §2; US1 acceptance 1–5).

- [X] T034 [US1] Add `list_class_students(class_id, status)` to `src/server/dashboard/repository.py`. It returns each student with their session records and word outcomes, in a bounded number of queries (no N+1): one query for students, one for sessions joined to outcomes, filtered by class.
- [X] T035 [US1] Add `GET /class?status=&sort=&order=` to `src/server/dashboard/router.py`, using `metrics.student_status`, `cumulative_counts` and `display_reading_level`. Response shape per contracts/rest-api.md. `sessions_completed` counts `completion = completed`.
- [X] T036 [P] [US1] Create `src/client/react/src/components/teacher/StatusTag.tsx`: an antd `Tag` with colours on_track green, needs_attention orange, inactive default, no_sessions default, and labels from `labels.ts`.
- [X] T037 [P] [US1] Create `src/client/react/src/components/teacher/ReadingLevel.tsx`: shows `label`. When `source="teacher"`, append a small "set by teacher" `Tag`. When an `estimate` prop is given and differs, show "(estimate: …)" in secondary text.
- [X] T038 [US1] Create `src/client/react/src/pages/teacher/ClassOverview.tsx` at `/teacher`:
  - `Layout` with the title "My class", an "Add student" button (`AddStudentModal`) and a `Segmented` status filter (All / Needs attention / Inactive / On track).
  - An antd `Table` with columns Name (link to `/teacher/students/:id`), Last session (relative date, or "No sessions yet"), Sessions, Reading level, Words mastered and Status. Sorters on name, last session and words mastered.
  - An "Show archived" toggle (`status=archived`).
  - An empty state ("Add your first student to get started" + button), a loading `Spin` and an error `Alert` with "Try again".
  - On narrow screens (`Grid.useBreakpoint()`, below md), hide the Sessions and Reading level columns.
  - Clicking a row opens the student.
- [X] T039 [US1] Register `/teacher` with `TeacherRoute` in `src/client/react/src/App.tsx`.
- [ ] T040 [US1] Manual verification of US1 acceptance 1–5 and SC-001 (find the "needs attention" students in 10 s or less) with three seeded students. Test the tablet width (768 px).

**Checkpoint**: The MVP (US2 + US1) can be demoed: a teacher links students and monitors the class.

---

## Phase 5: User Story 3 — Student progress summary (P1)

**Goal**: The student page with reading level and override, cumulative counts, a word list with filter, a session timeline and a generated progress summary.

**Independent Test**: A student with 5 sessions shows totals, a trend and a session list matching those sessions (US3 acceptance 1–7).

- [X] T041 [US3] Add `get_student_detail(class_id, student_id)` to `src/server/dashboard/repository.py`. It returns the student, their session records ordered by `started_at DESC`, all their word outcomes, and the `student_summary` row.
- [X] T042 [US3] Add `GET /students/{id}` to `src/server/dashboard/router.py`, building the contract payload:
  - `counts`;
  - `reading_level` (displayed) and `reading_level_estimate`;
  - `reading_level_trend`;
  - `words` with history;
  - `sessions`, with `detail`: `ready` when `analysis_status=ready`, `pending` when pending/running, otherwise `unavailable`;
  - `summary`.
  - Return `404` when the student isn't in the class.
- [X] T043 [US3] Implement `generate_student_summary(student_id)` in `src/server/dashboard/analysis.py`, per contracts/session-analysis.md § Student summary:
  - Build the aggregates only (counts, per-step failure rates, last 5 sessions' mastery ratios, reading-level trend, still-learning words). **Never** read the transcript.
  - Make one `AsyncOpenAI` structured-output call (`DASHBOARD_ANALYSIS_MODEL`) returning `{text, strengths, difficulties, suggested_focus}`.
  - Upsert `student_summary`. On failure, `status=failed`.
- [X] T044 [US3] Call `generate_student_summary` after `ingest_flow_state` in `run_post_session` in `src/server/dashboard/analysis.py`. It is called again after the step analysis in Phase 6. If the student has no sessions with outcomes, skip it.
- [X] T045 [P] [US3] Create `src/client/react/src/components/teacher/LevelTrend.tsx` using antd primitives only (Constitution III): an antd `Statistic` showing the current level with `ArrowUpOutlined` / `ArrowDownOutlined` / `MinusOutlined` and the text "up from Grade 4" / "down from …" / "no change" compared with the first session, plus a compact antd `Timeline` listing only the sessions where the level changed (date + new level). Render nothing with fewer than 2 points.
- [X] T046 [US3] Create `src/client/react/src/pages/teacher/StudentDetail.tsx` at `/teacher/students/:id`:
  - **Header**: name, `StatusTag`, code with "Copy link", and a "More" dropdown (Rename, Regenerate code with confirmation, Archive/Restore).
  - **Card "Reading level"**: `ReadingLevel` + `LevelTrend`, and a "Set level" `Select` (Grade 3–8, or "Use estimate"). It calls `PATCH /students/{id}`.
  - **Row of `Statistic`s**: Already knew it, Taught, Mastered, Still learning.
  - **Card "Summary"**: the text, or "Summary will appear after the next session" / "Summary unavailable".
  - **Card "Words"**: a `Segmented` filter (All / Still learning / Mastered / Already knew it), plus a `Table` with Word, Status, Grade band and Last seen (link to the session).
  - **Card "Sessions"**: a `List` with date, book · chapter, "x of y mastered", a `Tag` for "Ended early", and "Results pending…" / "Detailed results not available". Each item links to `/teacher/sessions/:id`.
  - Loading, error and 404 ("Student not found") states.
- [X] T047 [US3] Register `/teacher/students/:id` with `TeacherRoute` in `src/client/react/src/App.tsx`.
- [ ] T048 [US3] Manual verification of US3 acceptance 1–7 (including override set and clear) per quickstart §4 "reading level" row.

**Checkpoint**: The P1 scope is complete.

---

## Phase 6: User Story 4 — Session detail with per-word task outcomes (P2)

**Goal**: For each session: words already known, and for each taught word the four steps plus the review result. No raw content.

**Independent Test**: A session with 1 known word, 1 word fully completed and 1 word failing "own sentence" displays correctly (quickstart §3.3–3.5).

- [X] T049 [US4] Implement `classify_steps(transcript, taught_words)` in `src/server/dashboard/analysis.py`, per contracts/session-analysis.md § Call 1:
  - The prompt includes the four step definitions and the classification rules.
  - Use the strict JSON schema with `AsyncOpenAI().chat.completions.create(..., response_format={"type": "json_schema", ...})`.
  - Check that the returned word set equals the taught set (case-insensitive), retrying once.
- [X] T050 [US4] Implement `run_post_session(session_dir_id)` in `src/server/dashboard/analysis.py`:
  1. Set `analysis_status=running`.
  2. Load `transcript.json` and the outcomes. If the transcript is missing or has no user turns, set `failed`.
  3. If there are taught words, run `classify_steps` and merge the steps into the `word_outcome` rows. Disposition and review always stay from the flow state.
  4. Set `ready` and `analyzed_at`.
  5. Write `learning_report.json` atomically in the session folder.
  - On exception: increment `analysis_attempts`. If attempts < 2, re-run once, otherwise set `failed` with `analysis_error`.
  - Then call `generate_student_summary`.
- [X] T051 [US4] Add `requeue_pending()` to `src/server/dashboard/analysis.py`, which schedules `run_post_session` for every `session_record` with `analysis_status IN ('pending','running')` whose folder has `flow_state.json`. Call it from the startup hook in `src/server/main.py` (T019).
- [X] T052 [US4] Add `GET /sessions/{id}` to `src/server/dashboard/router.py`, per the contract:
  - Look up the record by `session_record.id` joined to a student in the caller's class (`404` otherwise).
  - Return the session facts (`activity_label` mapped from the activity name, `teacher_selected_words`), `detail`, `already_knew[]` and `taught[]` (with steps, review and `teacher_selected`), plus the `summary` block (Phase 7 fills it in; until then `{"status": "pending"}`).
  - Never include `session_dir_id`.
- [X] T053 [P] [US4] Create `src/client/react/src/components/teacher/StepOutcome.tsx`: an icon and label per result (completed `CheckCircleFilled` green "Done"; attempted_not_completed `ExclamationCircleFilled` orange "Tried, not yet"; not_reached `MinusCircleOutlined` grey "Not reached"), with the step name from `labels.ts`.
- [X] T054 [US4] Create `src/client/react/src/pages/teacher/SessionDetail.tsx` at `/teacher/sessions/:id`:
  - **Breadcrumb**: My class › {student} › {date}.
  - **`Descriptions`**: book, chapter, date, duration, status (`Completed` / `Ended early` tag), and "Words chosen by teacher" when applicable.
  - **Summary card** at the top (filled in Phase 7).
  - **Card "Already knew it"**: word `Tag`s with their grade band.
  - **Card "Words taught"**: one antd `Collapse` panel per word, with a header showing the word, grade band and review tag. The body is a vertical list of four `StepOutcome`s.
  - While `detail="pending"`, show "Results are being prepared — check back in a minute" and poll every 15 s, up to 8 times. When `unavailable`, show "Detailed results not available".
  - When `not_applicable`, show the activity name only.
- [X] T055 [US4] Register `/teacher/sessions/:id` with `TeacherRoute` in `src/client/react/src/App.tsx`.
- [ ] T056 [US4] Manual verification of US4 acceptance 1–4, SC-002 (2 clicks from home), SC-006 (time from session end until detail shows "Ready"; must be 2 minutes or less, recorded for at least 3 sessions) and the "ended early" edge row. Check that no transcript, audio or raw student text appears anywhere in the API responses (inspect them in devtools).

---

## Phase 7: User Story 5 — Auto-generated session summary (P2)

**Goal**: A session summary of about 120 words or fewer, consistent with the outcomes, with no quotes from the student, and a Retry option.

**Independent Test**: Complete a session; its summary agrees with the per-word outcomes and contains no student quotes (quickstart §3.5).

- [X] T057 [P] [US5] Implement `src/server/dashboard/validators.py` as pure functions, per contracts/session-analysis.md § Call 2 validation:
  - `check_length(text, max_words=140)`;
  - `check_word_consistency(summary, outcomes)` (rules 2–4);
  - `check_no_quotes(summary_fields, user_turns, n=6)`, a case-insensitive token n-gram match ignoring punctuation.
  - Each returns a list of violation strings.
- [X] T058 [P] [US5] Write `src/server/tests/test_dashboard_validators.py` (`unittest`) with a passing case and a violating case for each rule, including a 6-word quote embedded in different casing and punctuation, and a 5-word overlap that must pass.
- [X] T059 [US5] Implement `summarize_session(transcript, outcomes, completion, duration)` in `src/server/dashboard/analysis.py`:
  - The prompt follows § Call 2, including the no-quoting and no-personal-details instructions.
  - Use the strict schema.
  - Run the validators. If there are violations, regenerate once with them listed in the prompt. If it still fails, set `summary_status=failed`. Otherwise store `summary_text`, `summary_json` and `summary_status=ready`.
  - For a session with no words, produce a short "ended before any words" summary without an LLM call.
- [X] T060 [US5] Call `summarize_session` from `run_post_session` in `src/server/dashboard/analysis.py`, after the steps are merged. Its failure must not change `analysis_status`. Include the summary in `learning_report.json`.
- [X] T061 [US5] Add `POST /sessions/{id}/retry` to `src/server/dashboard/router.py`:
  - If `analysis_status` or `summary_status` is `running`, return `409 {"detail": "Already working on it."}`.
  - Otherwise reset failed parts to `pending`, set `analysis_attempts=0` and schedule `run_post_session`. Return `202`.
- [X] T062 [US5] Fill in the summary card of `src/client/react/src/pages/teacher/SessionDetail.tsx`:
  - The text, an engagement `Tag` ("Engaged" / "Mixed" / "Low engagement"), "Went well" and "Was hard" word tags, and a "Suggestions" list.
  - "Summary unavailable" with a "Retry" button, which calls the retry endpoint, shows `message.info("Working on it…")` and resumes polling.
  - The retry button also appears for `detail="unavailable"`.
- [ ] T063 [US5] Manual verification of US5 acceptance 1–3 and the "bad OPENAI_API_KEY" edge row (failure, then Retry after restoring the key). Spot-check that summaries contain no student quotes.

---

## Phase 8: User Story 6 — Class-wide vocabulary insights (P3)

**Goal**: Per-word counts across the class, the hardest step, and which students are still learning each word.

**Independent Test**: Several students on the same chapter; counts are correct and sorting by mastery puts the hardest word first.

- [X] T064 [US6] Add `class_word_insights(class_rows)` to `src/server/dashboard/metrics.py` (pure). For each word across active students' latest outcomes, it computes the already_knew, taught, mastered and still_learning counts, `mastery_rate` (mastered ÷ taught, null when taught=0), `hardest_step` (the step most often `attempted_not_completed`, null on ties of zero) and the list of still-learning students.
- [X] T065 [P] [US6] Add `class_word_insights` cases to `src/server/tests/test_dashboard_metrics.py`.
- [X] T066 [US6] Add `GET /insights/words?sort=` to `src/server/dashboard/router.py`, reusing `list_class_students` from T034.
- [X] T067 [US6] Create `src/client/react/src/pages/teacher/WordInsights.tsx` at `/teacher/words`:
  - A `Table` with columns Word, Grade band, Already knew, Taught, Mastered, Still learning, Mastery (`Progress` percent) and Hardest step (label).
  - The default sort is mastery ascending.
  - Expandable rows list the still-learning students as links.
  - Empty state: "Word insights appear after your students complete sessions."
- [X] T068 [US6] Register `/teacher/words` with `TeacherRoute` in `src/client/react/src/App.tsx`, and add "Class" / "Words" `Segmented` or tab navigation in the header of `src/client/react/src/pages/teacher/ClassOverview.tsx`.
- [ ] T069 [US6] Manual verification of US6 acceptance 1–3.

---

## Phase 9: User Story 7 — Notes and printable report (P3)

**Goal**: Private timestamped notes on students and sessions, and a printable progress report per student.

**Independent Test**: A note persists across reloads and is invisible to another teacher; the report contains the summary, word lists and session history.

- [X] T070 [US7] Add `list_notes`, `create_note`, `update_note` and `delete_note` to `src/server/dashboard/repository.py`. Each is filtered by `teacher_email`, and validates that `target_id` belongs to the teacher's class (a student, or a session of one of their students). Body is 1–2,000 characters.
- [X] T071 [US7] Add `GET/POST /notes` and `PATCH/DELETE /notes/{id}` to `src/server/dashboard/router.py`, per the contract. Return `404` for another teacher's note.
- [X] T072 [P] [US7] Create `src/client/react/src/components/teacher/NotesPanel.tsx`, with props `targetType` and `targetId`:
  - An antd `List` of notes (body, relative time, edit and delete with `Popconfirm`) and a `TextArea` with an "Add note" button.
  - Helper text "Only you can see these notes."
- [X] T073 [US7] Add `NotesPanel` to `src/client/react/src/pages/teacher/StudentDetail.tsx` (as a card) and to `src/client/react/src/pages/teacher/SessionDetail.tsx` (below the words).
- [X] T074 [US7] Add `GET /students/{id}/report` to `src/server/dashboard/router.py`, returning the student-detail payload plus the student-level notes and `generated_at`.
- [X] T075 [US7] Create `src/client/react/src/pages/teacher/StudentReport.tsx` at `/teacher/students/:id/report`:
  - A print-friendly layout: student name, date, reading level, counts, summary, word lists grouped by status, a session history table and notes.
  - A "Print" button that calls `window.print()`, and an `@media print` stylesheet that hides navigation and the button.
  - Add a "Print report" button to the `StudentDetail.tsx` header that links to it.
- [X] T076 [US7] Register `/teacher/students/:id/report` with `TeacherRoute` in `src/client/react/src/App.tsx`.
- [ ] T077 [US7] Manual verification of US7 acceptance 1–2 and of note privacy using a second teacher account.

---

## Phase 10: Polish & cross-cutting

- [X] T078 [P] Performance check for SC-007: write the throwaway script `src/server/tests/seed_dashboard_load.py`, which seeds 35 students × 180 sessions × 4 words into a temporary DB (`DASHBOARD_DB_PATH`). Time `GET /api/teacher/class` and `GET /api/teacher/students/{id}`; both must be under 3 s. Add indexes or reduce queries if not. Delete the script, or keep it documented in quickstart if useful.
- [X] T079 [P] Privacy audit of `src/server/dashboard/router.py`. Grep every response model for `session_dir_id`, `user_key`, `transcript`, `analysis_error` and audio paths, and confirm none appear. Confirm `dashboard.db` is not under the `sessions/` static mount.
- [X] T080 [P] UX consistency pass over `src/client/react/src/pages/teacher/*`:
  - Every view has loading, empty and error states.
  - No raw API errors or IDs are shown.
  - Labels all come from `labels.ts`.
  - No horizontal page scroll at 768 px.
- [X] T081 [P] Update `src/server/README.md` with the `teacher_emails` allowlist field, `DASHBOARD_*` env vars, the `data/` volume, and the "use a non-teacher classroom account on student devices" guidance.
- [X] T082 Run `pre-commit run --all-files` and `cd src/server && python -m unittest discover -s tests`, and fix any findings.
- [ ] T083 Full regression per quickstart §5: a non-KIVA activity without a code behaves exactly as before. Run a complete happy path, from activity selection through to the session being saved.
- [ ] T084 Accuracy spot-check for SC-003: compare the recorded per-word outcomes against transcripts for at least 20 sessions. Note any prompt changes in `src/server/dashboard/analysis.py`, and record the results in the PR.

---

## Implementation status (2026-10-08)

- Done: every build task. Server unit tests pass (31). The API was smoke-tested end to end with a fake finished session and through `main.py`: student codes, 422 on a bad code, role gating, and no-code sessions unchanged. The client passes `tsc`, ESLint and Prettier on the new files, and `npm run build` succeeds. The dashboard was checked in the browser with seeded data at desktop and tablet widths. Load check (T078): 35 students × 180 sessions; the class list returns in 0.21 s.
- T082: `pre-commit` isn't installed locally, so Black, Flake8, ESLint and Prettier were run directly. Black was applied only to new files and to edited files that were already Black-formatted; `main.py`, `handlers.py` and `bot_runner.py` weren't before, so they weren't reformatted.
- Still open (needs a live voice session with a real `OPENAI_API_KEY`): T033, T040, T048, T056, T063, T069, T077, T083, T084.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: depends on Setup. **Blocks all stories.**
- **US2 (Phase 3)**: depends on Foundational.
- **US1 (Phase 4)**: depends on Foundational. It needs students to exist, so it is practically after T026–T027. The UI can be built against data seeded through the API.
- **US3 (Phase 5)**: depends on Foundational. It reuses the components from T036–T037.
- **US4 (Phase 6)**: depends on Foundational (ingestion, T022–T023). It is independent of the US1/US3 UI, although its pages are reached from them.
- **US5 (Phase 7)**: depends on US4's `run_post_session` (T050) and the `SessionDetail` page (T054).
- **US6 (Phase 8)**: depends on Foundational and T034. It is more useful after US4 (step data).
- **US7 (Phase 9)**: depends on the US3 and US4 pages (it adds panels to them).
- **Polish (Phase 10)**: after the desired stories are done.

### Key task dependencies

- T006 → T009 → all repository and router tasks
- T010 → T012, T013, T026
- T020 → T021, T023
- T022 → T023, T050
- T024 → T035, T042, T064
- T050 → T051, T060, T061

### Parallel Opportunities

- **Phase 1**: T001–T004 together.
- **Phase 2**: T007/T008, T011, T014/T015, T020, and T024/T025 in parallel once T006 is done.
- **US2**: T028, T029, T030 in parallel (separate client files).
- **US1**: T036 and T037 in parallel with T034/T035 (server).
- **US4**: T053 in parallel with the server tasks T049–T052.
- **US5**: T057 and T058 in parallel with T059's prompt work.
- **Polish**: T078–T081 in parallel.

### Parallel Example: User Story 2

```text
Task: "T028 Create labels.ts in src/client/react/src/components/teacher/labels.ts"
Task: "T029 Create AddStudentModal.tsx in src/client/react/src/components/teacher/AddStudentModal.tsx"
Task: "T030 Create KivaCodeEntry.tsx in src/client/react/src/pages/KivaCodeEntry.tsx"
```

### Parallel Example: Foundational

```text
Task: "T007 codes.py" + "T008 test_dashboard_codes.py"
Task: "T020 flow_snapshot.py"
Task: "T024 metrics.py" + "T025 test_dashboard_metrics.py"
Task: "T014 AuthContext roles" + "T015 TeacherRoute.tsx"
```

---

## Implementation Strategy

### MVP first (US2 + US1)

1. Phase 1 Setup → Phase 2 Foundational. Validate with the unit tests plus one coded session producing a `session_record` with words.
2. Phase 3 (US2) → Phase 4 (US1). **Stop and validate**: a teacher can link students and see class status from flow-state data alone.
3. Demo.

### Incremental delivery

1. Phase 5 (US3): student summary and reading level. **The P1 scope is complete.**
2. Phase 6 (US4) and Phase 7 (US5): per-step drill-down and session summaries. **The P2 scope is complete.**
3. Phase 8 (US6) and Phase 9 (US7): extras.
4. Phase 10: performance, privacy and accuracy validation before any classroom pilot.

---

## Notes

- Commit after each task or logical group. Never commit `src/server/data/` or `src/server/sessions/`.
- Do not edit any `flow_config.json` file.
- Anything that runs in the conversation path (T021, T023) must swallow and log its own exceptions.

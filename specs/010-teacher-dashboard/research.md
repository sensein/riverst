# Research: Teacher Monitoring Dashboard

**Feature**: 010-teacher-dashboard | **Date**: 2026-10-08

These are the decisions behind the plan's Technical Context. Each one records what was found in the codebase and what was chosen.

---

## R1. Where per-word step outcomes come from

**Finding**: The live flow does not track teaching steps per word.

- The `vocab` node checklist (`defined_simply`, `asked_book_context_understanding`, `asked_broader_context_understanding`, `asked_for_new_sentence`) belongs to the node. `update_checklist` only ever sets items to true (`src/server/bot/flows/handlers.py:201`).
- The prompt has the LLM call `check_vocab_progress` once, *after* all 3 words.
- The live state does record which words were known, taught, mastered and not mastered: `state["user"]["vocab_words_known"]`, `vocab_words_taught`, `vocab_words_taught+mastered` and `vocab_words_taught+not_mastered`. It is in memory only and lost at the end of the session.

**Decision**: Use two sources and merge them.

1. **The live flow state** decides each word's *disposition* (known or taught) and its *review result* (mastered or not mastered). The server snapshots `flow_manager.state["user"]` and the current node to `flow_state.json` in the session folder. It does this on every progress call (`general_handler`) and again on disconnect.
2. **A post-session analysis** reads `transcript.json` and classifies each taught word's four teaching steps as `completed`, `attempted_not_completed` or `not_reached`. It also produces the session summary.

If the two disagree about disposition or review result, the flow state wins. The analysis is only asked about step outcomes for words the flow state already lists.

**Rationale**:

- The live conversation is unchanged, so there is no new risk to the 2 s p95 latency budget (Constitution IV).
- No hand-editing of `flow_config.json` is needed.
- The LLM tutor already makes the known/taught/mastered decisions, so reusing them keeps the dashboard consistent with what KIVA did.
- Judging whether a child *completed* a step needs the whole exchange, and a post-hoc pass over the full transcript does that better than a mid-conversation function call.

**Alternatives considered**:

- *New per-word function `record_word_outcome` called live by the tutor.* This gives the most structured data. It was rejected because it adds a tool call per word mid-conversation (latency), needs `flow_config.json` edits in three activities, and the LLM may forget to call it, leaving gaps.
- *Post-hoc analysis only.* This is simpler, but the transcript alone is noisier than the tutor's own decision about known and mastered words. Rejected as the sole source.

---

## R2. Dashboard storage

**Finding**: There is no database. Everything is JSON files written with plain `open("w")`, which is not atomic and has no locking. `src/server/sessions/` is served **without auth** through the `StaticFiles` mount at `/api/sessions` (`main.py:61`).

**Decision**: Use a single SQLite file at `src/server/data/dashboard.db` through Python's standard-library `sqlite3`. It holds teachers, classes, students and codes, the session index, word outcomes, summaries and notes.

- The folder is new. Add it to `src/server/.gitignore` and mount it as a Docker volume (`./src/server/data:/app/data`).
- It MUST NOT live under `sessions/`, because that folder is publicly served.
- A copy of each session's analysis is also written as `learning_report.json` in the session folder, for researchers. The dashboard never reads it.

**Rationale**:

- SC-007 means about 35 students × about 180 sessions a year ≈ 6,300 sessions. Scanning that many folders on every page load won't meet a 3 s target. Indexed SQL queries will.
- Roster edits, notes and reading-level overrides need safe concurrent writes, which the file approach lacks.
- SQLite adds no dependency and no service.

**Alternatives considered**:

- *JSON files per teacher.* No query support, and races on edits.
- *Postgres.* A new service for a single-server deployment is unjustified.

---

## R3. Tying sessions to students (student code)

**Finding**: `user_id` is a random UUID made on the client (`SettingsForm.tsx:106`) and shown as an editable "USER ID" field. The server builds `session_id = {user_id}__{timestamp}_{uuid8}` (`main.py:197–227`). Long-term memory looks up a user's past sessions by `user_id` (`memory.py:136`).

**Decision**:

- Each student gets a 6-character code from an unambiguous alphabet: `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, which excludes 0/O and 1/I/L. That gives about 887 million combinations, and uniqueness is checked when a code is created.
- The client sends `student_code` on `POST /api/session`. The server resolves it to a student. An unknown code returns `422`, and the client shows "We didn't recognize that code — check with your teacher."
- When the code is valid, the server **sets `user_id` to the student's stable opaque key** `stu_<16 hex>`. That key never contains the name or the code. This keeps long-term memory working across a student's sessions.
- The server records `student_id` in `config.json` and in the session index.
- The link format is `/kiva?code=K7MPQ4`. A small route stores the code in `sessionStorage` and redirects to the KIVA activity list. `SettingsForm` prefills the "Student code" field from `sessionStorage`. The `?code=` parameter is not carried through router state, because `settingsUrl` comes only from router state.
- Regenerating a code overwrites `student.code`. Past sessions stay linked through `student_id`.

**Alternatives considered**:

- *Using the code itself as `user_id`.* Rejected: the code would end up in folder names, and regenerating it would break memory continuity.
- *Linking after the fact.* Rejected in the spec (Q1).

---

## R4. Teacher authentication and roles

**Finding**: Google sign-in checks against the allowlist `authorization/authorized_users.json` (`{"authorized_emails": [...]}`). The JWT claims are `{sub: email, name, exp}` with a 30-minute lifetime. There are no roles, and every signed-in user can open `/sessions` and `/sessions/:id`, which show transcripts and audio features.

**Decision**: Add an optional `teacher_emails` list to the same allowlist file.

- An email in `teacher_emails` counts as authorized to sign in and gets the `teacher` role.
- An email in `authorized_emails` keeps today's full access and gets the `researcher` role.
- An email in both lists has both roles.
- The JWT gets a `roles` claim. `/api/auth/me` returns it, so the client can show or hide navigation.
- New dependencies: `require_teacher`, and `require_researcher` for the existing raw-session endpoints (`GET /api/sessions`, `GET /api/session/{id}`).
- A teacher-only account therefore cannot reach transcripts (FR-021), and the `/sessions` pages are hidden from it.
- Student devices should be signed in with a non-teacher classroom account, so students can't open the dashboard (FR-004). `quickstart.md` documents this.

**Rationale**: This reuses the existing mechanism, as the spec assumes. Without a role split, every teacher would be a researcher who can read transcripts, which contradicts Q3.

**Known residual risk (pre-existing, out of scope)**: The `StaticFiles` mount at `/api/sessions` serves session folders without auth. It is reachable only by someone who knows the exact `session_id`, which contains a random `uuid8` and a timestamp. Teachers never receive session folder IDs: the dashboard API uses its own opaque session record IDs. A follow-up should put that mount behind researcher auth.

---

## R5. Post-session analysis trigger and LLM

**Finding**:

- Session teardown happens in `on_client_disconnected` (`bot/core/event_manager.py:97–131`). It already starts a background `asyncio.create_task` for audio analysis.
- An end triggered by the LLM goes through `task.stop_when_done()`. The client then disconnects, so the same handler runs.
- `OPENAI_API_KEY` is always present, and the default text model is `gpt-4.1` (`component_factory.py:344`).
- Nothing in the codebase calls the `openai` SDK directly, but the package is installed through pipecat.

**Decision**:

- In `on_client_disconnected`, after the final `flow_state.json` snapshot, schedule `analyze_session(session_id)` with `asyncio.create_task` when the session has a `student_id` and a vocabulary activity.
- Use `openai.AsyncOpenAI` with **structured outputs** (a JSON schema) and the model `gpt-4.1`, configurable with `DASHBOARD_ANALYSIS_MODEL`. Declare `openai` explicitly in `requirements.txt`, pinned to the version pipecat already installs.
- Make two calls:
  1. **Step outcomes**: transcript plus the word list from the flow state, returning step outcomes per taught word.
  2. **Session summary**: the merged outcomes plus the transcript, returning the summary text plus `words_went_well[]` and `words_hard[]`.
- On server start, re-queue sessions still `pending` or `running`, so a crash or restart doesn't leave a session stuck.
- One automatic retry on failure. After that the status is `failed`, with a teacher-visible "Retry" (FR-020).

**Rationale**: About 2 calls × 10–30 s fits SC-006's 2-minute window. Structured output removes parsing errors.

---

## R6. Keeping summaries consistent with outcomes (FR-019), and no quoting (FR-021)

**Decision**: The summary call returns structured `words_went_well[]` and `words_hard[]` next to the text. The server checks them:

- every listed word must be in the session's taught words;
- a word in `words_went_well` must not be `not_mastered`, and a word in `words_hard` must not be `mastered` unless a step was `attempted_not_completed`.

On failure, the server regenerates once with the conflicts pointed out, then marks the summary `failed`.

For quoting, the prompt forbids quoting the student. The server then rejects any summary that contains a run of 6 or more consecutive words from a user turn in the transcript, and regenerates once.

The student progress summary (FR-016) is built **only from aggregated outcomes**, never the transcript. It is regenerated after each successful session analysis.

**Alternatives considered**: An LLM judge pass. Rejected as costlier and less predictable than these deterministic checks.

---

## R7. Reading-level estimate, status, completion — deterministic server logic

**Decision**: These are pure functions in `src/server/dashboard/metrics.py`, unit-testable with `unittest` (the existing test style):

- **Reading level**:
  - Use the student's last 5 sessions with ingested word outcomes. This needs only the flow state, not the AI analysis.
  - For each grade band (4, 5, 6), compute (mastered + already known) ÷ words encountered in that band.
  - The level is the highest band where the ratio is at least ⅔ and at least 2 words were encountered.
  - If no band qualifies, show "Below grade-4 words". With fewer than 2 such sessions, show "Not enough sessions yet".
  - A teacher override replaces the displayed level everywhere.
- **Grade band of a word**: looked up in the book's resource file (the `vocab` grade_4/5/6 lists for that chapter). A word that isn't in those lists, such as a teacher override word, gets `grade_band = null` and is excluded from the reading-level estimate.
- **Status**: the first rule that matches wins.
  - `inactive`: the last session was more than 7 days ago.
  - `needs_attention`: each of the last 2 *completed* sessions had at least 1 taught word, and in each, at least half of its taught words were `not_mastered`.
  - `on_track`: otherwise.
- **Completion**: `completed` if the last snapshot node is `closing` or `end`, otherwise `ended_early`.
- **Duration**: from the first transcript timestamp to the last.

---

## R8. Frontend approach

**Finding**: React 19, antd 5.26 and react-router 7 (BrowserRouter). Data is fetched with `useEffect` and `useState` through `useAuth().authRequest` (axios with a Bearer header). There is no chart library, no test framework and no responsive conventions yet.

**Decision**:

- New lazy-loaded pages under `/teacher`, each wrapped in a new `TeacherRoute` that checks for the `teacher` role.
- Built from antd `Table`, `Tag`, `Statistic`, `Descriptions`, `Collapse`, `Segmented`, `Modal` and `Grid.useBreakpoint`, for tablet layout (FR-027).
- The reading-level trend uses antd primitives only (Constitution III): a `Statistic` with an up, down or flat arrow ("Grade 5 words, up from Grade 4"), and a compact `Timeline` of level changes. No custom SVG and no chart dependency.
- The printable report is a `/teacher/students/:id/report` page with print CSS and a "Print" button (`window.print()`). No PDF library.
- All teacher-facing labels live in one `labels.ts` map ("Mastered", "Still learning", "Already knew it"…), to keep FR-026 consistent.

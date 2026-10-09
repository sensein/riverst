# Implementation Plan: Teacher Monitoring Dashboard

**Branch**: `010-teacher-dashboard` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/010-teacher-dashboard/spec.md`

## Summary

Teachers get a role-scoped dashboard (`/teacher`) with three levels:

1. **Class overview**: status flags (on track, needs attention, inactive).
2. **Student summary**: reading level with teacher override, word lists, and a generated progress summary.
3. **Session detail**: words the student already knew, plus each taught word's four steps and review result, and a generated session summary.

Students are linked through a 6-character code or link entered when they start KIVA. The server maps the code to a stable, opaque `user_id`.

KIVA does not record per-word outcomes today, so the plan adds two pieces:

- **Flow-state snapshots**: the tutor's own known/taught/mastered decisions, saved to `flow_state.json`.
- **Post-session analysis**: two structured LLM calls that classify the teaching steps from the transcript and write a summary. Deterministic checks keep the summaries consistent with the outcomes and free of quotes from the student.

Dashboard data lives in a new SQLite store, outside the publicly served `sessions/` folder. Teachers never see raw content.

## Technical Context

**Language/Version**: Python 3.11 (server), TypeScript ~5.8 / React ~19.1 (client)
**Primary Dependencies**: FastAPI, pipecat-ai 0.0.89 and pipecat-ai-flows (existing), `openai` (`AsyncOpenAI`, now declared explicitly), stdlib `sqlite3`; antd ~5.26, react-router-dom ~7.5, axios ~1.10 (existing). No new client dependencies.
**Storage**: SQLite `src/server/data/dashboard.db` (new, gitignored, Docker volume). New per-session files `flow_state.json` and `learning_report.json`.
**Testing**: `unittest` for pure logic (metrics, validators, code generation, role checks), plus manual integration per `quickstart.md` (Constitution II). There is no client test framework, and none is added.
**Target Platform**: The existing Docker Compose stack: Linux server, browser client on laptops and tablets.
**Project Type**: Web application (the existing `src/server` + `src/client/react`).
**Performance Goals**: Class overview in under 3 s for 35 students × about 180 sessions each (SC-007). Results within 2 minutes of session end (SC-006). No change to the live-conversation latency.
**Constraints**:
- No raw session content reaches teacher-role accounts (FR-021).
- No changes to `flow_config.json`.
- Analysis runs off the conversation path, after disconnect.
- Error messages are actionable and expose no internals.

**Scale/Scope**: About 10 teacher-facing screens/views, about 15 new endpoints, 6 new tables. Applies to `vocab-tutoring` only. `esl-vocab-tutoring` and `isl-vocab-tutoring` run without a structured flow (`advanced_flows: false`), so they have no flow state and are out of scope for v1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Code Quality | ✅ Pass | New server code is a self-contained `src/server/dashboard/` package (one responsibility per module). Auth and roles stay in `authorization/`. Black/Flake8 120, ESLint/Prettier, and Google docstrings apply. |
| II. Testing Standards | ✅ Pass | `quickstart.md` defines the full live-session checks and the regression path. Pure logic gets `unittest` coverage as an addition. |
| III. UX Consistency | ✅ Pass | antd primitives only, with explicit loading, pending, unavailable and error states for every view. Student-code errors are actionable. The KIVA session lifecycle UX is unchanged, apart from one form field. |
| IV. Performance | ✅ Pass | No work is added to the conversation pipeline except one small atomic JSON write per progress call (well under 1 ms). LLM analysis runs after disconnect. SQLite is indexed for SC-007. |
| Dev Workflow | ✅ Pass | No `flow_config.json` edits. New secrets come only from `.env`. The DB lives in a gitignored `data/`, never in `sessions/`, and no session data is committed. |
| Quality Gates | ✅ Pass | Gate 5 is reinforced: `.gitignore` gains `data/`. |

**Post-design re-check (after Phase 1)**: still passing.

- **Residual pre-existing risk**: the unauthenticated `StaticFiles` mount of `sessions/`, recorded in research R4. It is mitigated because teacher APIs never return session folder IDs. It should be tracked as a follow-up issue, not fixed here, because researcher audio playback depends on it.

## Project Structure

### Documentation (this feature)

```text
specs/010-teacher-dashboard/
├── plan.md                    # this file
├── research.md                # Phase 0: R1–R8 decisions
├── data-model.md              # Phase 1: SQLite schema + derived metrics
├── quickstart.md              # Phase 1: setup + manual integration checks
├── contracts/
│   ├── rest-api.md            # /api/teacher/* + auth/session changes
│   └── session-analysis.md    # post-session LLM calls, schemas, validators
├── checklists/requirements.md
└── tasks.md                   # Phase 2 (/speckit-tasks), not created here
```

### Source Code (repository root)

```text
src/server/
├── main.py                         # mount teacher router; student_code on POST /api/session;
│                                   # researcher role on /api/sessions, /api/session/{id}; startup re-queue
├── authorization/
│   └── auth.py                     # teacher_emails, roles claim, require_teacher / require_researcher
├── dashboard/                      # NEW package
│   ├── __init__.py
│   ├── db.py                       # connection, schema creation/versioning, transactions
│   ├── repository.py               # teacher/class/student/session/word/note queries
│   ├── codes.py                    # student code + user_key generation
│   ├── metrics.py                  # reading level, status, completion, word status, insights (pure)
│   ├── flow_snapshot.py            # atomic flow_state.json writer
│   ├── analysis.py                 # analyze_session(): two LLM calls, merge, validate, persist
│   ├── validators.py               # FR-019 consistency + no-quote checks (pure)
│   └── router.py                   # FastAPI APIRouter for /api/teacher/*
├── bot/flows/handlers.py           # general_handler → flow_snapshot.write()
├── bot/core/event_manager.py       # on disconnect: final snapshot + schedule analysis
├── requirements.txt                # + openai (pinned to pipecat's version)
├── .gitignore                      # + data/
└── tests/
    ├── test_dashboard_metrics.py
    ├── test_dashboard_validators.py
    └── test_dashboard_codes.py

src/client/react/src/
├── App.tsx                         # /kiva, /teacher/* routes
├── contexts/AuthContext.tsx        # user.roles
├── components/
│   ├── TeacherRoute.tsx            # role guard
│   ├── SettingsForm.tsx            # "Student code" field (prefilled from sessionStorage), name confirmation
│   └── teacher/
│       ├── labels.ts               # plain-language label map (FR-026)
│       ├── StatusTag.tsx
│       ├── ReadingLevel.tsx        # value + "set by teacher" + estimate
│       ├── LevelTrend.tsx          # antd Statistic + Timeline trend
│       ├── StepOutcome.tsx         # ✓ / tried, not yet / not reached
│       ├── NotesPanel.tsx
│       └── AddStudentModal.tsx
└── pages/
    ├── KivaCodeEntry.tsx           # /kiva?code= → sessionStorage → KIVA activity list
    └── teacher/
        ├── ClassOverview.tsx       # /teacher
        ├── StudentDetail.tsx       # /teacher/students/:id
        ├── SessionDetail.tsx       # /teacher/sessions/:id
        ├── WordInsights.tsx        # /teacher/words  (P3)
        └── StudentReport.tsx       # /teacher/students/:id/report (print, P3)

docker-compose.yaml                 # server volume ./src/server/data:/app/data
```

**Structure Decision**: Extend the existing web-application layout. Server logic goes in a new `src/server/dashboard/` package, with changes to existing files limited to integration points. Client screens go under `pages/teacher/` and `components/teacher/`, matching the current pages/components split and lazy-loaded routes.

## Delivery order (maps to spec priorities)

1. **Foundation**: SQLite store, roles, student codes, `student_code` on session creation, flow snapshots. Unblocks everything.
2. **P1**: US2 (link students) → US1 (class overview) → US3 (student summary, reading level + override). Until the analysis lands, the counts use the flow-state data only.
3. **P2**: post-session analysis → US4 (session detail) → US5 (session summary + retry).
4. **P3**: US6 (word insights) → US7 (notes, printable report).

## Risks

| Risk | Mitigation |
|---|---|
| The LLM misclassifies teaching steps (SC-003) | Disposition and review come from the tutor's flow state, and only steps are LLM-judged. Spot-check 20 sessions before pilot. Prompt tuned against those. |
| `on_client_disconnected` doesn't fire (server crash) | Startup re-queue of `pending`/`running` records. The flow snapshot is written on every progress call, so data survives. |
| A student device is signed in with a teacher account | Documented setup (classroom account). The role guard hides `/teacher` only from non-teachers, so this is an operational rule. Noted in quickstart. |
| `short_term_memory=false` cleanup removes `transcript.json` | Cleanup runs at session *start*, on the new folder. Verify during implementation that it never touches a folder still awaiting analysis. |

## Complexity Tracking

No constitution violations. Table not required.

# Tasks: Avatar Edge Case Fallback Handling

**Input**: Design documents from `specs/007-avatar-fallback-handling/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md), [research.md](research.md), [quickstart.md](quickstart.md)

**Tests**: No automated test suite exists in this project. Verification is by manual integration testing via live WebRTC session.

**Organization**: Tasks are grouped by user story. The foundational phase creates the loader mechanism; each user story phase adds and validates its specific scenario(s) in `shared_persona.json`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- Exact file paths are included in every task description

---

## Phase 1: Setup

No new project initialization needed — this feature modifies an existing Python package and adds one new JSON file. No new dependencies, no schema migrations, no new endpoints.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create the shared persona loading mechanism in `loaders.py` and the initial `shared_persona.json` schema. All user story phases depend on this being complete and passing lint.

**⚠️ CRITICAL**: No user story scenario can be tested until the loader injection is wired up.

- [x] T001 Create `src/server/bot/shared_persona.json` with the top-level schema: `version` ("1.0.0"), `description`, and a `scenarios` array containing the `english_only` scenario as its first and only entry (name, trigger, instruction as specified in [data-model.md](data-model.md)) — this is a hard platform constraint (FR-004) that must be active from the first live test onward, not deferred to Phase 5
- [x] T002 Add `_load_shared_persona()` helper function to `src/server/bot/flows/loaders.py`: reads `shared_persona.json` relative to the `flows/` package directory and assembles all scenario `instruction` fields into a single formatted system-prompt block — reads from disk on every call (no module-level cache) so updated scenarios take effect in the next session without a server restart
- [x] T003 Modify `load_flow_config()` in `src/server/bot/flows/loaders.py` to call `_load_shared_persona()` after the optional `preprocess_flow_config` hook and before `FlowConfigurationFile(**flow_config_data)` validation: iterate over every node in `flow_config_data["flow_config"]["nodes"]`, call `setdefault("role_messages", [])` on each, and append `{"role": "system", "content": <shared_persona_text>}` to that list
- [x] T004 Add Google-style docstrings to `_load_shared_persona()` and any other new or substantially modified functions in `src/server/bot/flows/loaders.py`
- [x] T005 Run `pre-commit run --all-files` from `src/server/` and confirm Black, Flake8 (120-char max), and all other hooks pass with zero errors
- [ ] T005a Run a baseline FR-007 verification: start a `vocab-tutoring` session and complete at least one full warm-up → vocab → review cycle. Confirm all node transitions fire at the correct times (`check_warm_up_progress`, `check_vocab_progress`, `check_review_progress` all called without premature or missed triggers). This establishes the expected behavior and confirms the shared persona injection does not interfere with existing activity-specific task instructions (FR-007).

**Checkpoint**: The `vocab-tutoring` session in T005a should behave identically to before the loader change. The `english_only` scenario is now active (added in T001) — if the student responds in Spanish at any point, the avatar must reply in English. Confirm in server logs that the shared persona block is being injected (add a debug log in `_load_shared_persona()` if helpful, remove before merge).

---

## Phase 3: User Story 1 — Off-Topic Redirect (Priority: P1) 🎯 MVP

**Goal**: When a student says something significantly off-topic, the avatar briefly acknowledges and returns to the task within one turn, without calling any transition function.

**Independent Test**: Start a `vocab-tutoring` session. Mid-lesson, say "Did you know my dog ate a sock?" Confirm the avatar acknowledges the comment in one short sentence and returns to the exact vocab step it was on. Say something off-topic two turns in a row and confirm the redirect becomes warmer and more explicit. Say something emotionally charged ("I'm really upset") and confirm the avatar shows brief empathy before returning.

- [x] T006 [US1] Add the `off_topic_redirect` scenario to the `scenarios` array in `src/server/bot/shared_persona.json`: `name`: `"off_topic_redirect"`, `trigger`: `"Student says something significantly unrelated to the current task"`, `instruction`: the full redirect instruction from [data-model.md](data-model.md) covering single-digression, repeated-digression, and emotionally-charged cases
- [ ] T007 [US1] Start a new session and run the manual integration test described in the Independent Test above; tune the `instruction` text in `src/server/bot/shared_persona.json` if the avatar's behavior does not match the acceptance scenarios in [spec.md](spec.md) (US1, scenarios 1–3) — no server restart needed; each new session reads the updated JSON
- [ ] T008 [US1] Confirm that no state-transition function (e.g., `check_vocab_progress`, `check_warm_up_progress`) is called during the off-topic exchange by checking the server logs; if a transition fires prematurely, add an explicit instruction to `off_topic_redirect` prohibiting function calls until the student is back on task

**Checkpoint**: US1 passes all three acceptance scenarios from spec.md. Off-topic redirect is live and tuned.

---

## Phase 4: User Story 2 — Silence and Refusal Handling (Priority: P2)

**Goal**: The avatar gives the student adequate think time before treating silence as non-participation, never repeats the same question verbatim, escalates through hint → simpler → graceful close, and does not trigger any state transition while in a refusal/silence state.

**Independent Test**: Start a `vocab-tutoring` session. (a) Go completely silent after being asked a question — confirm the avatar gives one warm wait-prompt and waits again before escalating. (b) Say "I don't know" — confirm the avatar gives a hint rather than repeating the question. (c) Say "I don't want to do this" — confirm the avatar acknowledges the feeling and tries a different approach. (d) Refuse three consecutive questions — confirm the avatar moves toward session close gracefully.

- [x] T009 [US2] Add the `silence_handling` scenario to `src/server/bot/shared_persona.json` (position it after `off_topic_redirect`): `name`: `"silence_handling"`, `trigger`, and `instruction` covering the two-stage wait (one warm prompt, then wait before escalating) as specified in [data-model.md](data-model.md)
- [x] T010 [US2] Add the `refusal_handling` scenario to `src/server/bot/shared_persona.json` (position it after `silence_handling`): `name`: `"refusal_handling"`, `trigger`, and `instruction` covering the hint → simplify → different approach → graceful close ladder as specified in [data-model.md](data-model.md)
- [ ] T011 [US2] Start a new session and run the manual integration test described in the Independent Test above (parts a–d); tune `silence_handling` and `refusal_handling` instruction texts in `src/server/bot/shared_persona.json` until all acceptance scenarios from spec.md (US2, scenarios 1–5) pass — no server restart needed; also verify the graceful-close path (US2 scenario 5): the `refusal_handling` instruction must explicitly state that after sustained consecutive refusals the avatar **is permitted** to call the closing/end transition function (this is the intended exception to FR-005's "no transitions during fallback" rule — session close is the goal, not a premature transition)
- [ ] T012 [US2] Confirm in server logs that no state-transition function fires during any silence or refusal exchange; if premature transitions occur, add an explicit prohibition to the relevant scenario instruction

**Checkpoint**: US1 and US2 both pass their acceptance scenarios. Silence, "I don't know," and explicit refusals are all handled. Graceful session close under sustained refusal is live.

---

## Phase 5: User Story 3 — English-Only Enforcement (Priority: P3)

**Goal**: 100% of avatar turns are in English regardless of the language the student uses. The avatar may briefly note it will continue in English but does not scold or code-switch.

**Independent Test**: Start a `vocab-tutoring` session. (a) Respond entirely in Spanish — confirm every word of the avatar's reply is English. (b) Continue in Spanish for three turns — confirm the avatar stays in English and may gently note its language without making the student feel wrong. (c) Mix Spanish and English in the same sentence — confirm the avatar responds only to the English content and continues in English.

- [x] T013 [US3] Verify `english_only` is at position 0 (first entry) in the `scenarios` array in `src/server/bot/shared_persona.json` — it was added there in T001 as a hard constraint; confirm the instruction text matches [data-model.md](data-model.md) and the highest-salience placement is preserved after Phases 3–4 scenario additions
- [ ] T014 [US3] Start a new session and run the manual integration test described in the Independent Test above (parts a–c); tune the `english_only` instruction in `src/server/bot/shared_persona.json` if any non-English words appear in avatar responses or if the student is made to feel scolded — no server restart needed
- [x] T015 [US3] Verify the final scenario order in `src/server/bot/shared_persona.json` is `english_only` → `off_topic_redirect` → `silence_handling` → `refusal_handling`; this priority ordering matches the spec and Scenario Priority section in [plan.md](plan.md)

**Checkpoint**: US1, US2, and US3 all pass. The avatar never produces non-English output. Scenario order in the JSON is correct.

---

## Phase 6: User Story 4 — Extensibility Validation (Priority: P4)

**Goal**: A new scenario can be added to `src/server/bot/shared_persona.json` and be active in all activities without touching any `flow_config.json`. The process takes under 10 minutes.

**Independent Test**: Add a temporary test scenario (e.g., `name: "test_scenario"`, `instruction: "If the student says 'banana', reply with 'I heard banana!'"`). Restart the server. Start a session and say "banana." Confirm the avatar replies as instructed. Remove the test scenario and confirm the behavior is gone after restart.

- [ ] T016 [US4] Add a temporary `test_extensibility` scenario to `src/server/bot/shared_persona.json` following the pattern in [quickstart.md](quickstart.md); start a new session with `vocab-tutoring` **and** one other activity (e.g., `audiobook-avatar-demo` or any activity that has a `flow_config.json`) and confirm the behavior appears in both without any changes to either activity's `flow_config.json` — this satisfies US4 AC1 which requires two different activities
- [x] T017 [US4] Remove the `test_extensibility` scenario from `src/server/bot/shared_persona.json`; increment the `version` field to `"1.1.0"` (MINOR bump for the scenario additions since initial `1.0.0`)
- [x] T018 [US4] Review [quickstart.md](quickstart.md) against the actual implementation; update any instructions that no longer match (e.g., correct server restart procedure, actual file path)

**Checkpoint**: All four user stories pass. The extension workflow in quickstart.md accurately describes how to add a new scenario in one file.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Age-appropriateness review, final lint, and end-to-end session test.

- [ ] T019 Review all four scenario `instruction` fields in `src/server/bot/shared_persona.json` for age-appropriateness: language and tone should feel natural for ages 8–12 (not babyish, not adult). Rewrite any instruction text that feels off-register.
- [ ] T020 Review all four scenario `instruction` fields for consistency: phrasing style, length, and level of specificity should be uniform across scenarios so new entries can follow the same pattern
- [ ] T021 Run `pre-commit run --all-files` from the repo root; confirm Black, Flake8, ESLint, and Prettier all exit 0
- [ ] T022 Run a final end-to-end manual integration session using `vocab-tutoring` that exercises all four fallback scenarios in one session: go off-topic, go silent, say "I don't know," respond in Spanish. Confirm all behaviors match their acceptance scenarios from spec.md and that no premature state transitions occur.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately. **BLOCKS all user story phases.**
- **US1 (Phase 3)**: Requires Phase 2 complete. Can start as soon as loader injection passes lint.
- **US2 (Phase 4)**: Requires Phase 2 complete. Can start in parallel with US1 if two people available (different scenario entries in the JSON — no file conflict).
- **US3 (Phase 5)**: Requires Phase 2 complete. Note: T013 moves `english_only` to position 0; do this after US1 and US2 are merged to avoid array-order conflicts.
- **US4 (Phase 6)**: Requires all prior user story phases complete (validates the full system).
- **Polish (Phase 7)**: Requires Phase 6 complete.

### User Story Dependencies

- **US1 (P1)**: Only depends on Foundational — no other story dependency.
- **US2 (P2)**: Only depends on Foundational — no other story dependency.
- **US3 (P3)**: Only depends on Foundational — but T015 (reorder array) should run after US1/US2 are stable to avoid churn.
- **US4 (P4)**: Depends on US1 + US2 + US3 being complete (validates the whole system works together).

### Within Each User Story

- Add scenario to JSON → restart server → live test → tune text → confirm no premature transitions
- All adjustments stay in `src/server/bot/shared_persona.json` until satisfied, then move to next story

---

## Parallel Opportunities

```bash
# Foundational tasks T001 and T002 can run in parallel:
Task T001: "Create src/server/bot/shared_persona.json with english_only scenario"
Task T002: "Add _load_shared_persona() to src/server/bot/flows/loaders.py"
# T003 depends on T002 (wires the function in); T005a depends on T003

# US1 and US2 can run in parallel across two people:
Person A: T006, T007, T008  (off_topic_redirect scenario)
Person B: T009, T010, T011, T012  (silence + refusal scenarios)
# Both editing shared_persona.json — coordinate to avoid merge conflicts

# Polish T019 and T020 can be done simultaneously (read-only review, same file):
Task T019: "Age-appropriateness review of all instruction texts"
Task T020: "Consistency review of phrasing and style across scenarios"
# Note: not marked [P] because [P] is reserved for tasks on different files
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001–T005)
2. Complete Phase 3: US1 Off-Topic Redirect (T006–T008)
3. **STOP and VALIDATE**: A live session now has off-topic redirect working for all activities
4. This is the smallest independently useful fallback — deploy/demo if ready

### Incremental Delivery

1. Foundational → loader mechanism works, no scenarios yet
2. US1 → off-topic redirect live and tested
3. US2 → silence + refusal live and tested
4. US3 → English-only live and tested
5. US4 → extensibility confirmed
6. Polish → age-appropriate, lint-clean, end-to-end verified

---

## Notes

- All behavioral tuning happens in `src/server/bot/shared_persona.json` — no Python code changes after Phase 2
- No server restart needed after JSON changes — `_load_shared_persona()` reads from disk on each session start; just start a new session to pick up changes
- Check server logs for premature function calls during fallback states — this is the most likely integration issue
- T019 and T020 in the Polish phase cover the same file but from different review angles; they can be done by two people reading simultaneously (read-only review, no write conflict) but are not marked [P] since the task format reserves [P] for tasks on different files
- Scenario array order in `shared_persona.json` matters for LLM salience — `english_only` must be first; it is added in T001 (Foundational) and must remain at position 0 throughout all subsequent edits

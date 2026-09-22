# Tasks: Story Context Lookup for Vocab Tutoring

**Input**: Design documents from `specs/008-story-context-lookup/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in each description

---

## Phase 1: Setup

No project structure or dependency changes are needed. The handler follows existing patterns in the codebase; the book JSON already loads into `flow_manager.state["activity"]` at session start. Proceed directly to foundational work.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the shared `story_context_lookup_handler` and register it as a built-in. This must be complete before any user story can be wired into the flow config.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T001 Implement `story_context_lookup_handler(args, flow_manager)` in `src/server/bot/flows/handlers.py` — add after `get_user_handler`; supports `context_type` values `"book_summary"`, `"chapter_summary"`, `"vocab_word"`; reads from `flow_manager.state["activity"]["reading_context"]` and `flow_manager.state["activity"]["vocab"]`; falls back to `state["user"]["index"]` when `chapter_index` is not in args; returns `{"status": "success", "data": ...}` or `{"status": "error", "message": ...}` — no NodeConfig returned

- [x] T002 Register `story_context_lookup_handler` in `resolve_handler` in `src/server/bot/flows/loaders.py` — add `elif handler_string == "story_context_lookup_handler": return story_context_lookup_handler` alongside the existing built-in entries; add the import at the top of the import block

**Checkpoint**: Handler is callable from any flow node. Verify by reading `handlers.py` — `story_context_lookup_handler` exists and is imported in `loaders.py`.

---

## Phase 3: User Story 1 — Avatar fetches word details on demand (Priority: P1) 🎯 MVP

**Goal**: During the vocab teaching phase, the avatar calls `lookup_story_context` with `context_type="vocab_word"` and a specific word to retrieve that word's in-story sentence and context description — instead of receiving the full chapter reading context in bulk.

**Independent Test**: Start a vocab tutoring session; observe server logs show `lookup_story_context` function calls (not `get_reading_context`) when the avatar introduces a vocabulary word; confirm the avatar's explanation references the correct in-story sentence from the book JSON.

- [x] T003 [US1] Replace the `get_reading_context` function entry in the `vocab` node of `src/server/activities/vocab-tutoring/flow_config.json` with the `lookup_story_context` function schema — remove the old entry (`handler: get_activity_handler`, `variable_name: reading_context`) and insert the new schema with `context_type` enum, `chapter_index` integer, and optional `word` string parameters; `handler: story_context_lookup_handler`

- [x] T004 [US1] Update the `task_messages` TOOLS section of the `vocab` node in `src/server/activities/vocab-tutoring/flow_config.json` to instruct the LLM to call `lookup_story_context(context_type="vocab_word")` without a word argument to retrieve the available word list before teaching begins, then call again with `word=<the word>` to retrieve the in-story sentence and context for each word as it is introduced — replace the existing "A list of vocab words from the story has been provided" instruction which was incorrect (vocab data was never pre-injected)

**Checkpoint**: Vocab tutoring session completes the vocab stage (3 words taught) with `lookup_story_context` calls visible in server logs. Avatar uses correct in-story sentences for each word.

---

## Phase 4: User Story 2 — Avatar recalls chapter plot and book summary (Priority: P2)

**Goal**: During warm-up and review, the avatar calls `lookup_story_context` with `context_type="chapter_summary"` or `"book_summary"` to answer comprehension questions — rather than relying on a bulk `get_reading_context` call that returns the full reading context object.

**Independent Test**: During the warm-up stage, ask "what was this chapter about?" — observe a `lookup_story_context` call with `context_type="chapter_summary"` in server logs; confirm the avatar's summary matches the `chapter_summary` text in the book JSON for the current chapter.

- [x] T005 [P] [US2] Replace the `get_reading_context` function entry in the `warm_up` node of `src/server/activities/vocab-tutoring/flow_config.json` with the `lookup_story_context` function schema (same schema as T003)

- [x] T006 [P] [US2] Replace the `get_reading_context` function entry in the `review` node of `src/server/activities/vocab-tutoring/flow_config.json` with the `lookup_story_context` function schema (same schema as T003)

- [x] T007 [US2] Update the `task_messages` TOOLS section of the `warm_up` node in `src/server/activities/vocab-tutoring/flow_config.json` to instruct the LLM to call `lookup_story_context(context_type="chapter_summary", chapter_index=<N>)` after the child tells you their chapter, and `context_type="book_summary"` if a general book overview is needed; remove the reference to content being "automatically provided"

- [x] T008 [US2] Update the `task_messages` TOOLS section of the `review` node in `src/server/activities/vocab-tutoring/flow_config.json` to instruct the LLM to call `lookup_story_context(context_type="vocab_word", chapter_index=<N>, word=<word>)` only if it needs to re-check a word's sentence or context during review, rather than relying on a pre-loaded context dump

**Checkpoint**: Full session warm_up → vocab → review completes. Warm-up references the correct chapter summary via `lookup_story_context`. Review uses correct word details if re-lookup occurs.

---

## Phase 5: User Story 3 — Avatar discovers available words at vocab stage entry (Priority: P3)

**Goal**: When the vocab stage begins, the avatar calls `lookup_story_context(context_type="vocab_word")` without a `word` argument to get the list of available words organized by grade level — then selects a word to teach from the returned list, rather than having the list pre-loaded.

**Independent Test**: Start a session at the vocab stage; the first `lookup_story_context` call logged should have no `word` argument and `context_type="vocab_word"`; the avatar then selects a word from the returned `available_words` dict before making a second call with a specific word.

**Note**: The handler already supports this path (implemented in T001). The task here is verifying the task_message instruction from T004 correctly drives this two-step behavior (list → select → detail). If T004's wording is insufficient, update it.

- [x] T009 [US3] Verify the `vocab` node `task_messages` updated in T004 explicitly instructs the LLM to call `lookup_story_context(context_type="vocab_word", chapter_index=<N>)` with no `word` first to get the `available_words` list before selecting a word to teach; if the wording from T004 does not produce this two-call pattern in a live session, refine the instruction until it does — edit `src/server/activities/vocab-tutoring/flow_config.json` vocab node `task_messages`

**Checkpoint**: Server logs show the two-step pattern: first call without `word` (returns word list), second call with a specific `word` (returns word details), repeated for each word taught.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Confirm code quality, style, and integration correctness across all user stories.

- [x] T010 Run `pre-commit run --all-files` from the project root and fix any Black, Flake8, or formatting errors in the modified files (`handlers.py`, `loaders.py`)

- [x] T011 Verify the complete session integration path from quickstart.md: warm_up → vocab (3 words taught) → review → closing — confirm no errors from missing context and confirm graceful error handling when `chapter_index` is unavailable (avatar asks the child which chapter they are on)

- [x] T012 [P] Confirm other activities (basic-avatar-demo, audiobook-avatar-demo) are unaffected — run a short session in each and confirm no `story_context_lookup_handler` errors appear in server logs

- [x] T013 [P] Add Google-style docstring to `story_context_lookup_handler` in `src/server/bot/flows/handlers.py` if not already present from T001, following the format of `get_activity_handler` and `get_user_handler`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **User Story phases (Phase 3, 4, 5)**: All depend on Phase 2 completion (T001 + T002 must be done before any `flow_config.json` changes referencing `story_context_lookup_handler`)
- **US2 (Phase 4)**: Independent of US1 (Phase 3) — can proceed in parallel once Phase 2 is done
- **US3 (Phase 5)**: Depends on Phase 3 (T004 must exist before T009 can verify it)
- **Polish (Phase 6)**: Depends on all user story phases being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependency on US2 or US3
- **US2 (P2)**: Can start after Phase 2 — no dependency on US1 or US3
- **US3 (P3)**: Depends on US1 (Phase 3) — verifies the two-call pattern driven by T004

### Within Each Phase

- T001 before T002 (handler must exist before registration can reference it)
- T002 before T003/T005/T006 (handler must be registered before `flow_config.json` references it)
- T003 before T004 (function schema in node must exist before task_messages reference it)
- T005/T006 can run in parallel (different nodes in the same file)
- T007/T008 can run in parallel (different nodes in the same file)
- T004 before T009 (T009 verifies T004's output)

---

## Parallel Example: Phase 4 (US2)

```bash
# T005 and T006 edit different nodes — can be done together:
Task: "Replace get_reading_context in warm_up node of flow_config.json"
Task: "Replace get_reading_context in review node of flow_config.json"

# T007 and T008 update different task_messages — can follow in parallel:
Task: "Update warm_up task_messages for chapter_summary/book_summary lookup"
Task: "Update review task_messages for word detail re-lookup"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001, T002)
2. Complete Phase 3: US1 (T003, T004)
3. **STOP and VALIDATE**: Run a vocab tutoring session through the vocab stage — confirm `lookup_story_context` calls appear in logs, avatar uses correct sentences
4. Proceed to Phase 4 once US1 is validated

### Incremental Delivery

1. Phase 2 complete → handler is available for all activities (no behavior change yet)
2. Phase 3 (US1) complete → vocab word teaching now uses on-demand lookup
3. Phase 4 (US2) complete → warm_up and review also use targeted lookup; full session is clean
4. Phase 5 (US3) complete → word list discovery is verified; two-call pattern confirmed
5. Phase 6 (Polish) complete → ready for PR

---

## Notes

- [P] tasks = different files or different non-conflicting sections — safe to do together
- No automated test suite exists; all validation is manual integration testing against a live session
- `flow_config.json` edits are noted in the PR description per the constitution (non-trivial hand-edits)
- T009 is a verify-and-refine task — it may be a no-op if T004 produced the right instruction wording
- All 13 tasks across 3 modified files

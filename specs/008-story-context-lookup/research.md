# Research: Story Context Lookup for Vocab Tutoring

**Branch**: `008-story-context-lookup` | **Date**: 2026-08-21

## Findings

---

### Decision 1: New handler vs. modifying existing `get_activity_handler`

**Decision**: Add a new dedicated `story_context_lookup_handler` function in `bot/flows/handlers.py`, registered as a new built-in alongside `get_activity_handler`.

**Rationale**: `get_activity_handler` / `IndexableVariableHandler` is a general-purpose variable fetcher — it retrieves an entire indexed variable (e.g. all of `reading_context` for the current chapter, including book_summary and key_information). The new handler needs to return precise slices: a single chapter summary, a single word's sentence + context description, or just the list of available words. Overloading `get_activity_handler` with vocab-word-level granularity would require adding parameters it was not designed for and would make the general handler harder to maintain. A purpose-built handler is cleaner and follows the existing pattern (e.g. `get_activity_handler` vs. `get_user_handler` as separate handlers for different sources).

**Alternatives considered**:
- Extending `IndexableVariableHandler` with a `sub_key` parameter — rejected: would add conditional branching into a generic class and blur its responsibility.
- Registering as a custom activity handler (via `handlers.py` in the activity dir) — rejected: story context lookup is not activity-specific logic that needs activity-level overriding; it belongs in the shared built-in layer so other reading activities can reuse it.

---

### Decision 2: Storage — keep story data in `flow_manager.state["activity"]`; no external index

**Decision**: The book JSON (already loaded into `flow_manager.state["activity"]`) is the store. No vector embedding, no external database, no file re-reads during a session.

**Rationale**: The story content is well-structured JSON with clearly keyed sections (chapters list, vocab_words dict by grade). All retrieval needed for tutoring (book summary, chapter summary, word sentence/context) is O(1) key lookup — no fuzzy search is required. Vector search would add dependencies (an embedding model, a vector store) without any benefit for deterministic key-based access. The data is already resident in memory at session start.

**Alternatives considered**:
- Lightweight BM25 search over paragraph text — rejected: overcomplicated for a structure where every retrieval maps to a known key; also adds latency in a real-time voice pipeline.
- Re-reading the book JSON file per request — rejected: unnecessary I/O; the file is already loaded into state.

---

### Decision 3: Function interface — three context types via a single `lookup_story_context` function

**Decision**: The new flow function exposes a single `lookup_story_context` entrypoint with a `context_type` enum (`"book_summary"`, `"chapter_summary"`, `"vocab_word"`), a `chapter_index` integer, and an optional `word` string.

**Rationale**: A single function with typed dispatch is simpler for the LLM to reason about than three separate functions — fewer tools in the function list reduces the chance of the model calling the wrong one. The LLM already handles this pattern with `get_reading_context` (which takes `variable_name` and `current_index`). Keeping the count of exposed functions low is consistent with the existing flow design.

**Alternatives considered**:
- Three separate functions (`get_book_summary`, `get_chapter_summary`, `get_vocab_word`) — rejected: multiplies the function list without clear benefit; the LLM would need to learn which function to call for each context type rather than reasoning about context_type.
- Returning all context types at once (one big dump) — rejected: this is exactly the bulk-injection anti-pattern we are removing.

---

### Decision 4: Removal of `get_reading_context` + bulk injection from vocab and warm_up nodes

**Decision**: Replace the `get_reading_context` function (backed by `get_activity_handler`) with `lookup_story_context` in all nodes where it appears (warm_up, vocab, review). Update task_messages in each node to instruct the LLM to call the new function on demand rather than expecting content to be pre-loaded.

**Rationale**: The current `get_reading_context` function returns the full indexed `reading_context` object for the chapter — including the book summary, all key_information, and the full chapter summary — on every call. This is still a bulk retrieval: one call surfaces everything. Replacing it with targeted lookup and updating the task instructions to name which context_type to request for each situation reduces per-turn context to only what was needed.

There are no `pre_actions` doing bulk injection in warm_up or vocab nodes (contrary to the initial hypothesis from the prior conversation — inspection confirms pre_actions in those nodes are only `tts_say`, not variable injection). The bulk comes from the function call returning the full `reading_context` object.

**Alternatives considered**:
- Keeping `get_reading_context` and adding `lookup_story_context` alongside it — rejected: the LLM would have two overlapping tools and might continue using the bulk one; cleaner to replace.
- Injecting only a "word list" at node entry (pre_action) then using on-demand lookup for details — a reasonable middle ground, but it still puts data into the context window proactively. On-demand only is cleaner and is achievable because the LLM already knows to call a function to get context (as evidenced by the warm_up task_message).

---

### Decision 5: Vocab data access — expose through `lookup_story_context` using the `vocab` key in `flow_manager.state["activity"]`

**Decision**: The handler reads `flow_manager.state["activity"]["vocab"]` (which is loaded from the book JSON alongside `reading_context`) to serve vocabulary word lookups.

**Rationale**: The book JSON file has a top-level `vocab` key containing per-chapter word lists, separate from `reading_context`. Both are loaded into `flow_manager.state["activity"]` when `load_activity_variables` runs. The current vocab node task_message says "A list of vocab words from the story has been provided" — this is aspirational/incorrect in the current implementation; `get_reading_context` only returns reading context, not vocab. The new handler fixes this gap by explicitly supporting vocab word retrieval.

**Alternatives considered**: None — the data is already there; this is purely a matter of the handler knowing to read the `vocab` key in addition to `reading_context`.

---

### Decision 6: Handler return signature — dict only (no NodeConfig), matching `get_activity_handler` pattern

**Decision**: `story_context_lookup_handler(args, flow_manager) -> Dict[str, Any]` — returns a result dict and no NodeConfig.

**Rationale**: Handlers that return only a dict are "retrieval" functions that don't cause node transitions; pipecat-flows sends the result back to the LLM as the function call response, and the LLM continues in the current node. This is the same pattern as `get_activity_handler` and `get_user_handler`. The handler does not own any transition logic; `general_handler` handles all node transitions.

---

## Summary of resolved questions

| Question | Answer |
|---|---|
| Where does the story data live? | `flow_manager.state["activity"]` — in-memory, loaded once at session start |
| Do we need file I/O or a vector store? | No — key-based dict lookup over existing in-memory state |
| Shared built-in or activity-specific? | Shared built-in in `bot/flows/handlers.py` |
| How many LLM-callable functions? | One (`lookup_story_context`) with a `context_type` discriminator |
| Does it trigger node transitions? | No — returns a dict only, same as `get_activity_handler` |
| What happens to `get_reading_context`? | Removed from all nodes and replaced with `lookup_story_context` |
| What about the vocab data gap? | Fixed: `lookup_story_context` reads both `reading_context` and `vocab` from state |

# Implementation Plan: Story Context Lookup for Vocab Tutoring

**Branch**: `008-story-context-lookup` | **Date**: 2026-08-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/008-story-context-lookup/spec.md`

## Summary

Replace the bulk `get_reading_context` function (which returns the full chapter reading context on every call) with a targeted `lookup_story_context` function that the avatar calls during conversation to retrieve exactly what it needs — book summary, chapter summary, or a specific vocabulary word — from story data already resident in session state. No new storage layer is required; the book JSON is already loaded into `flow_manager.state["activity"]` at session start.

## Technical Context

**Language/Version**: Python 3.11 (server), JSON (activity config)
**Primary Dependencies**: `pipecat-ai-flows` (FlowManager, FlowArgs), `pipecat-ai` (LLMMessagesAppendFrame)
**Storage**: In-memory session state (`flow_manager.state["activity"]`) — no change
**Testing**: Manual integration testing against a live WebRTC session (no automated test suite)
**Target Platform**: Server-side FastAPI process (Linux / macOS)
**Project Type**: Real-time voice pipeline server component
**Performance Goals**: Handler executes in < 1 ms (pure dict lookup); no latency budget impact
**Constraints**: Must not add any new external dependencies; no file I/O during session
**Scale/Scope**: One activity (`vocab-tutoring`); handler is shared infrastructure

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Code Quality — Black / Flake8 / 120 char limit | PASS | New handler follows same structure as existing handlers; must run `pre-commit` |
| I. Code Quality — Google-style docstrings | PASS | Required on the new handler function and any new methods |
| I. Code Quality — Single clear responsibility | PASS | Handler is purely a retrieval function; no transition logic mixed in |
| II. Testing — Manual integration test required | PASS | Full session (warm_up → vocab → review → closing) must be run before merge |
| II. Testing — Activity configs validated by live flow | PASS | `flow_config.json` changes must be exercised in a live session |
| III. UX Consistency — No new user-facing states | PASS | Change is invisible to the child; avatar behavior is improved, not different |
| IV. Performance — No latency regression | PASS | Dict lookup; negligible cost; tool call round-trip already exists in current flow |
| Dev Workflow — No secrets / session data committed | PASS | No new env vars or session paths touched |
| Dev Workflow — flow_config.json editing | NOTE | Changes to `flow_config.json` are non-trivial; must be noted in PR description per constitution |

*Post-design re-check*: No violations. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/008-story-context-lookup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code

```text
src/server/
├── bot/
│   └── flows/
│       ├── handlers.py          # MODIFIED: add story_context_lookup_handler
│       └── loaders.py           # MODIFIED: register new handler in resolve_handler
└── activities/
    └── vocab-tutoring/
        └── flow_config.json     # MODIFIED: replace get_reading_context with lookup_story_context
                                 #           in warm_up, vocab, review nodes; update task_messages
```

## Implementation Detail

### 1. `bot/flows/handlers.py` — new `story_context_lookup_handler`

Add after the existing `get_user_handler` function:

```python
async def story_context_lookup_handler(
    args: Union[FlowArgs, dict], flow_manager: FlowManager
) -> Dict[str, Any]:
    """Retrieve a targeted slice of story content from session state.

    Args:
        args: Must contain 'context_type' ("book_summary", "chapter_summary", "vocab_word").
              For chapter_summary and vocab_word: 'chapter_index' (1-based int) is required
              unless already stored in user state. For vocab_word: 'word' (str) is optional;
              if omitted, returns the available word list for the chapter.
        flow_manager: Active FlowManager with story data in state["activity"].

    Returns:
        Dict with 'status' ("success"/"error") and 'data' or 'message'.
    """
    context_type = args.get("context_type")
    chapter_index = args.get("chapter_index")
    word = args.get("word")

    activity = flow_manager.state.get("activity", {})

    # Resolve chapter index: explicit arg takes priority, then user state
    def _resolve_chapter(data_section: dict) -> Optional[int]:
        idx = chapter_index
        if idx is None:
            idx = flow_manager.state.get("user", {}).get("index")
        if idx is None:
            return None
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return None
        items = data_section.get(data_section.get("indexable_by", ""), [])
        if not 1 <= idx <= len(items):
            return None  # caller checks separately
        return idx

    if context_type == "book_summary":
        reading_ctx = activity.get("reading_context")
        if not reading_ctx:
            return {"status": "error", "message": "Story content is not loaded. The session may not have a book configured."}
        return {"status": "success", "data": reading_ctx.get("book_summary", "")}

    if context_type == "chapter_summary":
        reading_ctx = activity.get("reading_context")
        if not reading_ctx:
            return {"status": "error", "message": "Story content is not loaded. The session may not have a book configured."}
        chapters = reading_ctx.get("chapters", [])
        idx = _resolve_chapter(reading_ctx)
        if idx is None:
            if chapter_index is not None:
                return {"status": "error", "message": f"chapter {chapter_index} is out of range. Valid chapters: 1–{len(chapters)}."}
            return {"status": "error", "message": "chapter_index is required for chapter_summary. Ask the child which chapter they are on."}
        return {"status": "success", "data": chapters[idx - 1]["chapter_summary"]}

    if context_type == "vocab_word":
        vocab_ctx = activity.get("vocab")
        if not vocab_ctx:
            return {"status": "error", "message": "Vocabulary data is not loaded. The session may not have a book configured."}
        chapters = vocab_ctx.get("chapters", [])
        reading_ctx = activity.get("reading_context", {})
        idx = _resolve_chapter(reading_ctx)
        if idx is None:
            if chapter_index is not None:
                return {"status": "error", "message": f"chapter {chapter_index} is out of range. Valid chapters: 1–{len(chapters)}."}
            return {"status": "error", "message": "chapter_index is required for vocab_word. Ask the child which chapter they are on."}
        vocab_words = chapters[idx - 1]["vocab_words"]
        if not word:
            available = {grade: [w["word"] for w in words] for grade, words in vocab_words.items()}
            return {"status": "success", "data": {"available_words": available}}
        for grade_words in vocab_words.values():
            for entry in grade_words:
                if entry["word"] == word:
                    return {"status": "success", "data": {"word": entry["word"], "sentence": entry["sentence"], "context_description": entry["context_description"]}}
        all_words = [w["word"] for grade_words in vocab_words.values() for w in grade_words]
        return {"status": "error", "message": f"'{word}' not found in chapter {idx}. Available words: {all_words}."}

    return {"status": "error", "message": f"Unknown context_type '{context_type}'. Valid types: book_summary, chapter_summary, vocab_word."}
```

### 2. `bot/flows/loaders.py` — register new handler

In `resolve_handler`, add alongside the existing entries:

```python
elif handler_string == "story_context_lookup_handler":
    return story_context_lookup_handler
```

Add the import at the top of the import block:
```python
from .handlers import (
    get_activity_handler,
    general_handler,
    get_user_handler,
    get_variable_action_handler,
    story_context_lookup_handler,   # new
)
```

### 3. `activities/vocab-tutoring/flow_config.json` — replace function + update task_messages

**In each of `warm_up`, `vocab`, and `review` nodes**:

Replace the existing `get_reading_context` function entry with:

```json
{
  "type": "function",
  "function": {
    "name": "lookup_story_context",
    "description": "Retrieve a specific piece of story content: 'book_summary' for the overall plot, 'chapter_summary' for the current chapter's events, or 'vocab_word' for a specific word's sentence and context (or the list of available words for the chapter if word is omitted).",
    "parameters": {
      "type": "object",
      "properties": {
        "context_type": {
          "type": "string",
          "enum": ["book_summary", "chapter_summary", "vocab_word"],
          "description": "What kind of story content to retrieve."
        },
        "chapter_index": {
          "type": "integer",
          "description": "1-based chapter number. Required for chapter_summary and vocab_word unless already established in the session."
        },
        "word": {
          "type": "string",
          "description": "The vocabulary word to look up. Omit to get the full list of available words for the chapter."
        }
      },
      "required": ["context_type"]
    },
    "handler": "story_context_lookup_handler"
  }
}
```

**Updated task_messages** (replace the TOOLS section of each node):

*warm_up node*:
```
TOOLS:
Use lookup_story_context() to get story content when you need it.
- To confirm the book title and author: call with context_type="book_summary".
- To give a chapter summary after the child tells you their chapter: call with context_type="chapter_summary" and chapter_index=<their answer>.
- If the chapter is already known (see Key Information), use context_type="chapter_summary" with the known chapter_index directly.
Do not call lookup_story_context proactively before you need the information.
```

*vocab node*:
```
TOOLS:
Use lookup_story_context() to retrieve story content on demand:
- To get the list of words to teach: call with context_type="vocab_word" and the known chapter_index (no word argument).
- To get a specific word's in-story sentence and context: call with context_type="vocab_word", chapter_index, and word=<the word>.
Do not prefetch all words at once. Retrieve each word's details when you are about to teach that word.
```

*review node*:
```
TOOLS:
Use lookup_story_context() if you need to re-check a word's sentence or context during review:
- Call with context_type="vocab_word", the chapter_index, and word=<the word being reviewed>.
Only call this if you do not already have the information from earlier in the session.
```

## Verification checklist (pre-merge)

- [ ] `pre-commit run --all-files` exits 0
- [ ] Full vocab tutoring session runs: warm_up → vocab (3 words taught) → review → closing
- [ ] Server logs show `lookup_story_context` calls, not `get_reading_context` calls
- [ ] Avatar correctly references in-story sentences and chapter summaries via on-demand lookup
- [ ] Session ends cleanly with no errors from missing context
- [ ] Other activities (basic-avatar-demo, audiobook) unaffected

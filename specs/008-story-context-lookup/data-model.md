# Data Model: Story Context Lookup

**Branch**: `008-story-context-lookup` | **Date**: 2026-08-21

## Entities

### LookupRequest (input to `lookup_story_context`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `context_type` | `"book_summary" \| "chapter_summary" \| "vocab_word"` | Yes | Discriminates what to return |
| `chapter_index` | `int` (1-based) | Conditional | Required for `chapter_summary` and `vocab_word` |
| `word` | `str` | Optional | If omitted for `vocab_word`, returns the available word list |

**Validation rules**:
- `chapter_index` must be ≥ 1 and ≤ number of chapters in the book; any other value yields an error response
- `word` is case-sensitive and must match a word in the chapter's `vocab_words` dict across grade levels
- If `context_type` is `"book_summary"`, `chapter_index` and `word` are ignored

---

### LookupResponse (return from `lookup_story_context`)

Success:
```
{"status": "success", "data": <payload>}
```

Error:
```
{"status": "error", "message": "<descriptive message the LLM can act on>"}
```

**Payload shapes by context_type**:

| `context_type` | Success payload shape |
|---|---|
| `"book_summary"` | `str` — the book-level summary text |
| `"chapter_summary"` | `str` — the summary text for the requested chapter |
| `"vocab_word"` (with `word`) | `{"word": str, "sentence": str, "context_description": str}` |
| `"vocab_word"` (without `word`) | `{"available_words": {"grade_4": [str, ...], "grade_5": [...], "grade_6": [...]}}` |

---

### ActivityState (existing, in `flow_manager.state["activity"]`)

The handler reads two existing top-level keys — no changes to their structure.

```
state["activity"]["reading_context"]
  key_information: {name, author, ...}
  book_summary: str
  indexable_by: "chapters"
  chapters: [
    {chapter_summary: str, image: str},
    ...
  ]

state["activity"]["vocab"]
  indexable_by: "chapters"
  chapters: [
    {
      vocab_words: {
        grade_4: [{word, sentence, context_description}, ...],
        grade_5: [...],
        grade_6: [...]
      }
    },
    ...
  ]
```

Both keys are populated once by `load_activity_variables` at session start and are read-only throughout the session by the lookup handler.

---

## State transitions

The lookup handler has no side effects on flow state. It does not:
- Modify `flow_manager.state`
- Update the chapter index
- Trigger node transitions

The chapter index is set and managed separately by the existing `general_handler` and `IndexableVariableHandler` flows (as today). The lookup handler reads `state["user"]["index"]` as a fallback when `chapter_index` is not passed explicitly.

---

## Error catalogue

| Error condition | Message pattern |
|---|---|
| `chapter_index` missing and not in user state | `"chapter_index is required for {context_type}. Ask the child which chapter they are on."` |
| `chapter_index` out of range | `"chapter {n} is out of range. Valid chapters: 1–{max}."` |
| `word` not found in chapter | `"'{word}' not found in chapter {n}. Available words: {list}."` |
| `reading_context` not in activity state | `"Story content is not loaded. The session may not have a book configured."` |
| `vocab` not in activity state | `"Vocabulary data is not loaded. The session may not have a book configured."` |
| Unknown `context_type` | `"Unknown context_type '{value}'. Valid types: book_summary, chapter_summary, vocab_word."` |

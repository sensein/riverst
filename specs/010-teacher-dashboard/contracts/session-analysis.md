# Contract: Post-Session Analysis

This is the internal contract for `src/server/dashboard/analysis.py`. It covers the inputs, the two structured LLM calls and their JSON schemas, and the validation rules. See research R1, R5 and R6.

## Trigger

- **When**: `on_client_disconnected` (`bot/core/event_manager.py`), after the final `flow_state.json` snapshot.
- **Condition**: `config.json` has a `student_id`, and the activity is a vocabulary activity.
- **What runs**: `asyncio.create_task(analyze_session(session_dir_id))`.
- **Also runs**: on server startup, for every `session_record` that is `pending` or `running` (crash recovery); and from teacher Retry.

## Inputs

| Input | Source |
|---|---|
| Words + disposition + review | `flow_state.json`, using `user.vocab_words_known`, `vocab_words_taught`, `vocab_words_taught+mastered` and `vocab_words_taught+not_mastered`, plus `vocab_override` |
| Last node | `flow_state.json` `current_node` |
| Transcript | `transcript.json` (`[{index, timestamp, role, content}]`) |
| Grade bands | The book resource file (`activity_variables_path`), chapter `index`, and the `vocab.grade_4/5/6` lists |

**Missing inputs**:
- If `flow_state.json` or `transcript.json` is missing, or the transcript has no user turns: `analysis_status = failed`, and the dashboard shows "detailed results not available".
- If the flow state has no taught words and no known words (for example, the student left during warm-up): the outcomes are empty, `completion = ended_early`, and the analysis is `ready`. The summary notes that the session ended before any words.

## Call 1 — Step outcomes

The prompt gives the four step definitions from the spec (simple definition / story context / personal connection / own sentence), the list of taught words in order, and the transcript.

Instructions:
- Classify each step for each taught word.
- `completed` means the student made a relevant, correct attempt.
- `attempted_not_completed` means KIVA asked but the student's answer was missing, off-topic or incorrect after KIVA's help.
- `not_reached` means KIVA never asked.
- For `definition`, `completed` means KIVA delivered the definition and the student stayed engaged.

Response schema (strict):

```json
{
  "type": "object",
  "required": ["words"],
  "additionalProperties": false,
  "properties": {
    "words": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["word", "definition", "story_context", "personal_connection", "own_sentence"],
        "additionalProperties": false,
        "properties": {
          "word": { "type": "string" },
          "definition":          { "enum": ["completed", "attempted_not_completed", "not_reached"] },
          "story_context":       { "enum": ["completed", "attempted_not_completed", "not_reached"] },
          "personal_connection": { "enum": ["completed", "attempted_not_completed", "not_reached"] },
          "own_sentence":        { "enum": ["completed", "attempted_not_completed", "not_reached"] }
        }
      }
    }
  }
}
```

Validation:
- The set of returned words must equal the set of taught words, compared case-insensitively. If not, retry once.
- Disposition and review always come from the flow state, never from this call.

## Call 2 — Session summary

**Inputs**: merged outcomes, completion, duration and transcript.

**Instructions**:
- Write for a teacher, at most 120 words.
- Cover engagement, which words went well and which were hard, one notable moment, and 1–2 suggestions.
- **Never quote the student**, and include no personal details the student shared. Describe them generally instead, for example "connected the word to a family trip".

Response schema (strict):

```json
{
  "type": "object",
  "required": ["text", "engagement", "words_went_well", "words_hard", "notable_moments", "suggestions"],
  "additionalProperties": false,
  "properties": {
    "text": { "type": "string" },
    "engagement": { "enum": ["high", "mixed", "low"] },
    "words_went_well": { "type": "array", "items": { "type": "string" } },
    "words_hard": { "type": "array", "items": { "type": "string" } },
    "notable_moments": { "type": "array", "items": { "type": "string" }, "maxItems": 2 },
    "suggestions": { "type": "array", "items": { "type": "string" }, "minItems": 1, "maxItems": 2 }
  }
}
```

Validation (deterministic, R6). If it fails, regenerate once with the violations listed; after that, `summary_status = failed`.

1. `text` is at most 140 words (some tolerance over 120).
2. Every word in `words_went_well` and `words_hard` is a taught word.
3. No word in `words_went_well` has `review = not_mastered`.
4. No word in `words_hard` has `review = mastered` and also has all four steps `completed`.
5. No run of 6 or more consecutive tokens from any `role = user` transcript turn appears in `text`, `notable_moments` or `suggestions`. Matching is case-insensitive and ignores punctuation.

## Student summary (after each `ready` session)

**Inputs**: aggregates only: counts, per-step failure rates, the last 5 sessions' mastery ratios, the reading-level trend, and the still-learning words. **The transcript is never an input.**

**Output schema**: `{text, strengths, difficulties, suggested_focus}`. `text` is 2–4 sentences.

## Outputs

- **SQLite**: a transaction that replaces `word_outcome` rows for the session and updates `session_record` (status, completion, duration, summary fields).
- **Session folder**: `learning_report.json`, the same content, written atomically.

**Configuration**:
- `DASHBOARD_ANALYSIS_MODEL` (default `gpt-4.1`)
- `OPENAI_API_KEY` (existing)
- `DASHBOARD_DB_PATH` (default `src/server/data/dashboard.db`, which is `/app/data/dashboard.db` in Docker)

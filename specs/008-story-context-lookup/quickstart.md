# Quickstart: Story Context Lookup

**Branch**: `008-story-context-lookup` | **Date**: 2026-08-21

## What this feature adds

A targeted story context lookup function (`lookup_story_context`) that the avatar calls during conversation to retrieve specific pieces of the book — book summary, a chapter summary, or a vocabulary word's details — instead of receiving the full chapter content in bulk.

## Files changed

| File | Change |
|---|---|
| `src/server/bot/flows/handlers.py` | Add `story_context_lookup_handler` function |
| `src/server/bot/flows/loaders.py` | Register `"story_context_lookup_handler"` in `resolve_handler` |
| `src/server/activities/vocab-tutoring/flow_config.json` | Replace `get_reading_context` with `lookup_story_context` in warm_up, vocab, and review nodes; update task_messages |

## How to test locally

1. Start the server:
   ```
   cd src/server && conda activate riverst && python main.py
   ```
2. Start the client:
   ```
   cd src/client/react && npm run dev
   ```
3. Open the app and start a **Vocab Tutoring** session with any book.
4. Observe the server logs — you should see `lookup_story_context` function calls logged (via the `@function_call_debug` decorator) instead of `get_reading_context` calls.
5. Run through the full session flow:
   - Warm-up: confirm the avatar mentions the correct chapter summary after asking which chapter you are on.
   - Vocab: confirm the avatar teaches words with the correct in-story sentences.
   - Review: confirm the recap uses the correct word details.
6. Confirm no full chapter dump appears in the LLM system messages (check server debug logs).

## Regression check

Run the existing basic-avatar-demo and audiobook activities to confirm they are unaffected — `story_context_lookup_handler` is only registered in vocab-tutoring's `flow_config.json`.

## Pre-commit

```
pre-commit run --all-files
```

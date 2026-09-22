# Quickstart: Avatar Edge Case Fallback Handling

**Branch**: `007-avatar-fallback-handling` | **Date**: 2026-08-09

## What this feature does

Adds a shared behavioral fallback layer to all avatar sessions. When a student goes off-topic, refuses to participate, or responds in a non-English language, the avatar follows a consistent, extensible set of recovery strategies — without any changes to individual activity files.

## How it works

1. `src/server/bot/shared_persona.json` — new file defining all fallback scenarios.
2. `src/server/bot/flows/loaders.py` — modified to inject the shared persona into every node's `role_messages` at load time.
3. No changes to any activity's `flow_config.json`.

## Adding a new fallback scenario

Open `src/server/bot/shared_persona.json` and append a new object to the `scenarios` array:

```json
{
  "name": "my_new_scenario",
  "trigger": "Description of when this fires",
  "instruction": "What the avatar should do when this happens."
}
```

Increment the `version` field (MINOR bump if adding, PATCH if editing an existing scenario). The new behavior takes effect in the next session — no server restart needed.

## Testing a fallback

1. Start a session with any activity.
2. Trigger the scenario manually:
   - **Off-topic**: Say something completely unrelated mid-lesson.
   - **Refusal**: Say "I don't know" or "I don't want to."
   - **Non-English**: Respond in Spanish or French.
3. Confirm the avatar behaves per the scenario's `instruction`.
4. Confirm no state-transition function (e.g., `check_vocab_progress`) is called during the fallback.
5. Confirm the avatar returns to the correct task step within 1–2 turns.

## Files changed

| File | Change |
|------|--------|
| `src/server/bot/shared_persona.json` | New — defines all fallback scenarios |
| `src/server/bot/flows/loaders.py` | Modified — injects shared persona into node `role_messages` |

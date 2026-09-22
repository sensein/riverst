# Research: Avatar Edge Case Fallback Handling

**Branch**: `007-avatar-fallback-handling` | **Date**: 2026-08-09

## Decision Log

### Decision 1: Where to inject fallback instructions

**Decision**: Use a shared JSON configuration file (`src/server/bot/shared_persona.json`) merged into every node's `role_messages` at load time in `loaders.py`.

**Rationale**: The flow loader (`src/server/bot/flows/loaders.py`) already has a preprocessing hook (`preprocess_flow_config`) that fires before the validated config is returned. This is the right injection point: it keeps the change centralized in one place, requires no edits to any `flow_config.json`, and is transparent to the Flow Builder. A shared JSON file alongside the loader is easy to read, edit, and version.

**Alternatives considered**:
- *Embed fallback in each activity's `role_messages` by hand*: Requires editing every activity's `flow_config.json` and re-editing whenever the fallback rules change. Not extensible.
- *A global `fallback_config` key in `flow_config.json`*: Requires every activity file to opt in, defeating the "one place" goal unless enforced by a schema validator.
- *A database or runtime config*: Unnecessary overhead for what is essentially a static set of behavioral instructions.

**Affected files**: `src/server/bot/flows/loaders.py`, `src/server/bot/shared_persona.json` (new)

---

### Decision 2: Format of the shared persona/fallback config

**Decision**: A single JSON file with a top-level `global_role_instructions` string (a multi-section system prompt block) plus a `scenarios` array of structured entries (each with a `name`, `trigger_description`, and `instruction` field).

**Rationale**: The `role_messages` in `flow_config.json` already use plain system-prompt text. A single injected text block is the simplest format that the LLM can act on without any schema change. The `scenarios` array provides the extensibility layer: new edge cases can be added as new entries without changing the format, and a developer can immediately read what each scenario covers.

**Alternatives considered**:
- *Pure flat text*: Readable but no structure for tooling to validate or enumerate scenarios.
- *Separate files per scenario*: More files to manage; no clear benefit at this scale.

---

### Decision 3: How fallback instructions interact with node task_messages

**Decision**: The merged `role_messages` inject fallback instructions as a persistent behavioral layer. Task-specific instructions in `task_messages` are not touched. The fallback instructions explicitly state they apply "only when the current task flow has broken down" — the LLM decides contextually when to apply them.

**Rationale**: The pipecat-flows library keeps `role_messages` (the persona) and `task_messages` (the node task) as separate system message slots. Injecting into `role_messages` means the fallback applies at the same level as the avatar's core persona — always present but not overriding node-specific task steps.

**Key constraint confirmed**: `functions` (including state-transition tools like `check_vocab_progress`) must not be called while the student is in a fallback state. This is enforced via explicit instruction in the shared persona text rather than code-level gating, since the LLM already controls when to call functions.

---

### Decision 4: English-only enforcement mechanism

**Decision**: The English-only rule is a hard instruction in the shared `role_messages` — no separate code check. It is placed prominently (first item) so it takes precedence in the LLM's attention.

**Rationale**: OpenAI's TTS models do handle multilingual input/output naturally, so the LLM could respond in another language if not explicitly told not to. An explicit, high-salience instruction in the role message is the correct layer for this — language enforcement is a behavioral rule, not a content filter requiring a separate classifier.

**Limitation**: This is a best-effort enforcement via prompt. Extremely short or ambiguous inputs may still occasionally produce non-English words. If stricter enforcement is needed in the future, a post-processing filter can be added at the TTS stage.

---

### Decision 5: Silence detection scope

**Decision**: Elongated silence is handled within this fallback layer (not solely at the transport layer). The shared persona instructs the avatar to issue one warm wait-prompt ("Take your time — I'm here whenever you're ready") before escalating silence to the refusal handler. The pipeline's VAD sets the actual audio pause window.

**Rationale**: Treating silence purely as a refusal risks pressuring students who are simply thinking. Giving one non-pressuring prompt respects natural think time for ages 8–12, who may process questions more slowly. This is a behavioral instruction, not an audio-level mechanism — the transport layer still handles raw silence detection.

**Clarification**: Sessions are monitored by an adult supervisor, so safety-critical silence scenarios (e.g., distress) are handled through human oversight. The avatar's silence handler covers only participation-related pauses.

---

### Decision 6: Age range and tone

**Decision**: Uniform tone targeting ages 8–12. No per-activity tone profile at this stage.

**Rationale**: The platform's current activities are all in the 8–12 range. A single calibrated tone simplifies the shared persona and avoids conditional logic. If younger or older cohorts are added in the future, a `tone_profile` field can be added to the `SharedPersonaConfig` schema.

---

### Decision 7: Repeat-refusal handling and session close

**Decision**: The fallback instructions define a graduated refusal ladder: hint → simplify → acknowledge and move on → graceful session close after sustained non-participation. The session-close step maps to the existing `closing` node (if present) or the `end` node — the instruction tells the LLM to move to whichever wrap-up node is available.

**Rationale**: Pipecat flows already handle session termination via `post_actions: [{"type": "end_conversation"}]`. The fallback does not need to create new nodes for session close; it tells the LLM to call the appropriate transition function when the session should end due to sustained non-participation.

---

## Integration Points Confirmed

| Component | Role | Change Needed |
|-----------|------|---------------|
| `src/server/bot/flows/loaders.py` | Loads and validates flow configs | Inject shared persona into `role_messages` of every node before validation |
| `src/server/bot/shared_persona.json` | Shared fallback behavioral instructions | New file |
| Activity `flow_config.json` files | Per-activity conversation flows | No changes needed |
| `src/server/bot/flows/models/node_models.py` | Pydantic models for nodes | No changes needed |
| Flow Builder (`src/flow-builder/`) | Visual config editor | No changes needed; shared persona is loader-level |

## Open Questions (resolved)

- **Q: Does `role_messages` appear on every node or only the initial node?**
  A: Only required on the initial node per the validator (`NodesConfig.validate_node_config`). However, pipecat-flows passes role messages per node; the loader must inject the shared persona into every node's `role_messages` (creating the field if absent) so the LLM has the context regardless of which node is active.

- **Q: Does the preprocessing hook (`preprocess_flow_config`) run before or after Pydantic validation?**
  A: Before — the loader calls `preprocess_fn(flow_config_data, activity_variables)` on the raw dict before `FlowConfigurationFile(**flow_config_data)`. Injection must happen in the preprocessing stage.

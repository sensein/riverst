# Data Model: Avatar Edge Case Fallback Handling

**Branch**: `007-avatar-fallback-handling` | **Date**: 2026-08-09

## Entities

### SharedPersonaConfig (new file: `src/server/bot/shared_persona.json`)

The top-level structure of the shared persona configuration file. This is the single source of truth for all global fallback behaviors.

```
SharedPersonaConfig
├── version          string     Semantic version (e.g. "1.0.0") — increment when scenarios change
├── description      string     Human-readable description of this file's purpose
└── scenarios        Scenario[] Ordered list of fallback scenario definitions
```

### Scenario

Each entry describes one edge case the avatar may encounter and how to handle it.

```
Scenario
├── name             string     Unique slug (e.g. "off_topic_redirect", "refusal_handling")
├── trigger          string     Plain-English description of when this scenario activates
└── instruction      string     The system-prompt instruction text for this scenario
```

**Ordering note**: Scenarios are listed in priority order. The merged role message preserves this order so more critical instructions (e.g., safety, English-only) appear before less critical ones.

---

## Merged Role Message Shape

After injection by the loader, every node's `role_messages` will contain:

```
role_messages[0]: { role: "system", content: <original_role_message_text> }  # if present
role_messages[-1]: { role: "system", content: <injected_shared_persona_block> }  # appended
```

The injected block is a formatted string assembled from the `SharedPersonaConfig.scenarios` list, with a header that clearly marks it as the shared behavioral layer.

---

## Validation Rules

- `version` MUST follow semantic versioning (MAJOR.MINOR.PATCH).
- `name` MUST be unique across all scenarios in the file.
- `instruction` MUST be non-empty and written in second-person imperative directed at the avatar ("Always respond in English…"), not at the developer.
- A scenario MUST NOT reference any activity-specific node names or function names; it MUST use generic language ("the current task step", "the appropriate transition function").

---

## State Transitions (unchanged)

The fallback system does not introduce new flow states or modify the existing state machine. The `state_config` in each `flow_config.json` is untouched. All existing node transitions remain the sole mechanism for advancing the conversation pipeline.

---

## Example `shared_persona.json` Structure

```json
{
  "version": "1.0.0",
  "description": "Shared behavioral guidelines applied to all avatar sessions.",
  "scenarios": [
    {
      "name": "english_only",
      "trigger": "Student responds in a non-English language",
      "instruction": "Always respond exclusively in English, regardless of the language the student uses. Do not repeat, translate, or complete any non-English words or phrases. You may briefly acknowledge that you will continue in English, but do so warmly and without making the student feel corrected."
    },
    {
      "name": "off_topic_redirect",
      "trigger": "Student says something significantly unrelated to the current task",
      "instruction": "If the student says something off-topic, briefly acknowledge their comment in one short sentence, then redirect back to the exact task step you were on. Do not call any transition function while the student is off-topic. If the student has gone off-topic two or more consecutive times, use a warmer and more explicit redirect ('Let's save that for after our lesson — right now I need your help with…'). If the student's off-topic comment is emotionally charged, show brief empathy before returning to the lesson."
    },
    {
      "name": "silence_handling",
      "trigger": "Student goes silent without responding after being asked a question",
      "instruction": "If the student does not respond after being asked a question, give one warm, non-pressuring wait prompt such as 'Take your time — I'm here whenever you're ready' and then wait again. Do not repeat the question yet. Only after the student remains silent following that prompt should you treat it as a soft refusal and move to a hint or a simpler version of the question."
    },
    {
      "name": "refusal_handling",
      "trigger": "Student says 'I don't know', 'I don't want to', or signals disengagement",
      "instruction": "If the student refuses to answer or says they don't know, never repeat the exact same question verbatim. Instead: first offer a hint or a simpler version of the question. If they still refuse, acknowledge their feeling ('That's okay, let's try a different way') and try a different approach. Do not call any transition function until the student has re-engaged. If the student refuses multiple consecutive tasks, acknowledge the situation empathetically and move toward wrapping up the session gracefully."
    }
  ]
}
```

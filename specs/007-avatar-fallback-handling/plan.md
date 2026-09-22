# Implementation Plan: Avatar Edge Case Fallback Handling

**Branch**: `007-avatar-fallback-handling` | **Date**: 2026-08-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/007-avatar-fallback-handling/spec.md`

## Summary

Add a shared behavioral fallback layer to all Riverst avatar sessions. A new `src/server/bot/shared_persona.json` file defines edge case handling scenarios (off-topic redirect, refusal/disengagement, English-only enforcement). The flow loader (`loaders.py`) injects this shared persona into every node's `role_messages` at load time — no changes to any activity's `flow_config.json`. New scenarios can be added by editing one file.

## Technical Context

**Language/Version**: Python 3.11 (backend); no frontend changes  
**Primary Dependencies**: `pipecat-ai==0.0.89`, `pipecat-ai-flows`, FastAPI, Pydantic  
**Storage**: JSON files (static config — `shared_persona.json` lives alongside the loader)  
**Testing**: Manual integration testing via live WebRTC session (no automated test suite)  
**Target Platform**: Linux server (Ubuntu) / macOS (Apple Silicon) — same as all server-side work  
**Project Type**: Web service (backend pipeline component)  
**Performance Goals**: Zero added latency to session startup; the injection is a pure in-memory string concatenation at load time  
**Constraints**: Fallback instructions must not call or trigger flow-state transition functions during an off-topic/refusal state; English-only rule must apply across 100% of avatar turns  
**Scale/Scope**: Applies to all activities currently deployed; ~5–6 activity `flow_config.json` files affected transparently

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality** (Black, Flake8, pre-commit) | ✅ PASS | `loaders.py` changes will pass Black/Flake8 at 120-char max; Google-style docstring required on any new functions |
| **II. Testing Standards** (manual integration) | ✅ PASS | Feature verified by running a live session and triggering each fallback scenario; see Quickstart |
| **III. UX Consistency** (no UI changes) | ✅ PASS | This feature is entirely backend — no frontend changes, no new UI states |
| **IV. Performance** (p95 latency ≤ 2000ms) | ✅ PASS | Injection is in-memory at load time; no runtime path is on the hot latency path |
| **Dev Workflow** (feature branch, no direct main commits) | ✅ PASS | On branch `007-avatar-fallback-handling` |
| **flow_config.json via Flow Builder** | ✅ PASS | No `flow_config.json` files are edited; shared persona is loader-level |

Post-design re-check: No violations introduced. The design (loader injection + shared JSON) is the simplest change that satisfies all requirements.

## Project Structure

### Documentation (this feature)

```text
specs/007-avatar-fallback-handling/
├── plan.md          # This file
├── spec.md          # Feature specification
├── research.md      # Phase 0 — decisions and integration points
├── data-model.md    # Phase 1 — SharedPersonaConfig schema
├── quickstart.md    # Phase 1 — how to run and extend
├── contracts/       # (empty — no new external interface)
├── checklists/
│   └── requirements.md
└── tasks.md         # Phase 2 output — NOT created by /speckit.plan
```

### Source Code

```text
src/server/bot/
├── shared_persona.json          # NEW — shared fallback scenario definitions
└── flows/
    └── loaders.py               # MODIFIED — inject shared persona into role_messages
```

**Structure Decision**: Server-only change. The shared persona JSON sits at `src/server/bot/` (alongside the `flows/` package it feeds into). The loader modification is contained to `loaders.py`. No new Python packages, no new API endpoints, no frontend changes.

## Implementation Notes

### Injection Point in `loaders.py`

The injection happens in the `load_flow_config` function, after the optional `preprocess_flow_config` hook runs and before `FlowConfigurationFile(**flow_config_data)` validation:

```python
# Pseudocode — exact implementation in tasks
shared_persona_text = _load_shared_persona()   # reads from disk each call; no cache
for node_name, node_data in flow_config_data["flow_config"]["nodes"].items():
    role_msgs = node_data.setdefault("role_messages", [])
    role_msgs.append({"role": "system", "content": shared_persona_text})
```

The `_load_shared_persona()` helper reads `shared_persona.json` (relative to the `flows/` package directory) and assembles the scenario instructions into a single formatted string. It reads from disk on every call to `load_flow_config()` — no in-process caching — so an updated `shared_persona.json` takes effect in the next session without a server restart.

### Shared Persona Format

See [data-model.md](data-model.md) for the complete schema and an example `shared_persona.json`.

### Scenario Priority Order

Scenarios in `shared_persona.json` are injected in array order. The order in the initial file:
1. `english_only` — hard constraint, highest salience
2. `off_topic_redirect` — most common disruption
3. `silence_handling` — give adequate think time before escalating
4. `refusal_handling` — explicit verbal refusal or sustained non-participation

New scenarios are appended at the end unless they need higher priority, in which case they are inserted at the appropriate position.

### Extension Workflow

To add a new fallback scenario:
1. Open `src/server/bot/shared_persona.json`
2. Append a new `Scenario` object to the `scenarios` array
3. Increment `version` (MINOR bump)
4. Run `pre-commit run --all-files` (no Python lint issues expected for JSON changes)
5. Start a new session — changes take effect immediately (no server restart required)

No other files need to change.

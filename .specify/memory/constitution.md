# Riverst Constitution

## Core Principles

### I. Code Quality

Server code follows Black formatting and Flake8 linting (120-character line
length, per `.flake8`); public functions and classes use Google-style
docstrings. Each module keeps a single, clear responsibility — flow logic,
transport, and processing concerns stay in their existing directories
(`bot/flows/`, `bot/transport/`, `bot/processors/`, `bot/monitoring/`, etc.)
rather than being mixed together.

### II. Testing

There is no automated test suite for the server; the correctness gates are
`pre-commit run --all-files` plus manual integration testing against a live
WebRTC session. Any change to session behavior, `flow_config.json`, or the
runtime pipeline MUST be exercised in a live session before merge.

### III. UX Consistency

Changes MUST NOT introduce new user-facing states or behaviors for the child
using the avatar unless that is the explicit purpose of the feature. Backend
and infrastructure changes should be invisible to the session experience.

### IV. Performance

The real-time STT → LLM → TTS → lipsync loop has no slack for added latency.
Background or infrastructure work (logging, uploads, post-session analysis)
MUST run off the hot path — asynchronously, and without blocking session
teardown or the conversation loop.

### V. Operational Safety

No secrets or session data are committed to the repository — secrets live in
SSM Parameter Store under `/riverst/<env>/`, and `src/server/sessions/` is
gitignored. Infrastructure changes go through the environment's Terraform
root (`infra/envs/<env>`) rather than being hand-applied out-of-band, and
edits to `flow_config.json` are non-trivial enough to call out explicitly in
PR descriptions.

## Development Workflow

Pre-commit hooks (Black, Flake8, ESLint, Prettier) run via
`pre-commit run --all-files` before merge. `sandbox` is the environment
routine changes land on first (it tracks its own `sandbox` git branch and is
fully Terraform-managed); `prod` is hand-built outside Terraform and is
adopted separately — see `infra/README.md`.

## Governance

This constitution documents conventions already established in `CLAUDE.md`
and by prior features (e.g. `specs/008-story-context-lookup/plan.md`).
Amendments should update both this file and `CLAUDE.md` together so they do
not drift.

**Version**: 1.0.0 | **Ratified**: 2026-09-22 | **Last Amended**: 2026-09-22

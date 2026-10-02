# Implementation Plan: Sandbox Session Transcript Storage in S3

**Branch**: `009-sandbox-s3-transcripts` (git branch: `claude/sandbox-s3-transcripts-22f273`) | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/009-sandbox-s3-transcripts/spec.md`

## Summary

Sandbox session transcripts currently live only on the sandbox instance's
local disk (`sessions/<session_id>/transcript.json`) and are lost if the
instance is ever rebuilt or terminated. This feature provisions a dedicated,
private S3 bucket for the sandbox environment and uploads each session's
transcript to it automatically when the session ends — asynchronously, off
the real-time conversation path, with upload failures logged but never
blocking or affecting the user's session.

## Technical Context

**Language/Version**: Python 3.11 (server); OpenTofu/Terraform >= 1.6, AWS provider ~> 5.60 (infra)
**Primary Dependencies**: `boto3` (new — no AWS SDK currently in `src/server/requirements.txt`); existing `pipecat-ai` event/transport stack unaffected
**Storage**: New S3 bucket (`riverst-sandbox-transcripts-046959477181`), private, SSE-S3 encrypted; local disk storage of transcripts is unchanged and remains the source of truth during a session
**Testing**: No automated test suite (project-wide); `pre-commit run --all-files` plus manual integration testing against a live sandbox session, including a forced-failure check of the upload path
**Target Platform**: Sandbox EC2 instance (Ubuntu 24.04, `infra/envs/sandbox`), FastAPI server process
**Project Type**: Web service (real-time voice pipeline server) + its Terraform-managed infrastructure
**Performance Goals**: Zero added latency to the live conversation loop or to session teardown; upload runs via `asyncio.to_thread` inside a fire-and-forget `asyncio.create_task`, matching the existing audio-analysis trigger pattern
**Constraints**: Must not affect production (opt-in per environment, default off); must not require any new secret (bucket name is not sensitive); upload failure must never surface to the user or block disconnect handling
**Scale/Scope**: One environment (sandbox) initially; one object per session; no new API endpoints or UI surface

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Code Quality | PASS | New `transcript_uploader.py` is a single-responsibility helper; Black/Flake8 (120 char) and Google-style docstrings apply as usual |
| II. Testing | PASS | No automated suite exists project-wide; plan requires a live sandbox session test plus an explicit forced-failure check (see quickstart.md) before merge |
| III. UX Consistency | PASS | Entirely invisible to the child using the avatar — no new prompts, states, or timing changes in the conversation |
| IV. Performance | PASS | Upload is async and off the hot path (`asyncio.to_thread` + `create_task`); no change to the STT→LLM→TTS→lipsync loop |
| V. Operational Safety | PASS | No secret introduced (bucket name is plain config, not SSM); bucket is private with SSE-S3 and public access fully blocked; infra change goes through `infra/envs/sandbox`, not hand-applied; this plan explicitly flags the `flow_config.json`-style non-trivial infra change (IAM + new bucket) for the PR description |

*Post-design re-check*: No violations after Phase 1 design. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/009-sandbox-s3-transcripts/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created by /speckit.plan)
```

No `contracts/` directory: this feature adds no public API, CLI, or
inter-service contract — it's an internal upload step plus infrastructure.
The S3 object key schema (the closest thing to a contract here) is documented
in `data-model.md` instead.

### Source Code (repository root)

```text
infra/
├── modules/riverst-env/
│   ├── variables.tf          # + enable_transcript_storage (bool, default false)
│   ├── storage.tf            # NEW: S3 bucket, versioning off, SSE-S3, public access block
│   ├── iam.tf                # + scoped PutObject/GetObject policy on the new bucket
│   ├── user_data.sh.tftpl    # + RIVERST_TRANSCRIPTS_BUCKET written into src/server/.env
│   └── outputs.tf            # + transcripts_bucket output
└── envs/sandbox/
    └── main.tf                # enable_transcript_storage = true

infra/README.md                                 # + "Retrieving sandbox session transcripts" section

src/server/
├── requirements.txt                          # + boto3
└── bot/
    ├── components/
    │   └── transcript_uploader.py            # NEW: upload one file to S3, log-only on failure
    └── core/
        └── event_manager.py                  # on_client_disconnected calls the uploader (fire-and-forget)
```

**Structure Decision**: This is the existing single-project layout (FastAPI
server + its Terraform infra), extended in place — no new top-level project,
service, or frontend surface. The upload logic follows the existing
`bot/components/` convention (alongside `transcription.py`, `memory.py`) as a
small, independently-readable module, and is wired in at the one existing
hook already used for a comparable fire-and-forget post-session job
(`event_manager.py`'s `on_client_disconnected`, next to the audio-analysis
trigger). Infrastructure changes stay inside the existing
`infra/modules/riverst-env` module, gated by a new opt-in variable so `prod`
is unaffected unless separately enabled.

## Complexity Tracking

*No Constitution Check violations — this section is not applicable.*

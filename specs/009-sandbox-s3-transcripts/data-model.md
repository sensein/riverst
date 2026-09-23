# Data Model: Sandbox Session Transcript Storage in S3

**Branch**: `009-sandbox-s3-transcripts` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

No database or schema changes. This feature adds one new durable-storage
resource and one new outbound copy operation over data that already exists.

## Entities

### Session Transcript

The JSON record of a session's conversation turns. Already produced today;
unchanged in this feature.

| Field | Description |
|---|---|
| Local path | `src/server/sessions/<session_id>/transcript.json` (existing) |
| Format | JSON array of message objects (existing `TranscriptHandler.messages`) |
| Written by | `TranscriptHandler.save_messages()` on every transcript update (existing) |
| Read by (new) | The upload step, once, after the session ends |

### S3 Bucket (new)

One per environment; this feature provisions it for `sandbox` only.

| Field | Value |
|---|---|
| Name | `riverst-sandbox-transcripts-046959477181` |
| Region | `us-east-2` (matches the rest of the account) |
| Public access | Fully blocked (`block_public_acls`, `block_public_policy`, `ignore_public_acls`, `restrict_public_buckets` all `true`) |
| Encryption | SSE-S3 (`AES256`), default on the bucket |
| Versioning | Off — a re-upload for the same session is an intentional replace (FR-008), not a history to keep |
| Access | Only the sandbox instance role, scoped to `PutObject`/`GetObject` on this bucket's objects |

### Upload Event (new, not persisted — a runtime action)

Triggered once per session, at session end.

| Field | Description |
|---|---|
| Trigger | `on_client_disconnected` handler, after `task.cancel()` and audio-analysis dispatch |
| Input | `session_dir`, `session_id`, transcript path (`<session_dir>/transcript.json`) |
| Destination | `s3://<RIVERST_TRANSCRIPTS_BUCKET>/<session_id>/transcript.json` |
| Config gate | `RIVERST_TRANSCRIPTS_BUCKET` env var — unset (e.g. local dev) means the upload step is a no-op |
| Outcomes | `uploaded` (logged at info) or `failed` (logged at error; local file untouched either way) |
| Idempotency | Re-running for the same session overwrites the same S3 key — no duplicate objects |

## Key Schema

```text
s3://riverst-sandbox-transcripts-046959477181/<session_id>/transcript.json
```

`<session_id>` is the same identifier already used for the local
`sessions/<session_id>/` directory, so a transcript is always locatable by
session ID alone (SC-004) without needing a separate index.

## State Transitions

```text
Session running
  → TranscriptHandler keeps local transcript.json up to date (existing, unchanged)
Session ends (on_client_disconnected)
  → local transcript.json is final
  → asyncio.create_task: upload local transcript.json to S3 (non-blocking)
      success → object present at <session_id>/transcript.json (logged)
      failure → error logged; local transcript.json retained; no user-visible effect
```

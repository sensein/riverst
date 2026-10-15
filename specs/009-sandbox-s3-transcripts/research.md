# Research: Sandbox Session Transcript Storage in S3

**Branch**: `009-sandbox-s3-transcripts` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

## Context gathered from the existing codebase

- Transcripts are already produced locally: `TranscriptHandler` in
  [`src/server/bot/components/transcription.py`](../../src/server/bot/components/transcription.py)
  writes `sessions/<session_id>/transcript.json` on every update
  (`bot_runner.py` wires `output_file=os.path.join(session_dir, "transcript.json")`).
- There is already a fire-and-forget, feature-flagged post-session hook to
  copy from: `on_client_disconnected` in
  [`event_manager.py`](../../src/server/bot/core/event_manager.py) schedules
  `asyncio.create_task(trigger_analysis_on_audios(...))`, gated by the
  `ANALYZE_AUDIO` env var, after `task.cancel()`. This is the natural place to
  add a transcript upload without touching the live conversation loop.
- `src/server/requirements.txt` has no AWS SDK today — `boto3` is a new
  dependency.
- Sandbox infra (`infra/envs/sandbox` → `infra/modules/riverst-env`) already
  gives the EC2 instance a dedicated IAM instance profile
  (`aws_iam_instance_profile.instance` in `iam.tf`) scoped to *its own*
  environment's resources (SSM parameters under `/riverst/sandbox/*` only).
  The same "own environment only" scoping convention applies to a new bucket
  permission.
- Non-secret app configuration (`RIVERST_ENVIRONMENT`, `RIVERST_COMPUTE_DEVICE`)
  is already written into `src/server/.env` by `user_data.sh.tftpl` from plain
  Terraform template variables — this is the existing channel for a new
  `RIVERST_TRANSCRIPTS_BUCKET` value, no new secret machinery needed.
- `infra/bootstrap/main.tf` already has a working, reviewed pattern for a
  private, encrypted S3 bucket (`aws_s3_bucket` + `_versioning` +
  `_server_side_encryption_configuration` + `_public_access_block`) to mirror.
- Instance `user_data` changes do **not** auto-apply to the already-running
  sandbox instance (`ignore_changes = [ami, user_data]` in `compute.tf`,
  documented as deliberate in `infra/README.md`); the sandbox box needs a
  manual `cloud-init clean && reboot` re-bootstrap after this change, the same
  operational step already required after populating secrets.

## Decisions

### D1: AWS SDK — `boto3`, invoked off the event loop

**Decision**: Add `boto3` to `src/server/requirements.txt` and call its
(blocking) `put_object` inside `asyncio.to_thread(...)`, itself wrapped in the
existing `asyncio.create_task(...)` pattern in `on_client_disconnected`.

**Rationale**: `boto3` is the standard, well-supported AWS SDK for Python and
is what `infra`'s own conventions (and the `aws-sdk-python-usage` skill)
assume. Running the blocking call via `asyncio.to_thread` keeps it from
stalling the event loop, satisfying the performance principle (no impact on
session teardown) without pulling in an async AWS SDK (`aioboto3`) purely for
one call site.

**Alternatives considered**:
- `aioboto3` — rejected: an extra dependency and a different API surface just
  to avoid a single `to_thread` call.
- Shelling out to the `aws` CLI — rejected: fragile error handling, adds a
  process-spawn dependency the app doesn't otherwise have, and the AWS CLI
  isn't guaranteed present on the app's Python environment path.

### D2: Bucket provisioning — new dedicated bucket, per environment, opt-in

**Decision**: Add the bucket to `infra/modules/riverst-env` behind a new
`enable_transcript_storage` variable (default `false`), turned on explicitly
in `infra/envs/sandbox/main.tf`. Bucket name:
`riverst-${var.environment}-transcripts-${data.aws_caller_identity.current.account_id}`,
matching the existing `riverst-tfstate-046959477181` naming convention.

**Rationale**: Keeps prod untouched by default (per spec FR-009 / scope), the
same way `enable_monitoring` and `enable_scheduled_shutdown` already gate
sandbox-only behavior in the shared module. Per-environment buckets (rather
than one shared bucket) keep the existing "no environment can see another
environment's data" boundary that the SSM parameter scoping already
establishes.

**Alternatives considered**:
- One shared bucket with a prefix per environment — rejected: would need
  IAM conditions keyed on prefix instead of a plain resource ARN, more
  complex than per-environment buckets for no real benefit at this scale.
- Reusing the `infra/bootstrap` state bucket — rejected: mixes Terraform
  state with application data; different lifecycle, different access needs.

### D3: IAM — extend the existing instance role, scoped to one bucket

**Decision**: A new `aws_iam_role_policy` attached to the existing
`aws_iam_role.instance`, granting `s3:PutObject` and `s3:GetObject` only on
`arn:...:s3:::<bucket>/*` (no `s3:ListBucket`/bucket-level access, and
nothing on any other bucket).

**Rationale**: Mirrors `instance_secrets` in `iam.tf` — least-privilege,
scoped to exactly the one resource this environment owns. `GetObject` is
included (not just `PutObject`) so the same role could support a future
read-side tool without a second IAM change; it costs nothing extra to grant
alongside write access on the same object prefix.

**Alternatives considered**:
- A separate IAM role just for uploads — rejected: the instance already has
  one role; adding a second role/profile is unnecessary complexity for one
  more permission.

### D4: Upload trigger — session end, not periodic sync

**Decision**: Upload the transcript once, at `on_client_disconnected`, after
the transcript has stopped changing (session is ending) — not a periodic
background sync of the sessions directory.

**Rationale**: Matches user story 3 (automatic, no manual step) and keeps the
change scoped to one call site that already exists for a similar purpose
(the audio analysis trigger). A periodic sweep would need its own
scheduling, de-duplication, and partial-write handling for no benefit the
spec asks for.

**Alternatives considered**:
- Upload after every `save_messages()` call (i.e., after every turn) —
  rejected: far more S3 requests than needed; the spec only requires the
  transcript be durable once the session is over, and mid-session network
  cost is exactly the kind of overhead the performance principle warns
  against.
- A separate backfill/reconciliation script for old or failed uploads — out
  of scope for this feature (not required by any FR); noted as a possible
  follow-up, not built now.

### D5: Failure handling — log and keep the local copy, no retry queue

**Decision**: Wrap the upload in a `try/except` that only logs on failure
(mirroring `trigger_analysis_on_audios`'s own `except Exception` block); the
local `transcript.json` is never deleted regardless of upload outcome.

**Rationale**: Directly satisfies FR-004/FR-005 and SC-003 (upload failures
must never affect the user's session) with the simplest possible mechanism.
The local copy already survives instance stop/start (EBS-backed, not
ephemeral) — the risk this feature closes is instance *replacement* or
*terminate*, and a lost sandbox re-run trying again on the next session is an
acceptable gap for this environment.

**Alternatives considered**:
- A retry queue / dead-letter mechanism — rejected as over-engineering for a
  disposable sandbox environment with no SLA on transcript delivery latency
  (spec has no such requirement).

### D6: Object key layout

**Decision**: `<session_id>/transcript.json` — one prefix per session,
mirroring the existing local layout `sessions/<session_id>/transcript.json`.

**Rationale**: Satisfies FR-003/FR-008 and SC-004 directly — a reviewer who
has a session ID can go straight to `s3://<bucket>/<session_id>/transcript.json`
with no directory listing needed, and re-uploads land on the same key
(replace, not duplicate) with no extra logic required.

**Alternatives considered**:
- A flat key like `<session_id>.json` — equivalent in practice; the prefix
  form was chosen only because it leaves room for another artifact type
  under the same session prefix later without a rename.

---

description: "Task list for Sandbox Session Transcript Storage in S3"
---

# Tasks: Sandbox Session Transcript Storage in S3

**Input**: Design documents from `/specs/009-sandbox-s3-transcripts/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: The project has no automated test suite (see Constitution Principle
II) — verification is manual, against a live sandbox session. Each user
story phase therefore includes explicit manual-validation tasks tied to
`quickstart.md` in place of automated test tasks.

**Organization**: Tasks are grouped by user story (from spec.md) to enable
independent verification of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to the repository root

## Path Conventions

Single project (FastAPI server + its Terraform infra) — no new top-level
directories. See plan.md's Project Structure for the full file list.

---

## Phase 1: Setup

**Purpose**: Add the one new dependency and the one new Terraform toggle
everything else in this feature is gated behind.

- [X] T001 Add `boto3` to `src/server/requirements.txt`
- [X] T002 [P] Add `enable_transcript_storage` variable (bool, default `false`) to `infra/modules/riverst-env/variables.tf`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Provision the S3 bucket, its IAM permissions, and the plain
config channel the app reads the bucket name from. No user story can be
verified until this phase is applied to sandbox.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Create `infra/modules/riverst-env/storage.tf`: `aws_s3_bucket` named `riverst-${var.environment}-transcripts-${data.aws_caller_identity.current.account_id}` plus `aws_s3_bucket_versioning` (Suspended/off), `aws_s3_bucket_server_side_encryption_configuration` (SSE-S3/AES256), and `aws_s3_bucket_public_access_block` (all four flags true) — all `count = var.enable_transcript_storage ? 1 : 0`, mirroring `infra/bootstrap/main.tf`'s state-bucket pattern
- [X] T004 Add a scoped `aws_iam_role_policy` in `infra/modules/riverst-env/iam.tf` granting `s3:PutObject` and `s3:GetObject` only on the new bucket's `/*` ARN, attached to the existing `aws_iam_role.instance`, also gated on `var.enable_transcript_storage`
- [X] T005 Pass the bucket name into `user_data = templatefile(...)` in `infra/modules/riverst-env/compute.tf` (new `transcripts_bucket` template var, empty string when disabled) and write `RIVERST_TRANSCRIPTS_BUCKET=${transcripts_bucket}` into the `src/server/.env` heredoc in `infra/modules/riverst-env/user_data.sh.tftpl`
- [X] T006 [P] Add a `transcripts_bucket` output (empty string when disabled) to `infra/modules/riverst-env/outputs.tf`
- [X] T007 Set `enable_transcript_storage = true` in `infra/envs/sandbox/main.tf`
- [ ] T008 Run `terraform fmt` and `terraform validate` in `infra/modules/riverst-env` and `infra/envs/sandbox` (done — `tofu fmt`/`tofu validate` both pass; this also surfaced and fixed an unrelated pre-existing bug, an unescaped `%{http_code}` in `user_data.sh.tftpl` that broke `templatefile()` entirely), then `terraform plan` from `infra/envs/sandbox` and confirm the plan shows only the new bucket/IAM/env-var resources for the sandbox module — `infra/envs/prod` is a separate Terraform root with its own state (`infra/envs/prod/backend.tf`), so it is structurally untouched by this plan, not merely absent from it (**blocked**: this session's `aws login` has expired and re-authenticating needs interactive Duo — the user needs to run `terraform plan` themselves)

**Checkpoint**: Bucket, IAM policy, and `RIVERST_TRANSCRIPTS_BUCKET` plumbing are ready to apply. No application code depends on anything not yet in place.

---

## Phase 3: User Story 1 - Transcripts survive instance loss (Priority: P1) 🎯 MVP

**Goal**: Every completed sandbox session's transcript is automatically and durably copied to S3, so it survives the instance being stopped, rebuilt, or terminated.

**Independent Test**: Run a sandbox session to completion, confirm the transcript appears in S3 under a session-identifying key, then confirm it remains retrievable independent of the sandbox instance's own state.

### Implementation for User Story 1

- [X] T009 [US1] Create `src/server/bot/components/transcript_uploader.py`: an `async def upload_transcript(session_id: str, transcript_path: str) -> None` that reads `RIVERST_TRANSCRIPTS_BUCKET` from the environment, no-ops with a debug log if unset, otherwise runs boto3's `put_object` (key `f"{session_id}/transcript.json"`) inside `asyncio.to_thread(...)`, wrapped in `try/except Exception` that only logs (never raises) — implemented with `upload_file` instead of a manual `put_object`+read, same effect, simpler
- [X] T010 [US1] Wire `transcript_uploader.upload_transcript(...)` into `on_client_disconnected` in `src/server/bot/core/event_manager.py` via `asyncio.create_task(...)`, alongside the existing `trigger_analysis_on_audios` dispatch, passing the session id and `os.path.join(self.session_dir, "transcript.json")`
- [~] T011 [US1] Apply the Phase 2 Terraform change to sandbox (`terraform apply` from `infra/envs/sandbox`) and re-bootstrap the running sandbox instance (`aws ssm start-session` → `sudo cloud-init clean && sudo reboot`) per quickstart.md — **terraform apply done** (5 added, 0 changed, 0 destroyed: `riverst-sandbox-transcripts-046959477181` + scoped IAM policy; state synced back to the main checkout). **Re-bootstrap not yet done, and shouldn't happen yet**: the sandbox instance's bootstrap script tracks the `sandbox` git branch/origin, which doesn't have `transcript_uploader.py`/`event_manager.py` yet (still only on this local, unpushed branch) — rebooting now would just pick up the new `.env` var with no code to use it, for a real (if brief) service interruption. Re-bootstrap once this code is merged to `sandbox`.
- [ ] T012 [US1] Manually validate per quickstart.md: run a sandbox session to completion, then confirm `aws s3 ls s3://riverst-sandbox-transcripts-046959477181/<session_id>/` shows `transcript.json` and its downloaded content matches the local `sessions/<session_id>/transcript.json`
- [ ] T013 [US1] Manually validate FR-008 (overwrite, not duplicate): for the same `<session_id>`, trigger a second upload (e.g. re-run `upload_transcript` for that session, or end a second session that reuses a test session id) and confirm S3 still shows exactly one object at `<session_id>/transcript.json` — no `-1`/duplicate key, and its content reflects the latest upload
- [ ] T014 [US1] Manually validate durability two ways: (a) stop the sandbox instance (or wait for the nightly stop) and confirm the object is still downloadable from S3 afterward; (b) delete the local `sessions/<session_id>/` copy on the instance and confirm the transcript is still fully downloadable from S3 — this isolates the actual guarantee behind "terminated or rebuilt" (the object's existence never depended on the instance or its disk) without needing to destroy the running sandbox instance for every validation pass

**Checkpoint**: User Story 1 is fully functional and independently verifiable — this is the MVP.

---

## Phase 4: User Story 2 - Reviewer retrieves a past session without EC2 access (Priority: P2)

**Goal**: A team member can find and download any session's transcript from S3 using only its session ID, without SSH or EC2 access, and the bucket is not exposed beyond authorized access.

**Independent Test**: Given a known session ID, retrieve its transcript using only S3 access (`aws s3` CLI or console) — no `aws ssm start-session` involved.

### Implementation for User Story 2

- [ ] T015 [US2] Manually validate per quickstart.md: using only `aws s3 ls` / `aws s3 cp` against `s3://riverst-sandbox-transcripts-046959477181/<session_id>/`, retrieve a known session's transcript with no ambiguity about which object it is
- [ ] T016 [US2] Manually validate access restriction: confirm an unauthenticated request to the bucket/object (e.g. the plain HTTPS object URL, no SigV4) is rejected, confirming the public-access-block from T003 is effective
- [X] T017 [US2] [P] Add a short "Retrieving sandbox session transcripts" section to `infra/README.md` documenting the `aws s3 ls` / `aws s3 cp` retrieval commands for reviewers who only have S3 access, and stating explicitly that access is via the existing account-level admin identity (no separate reviewer IAM role is created by this feature — see spec.md Assumptions)

**Checkpoint**: User Stories 1 and 2 both independently functional and verified.

---

## Phase 5: User Story 3 - Upload happens automatically, every session (Priority: P3)

**Goal**: No operator ever has to remember a manual export step — every session's transcript uploads automatically at session end, before the nightly sandbox stop.

**Independent Test**: Run several sandbox sessions back-to-back with no manual intervention and confirm all of their transcripts land in S3.

### Implementation for User Story 3

- [ ] T018 [US3] Manually validate per quickstart.md: run 2-3 sandbox sessions back-to-back with no manual commands run between them, then confirm every session's transcript is present in S3
- [ ] T019 [US3] Manually validate timing: check server logs (or CloudWatch, if forwarded) to confirm a session's upload completed within seconds of that session ending, not at or after the nightly scheduled stop

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T020 [P] Run `pre-commit run --all-files` and fix any Black/Flake8 findings in the new/changed Python and Terraform files (**partial**: the `pre-commit` binary isn't installed in this environment; ran the equivalent directly instead — `black`/`flake8` clean on `transcript_uploader.py` and `event_manager.py`, `tofu fmt`/`tofu validate` clean on the changed `.tf`/`.tftpl` files. No client-side files touched, so ESLint/Prettier hooks don't apply. Re-run the real `pre-commit run --all-files` once it's installed, to be sure)
- [ ] T021 Manually validate the forced-failure path per quickstart.md: temporarily point `RIVERST_TRANSCRIPTS_BUCKET` at a nonexistent bucket (or otherwise break the IAM policy), confirm the session still ends normally for the user, an error is logged, and the local `transcript.json` is untouched — then restore the correct configuration
- [ ] T022 Write the PR description calling out the infrastructure change explicitly (new bucket + IAM policy on the sandbox instance role), per Constitution Principle V
- [ ] T023 Regression check: run a session on a different activity (e.g. audiobook or basic-avatar-demo) and confirm its transcript also uploads correctly — the uploader is not vocab-tutoring-specific

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001-T002) — BLOCKS all user stories; must be applied to sandbox (T008's plan reviewed, then T011 in Phase 3 actually applies it)
- **User Story 1 (Phase 3)**: Depends on Foundational — delivers the core mechanism (T009, T010) and is the first phase that applies infra (T011)
- **User Story 2 (Phase 4)**: Depends on Foundational + the applied infra from Phase 3 (T011) — reuses the same bucket/IAM, adds no new code, only verification + documentation
- **User Story 3 (Phase 5)**: Depends on Foundational + Phase 3's application code (T009-T010) — reuses the same upload path, adds no new code, only verification
- **Polish (Phase 6)**: Depends on Phases 3-5 being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — this is the mechanism every other story observes
- **User Story 2 (P2)**: Observes the mechanism built in US1 from a different angle (retrieval, access control); no code changes of its own
- **User Story 3 (P3)**: Observes the mechanism built in US1 from a different angle (automaticity, timing); no code changes of its own

Note: unlike a typical multi-surface feature, US2 and US3 here are primarily
verification and documentation on top of the one mechanism US1 builds —
there is a single upload code path (T009-T010) and a single infra change
(T003-T007), not parallel independent implementations. They are still
listed as separate phases because each has its own pass/fail acceptance
criteria in spec.md and should be checked off independently before calling
the feature done.

### Parallel Opportunities

- T001 and T002 can run in parallel (different files)
- T003, T004, T006 touch different Terraform files and can be drafted in parallel, but T004 references the bucket T003 creates, so validate/plan (T008) only after all three are written
- T016 and T017 in Phase 4 can run in parallel (one is a manual check, the other is a doc edit)
- T020 (pre-commit) can run in parallel with any manual-validation task

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Draft together (different files), then validate as a whole with T008:
Task: "Create infra/modules/riverst-env/storage.tf"
Task: "Add transcripts_bucket output to infra/modules/riverst-env/outputs.tf"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T008) — CRITICAL, blocks everything else
3. Complete Phase 3: User Story 1 (T009-T014), including applying infra to sandbox
4. **STOP and VALIDATE**: T012, T013, and T014 confirm transcripts upload, don't duplicate on re-upload, and survive instance loss
5. This alone satisfies the feature's core problem statement (spec.md's "why now")

### Incremental Delivery

1. Setup + Foundational → bucket and IAM exist, nothing uploads yet
2. Add User Story 1 (T009-T014) → transcripts durably land in S3 (MVP)
3. Add User Story 2 (T015-T017) → confirm/document reviewer retrieval without EC2 access
4. Add User Story 3 (T018-T019) → confirm zero-manual-step, correct timing
5. Polish (T020-T023) → lint, forced-failure check, PR framing, regression check

---

## Notes

- No automated tests exist or are added here — see Constitution Principle II; every "test" task above is a manual `quickstart.md` validation step instead
- [P] tasks touch different files with no dependency between them
- The Terraform apply in T011 is the one action in this feature with real
  blast radius (touches the live sandbox instance's IAM role and requires a
  re-bootstrap) — confirm the `terraform plan` from T008 looks right before
  running it
- Prod is untouched throughout: `enable_transcript_storage` defaults to
  `false` and is never set in `infra/envs/prod`

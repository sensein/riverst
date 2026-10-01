# Quickstart: Sandbox Session Transcript Storage in S3

**Branch**: `009-sandbox-s3-transcripts` | **Date**: 2026-09-22

## What this feature adds

A dedicated S3 bucket for the sandbox environment, and an automatic,
non-blocking upload of each session's `transcript.json` to that bucket when
the session ends — so transcripts survive instance stop/rebuild/terminate
and are reviewable without EC2 access.

## Files changed (expected — see plan.md Project Structure)

| File | Change |
|---|---|
| `infra/modules/riverst-env/variables.tf` | New `enable_transcript_storage` (bool, default `false`) |
| `infra/modules/riverst-env/storage.tf` (new) | S3 bucket + versioning-off + SSE + public-access-block, only when `enable_transcript_storage = true` |
| `infra/modules/riverst-env/iam.tf` | New scoped `s3:PutObject`/`s3:GetObject` policy on the new bucket, attached to the existing instance role |
| `infra/modules/riverst-env/user_data.sh.tftpl` | Write `RIVERST_TRANSCRIPTS_BUCKET=<bucket>` into `src/server/.env` |
| `infra/modules/riverst-env/outputs.tf` | New `transcripts_bucket` output (empty string when disabled) |
| `infra/envs/sandbox/main.tf` | `enable_transcript_storage = true` |
| `src/server/requirements.txt` | Add `boto3` |
| `src/server/bot/components/transcript_uploader.py` (new) | Small helper: upload one file to S3, log-only on failure |
| `src/server/bot/core/event_manager.py` | Call the uploader from `on_client_disconnected`, fire-and-forget |

## How to test locally (app logic, no AWS needed)

1. Leave `RIVERST_TRANSCRIPTS_BUCKET` unset in `src/server/.env`.
2. Start the server and client as usual, run a short session, end it.
3. Confirm in logs that the upload step no-ops cleanly (no bucket configured)
   and the session still tears down normally — this is the local dev path.

## How to test against real S3 (after the Terraform change is applied to sandbox)

1. Apply the infra change (see below), then re-bootstrap the sandbox
   instance — `user_data` changes do not auto-apply to a running instance:
   ```
   aws ssm start-session --target <sandbox-instance-id> --region us-east-2
   sudo cloud-init clean && sudo reboot
   # then watch: sudo tail -f /var/log/riverst-bootstrap.log
   ```
2. Run a full session against sandbox to completion.
3. Confirm the object exists:
   ```
   aws s3 ls s3://riverst-sandbox-transcripts-046959477181/<session_id>/
   ```
4. Download it and diff against the local copy in
   `src/server/sessions/<session_id>/transcript.json` — they should match.
5. Stop the sandbox instance (or wait for the nightly stop) and confirm the
   object is still retrievable from S3.
6. Force a failure (e.g., temporarily break the IAM policy or bucket name)
   and confirm: the session still ends normally for the user, an error is
   logged, and the local `transcript.json` is untouched.

## Terraform apply (sandbox)

```
cd infra/envs/sandbox
eval "$(aws configure export-credentials --format env)"
aws login
terraform plan   # review: new bucket, new IAM policy, no changes to prod
terraform apply
```

## Pre-commit

```
pre-commit run --all-files
```

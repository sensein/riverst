# Riverst AWS environments

Terraform for two environments — `sandbox` and `prod` — in account **046959477181**,
region **us-east-2**, isolated by separate VPCs and `Environment` tags.

## Why this shape

Pipecat's `small-webrtc` transport sends media **peer-to-peer directly to the host**
over UDP 10000–65535, with coturn alongside it on 3478. That rules out the reflexive
"ALB + Fargate + autoscaling" design: an ALB is HTTP-only, and a 55,000-port UDP range
plus a TURN server is genuinely painful on Fargate.

So the runtime shape stays what it already is — **one EC2 instance per environment** —
and the work goes into making it reproducible: IaC, secrets in Parameter Store,
SSM instead of open SSH, snapshots, and alarms.

## Layout

```
infra/
  bootstrap/            S3 remote state bucket (apply once, first)
  modules/riverst-env/  the whole environment, parameterised
  envs/sandbox/         sandbox root  — 10.20.0.0/16, m6i.xlarge, nightly shutdown
  envs/prod/            prod root     — 10.10.0.0/16, c6i.2xlarge, always on
```

## What the module builds

| | |
|---|---|
| Network | Dedicated VPC, one public subnet, IGW. No NAT (nothing for it to do here, saves ~$33/mo/env) |
| Security group | 443, 80, 3478 TCP+UDP, 10000-65535 UDP. **Port 22 closed by default** |
| Compute | Ubuntu 24.04 (Canonical SSM pointer), gp3 encrypted root, IMDSv2 required, `delete_on_termination = false` |
| Identity | Instance profile with SSM Session Manager + read access scoped to *its own* `/riverst/<env>/*` parameters |
| Secrets | Parameter Store SecureStrings, created empty with `ignore_changes` — values never touch state or tfvars |
| DNS | A record in the existing `kivaproject.org` zone → the environment's EIP |
| Bootstrap | `user_data.sh.tftpl` codifies all 13 manual steps from `notes/first_steps_to_deploy.md` |
| Backups | DLM daily root-volume snapshots (14 retained prod, 3 sandbox) |
| Monitoring | SNS topic + alarms on status check, CPU, root disk >80%. `enable_monitoring` — **off for sandbox** (the nightly scheduled stop reads as a status-check failure), on for prod |
| Cost control | EventBridge Scheduler stop/start, enabled on sandbox only |

## Prerequisites

Terraform is not installed on this machine:

```bash
brew install opentofu   # Homebrew core no longer ships Terraform
```

The AWS provider does not understand the CLI's `login_session` config key, so
export credentials into the environment first, in every new shell:

```bash
eval "$(aws configure export-credentials --format env)"
```

Then authenticate — the session is short-lived and expires:

```bash
aws login
```

## Standing up sandbox

```bash
cd infra/bootstrap && terraform init && terraform apply
```

Then uncomment the backend block in `envs/sandbox/backend.tf` and:

```bash
cd infra/envs/sandbox
cp terraform.tfvars.example terraform.tfvars   # set your emails
terraform init && terraform plan
```

Read the plan, then `terraform apply`. Afterwards, populate the secrets — the app
will not work until you do, because Terraform only creates empty placeholders:

```bash
for k in OPENAI_API_KEY GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET SECRET_KEY TURN_USER TURN_PASSWORD; do
  read -rsp "$k: " v && echo
  aws ssm put-parameter --region us-east-2 --name "/riverst/sandbox/$k" \
    --type SecureString --value "$v" --overwrite
done
```

The instance fetches these at boot, so re-run the bootstrap after setting them:

```bash
aws ssm start-session --target <instance-id> --region us-east-2
sudo cloud-init clean && sudo reboot
# then watch: sudo tail -f /var/log/riverst-bootstrap.log
```

You also need a Google OAuth redirect URI for `https://sandbox.kivaproject.org`,
and the sandbox user added to `src/server/config/authorized_users.json`.

## Retrieving sandbox session transcripts

Every sandbox session's transcript is uploaded automatically to a dedicated
S3 bucket when the session ends (see `specs/009-sandbox-s3-transcripts/`),
so it survives the instance being stopped, rebuilt, or terminated. Access is
via the same account-level identity already used for everything else in
this account — there is no separate reviewer-specific IAM role.

```bash
aws login   # if your session has expired
BUCKET=$(cd infra/envs/sandbox && terraform output -raw transcripts_bucket)

# List a session's transcript by its session ID:
aws s3 ls "s3://$BUCKET/<session_id>/" --region us-east-2

# Download it:
aws s3 cp "s3://$BUCKET/<session_id>/transcript.json" ./transcript.json --region us-east-2
```

No SSH or `aws ssm start-session` access to the sandbox instance is needed
for either of these.

## Adopting production — do this only after sandbox works

`envs/prod` is written but **deliberately not applied**. The live service is the
hand-built instance `i-073f87a2121c96159` (EIP `3.149.38.210`), in the *default*
VPC, created via launch-wizard. This config does not describe it.

**Option A — parallel build + EIP cutover (recommended).** Set
`hostname = "play-next.kivaproject.org"`, apply, verify a real conversation works,
then move the `play.kivaproject.org` A record. This mirrors the zero-downtime
procedure already in `notes/first_steps_to_deploy.md`. Snapshot the old volume and
copy `src/server/uploads/` across first — see the caveat below.

**Option B — `terraform import`.** Adopt the running instance, EIP and DNS record
into state. Avoids a rebuild, but the VPC, subnet and security group here will
never match the default-VPC resources the old box uses, so you inherit permanent
drift. Not recommended.

## Known gaps, deliberately out of scope

- **App state is still on EBS.** `src/server/sessions/` and `src/server/uploads/`
  live on the instance root volume. DLM snapshots are a stopgap, not a fix —
  replacing an instance still risks losing uploads. Moving both to S3 per
  environment is the follow-up that makes instances truly disposable.
- **`user_data` runs only on first boot** (`user_data_replace_on_change = false`,
  so edits do not silently replace a running instance). Re-bootstrap by hand with
  `cloud-init clean && reboot`.
- **No CI/CD to AWS.** Deploys are still git pull + rebuild on the box.
- **Sandbox has no alarms** (`enable_monitoring = false`). The CloudWatch agent is
  still installed and ships the bootstrap log to `/riverst/<env>/bootstrap`, which is
  what you want when debugging a failed first boot.

## Account cleanup, unrelated to this Terraform

- Release 2 unattached Elastic IPs (`18.224.102.12`, `3.21.191.176`) — ~$7/mo, and
  the quota is only 5
- Delete the 9 unused `launch-wizard-*` security groups
- `i-0ade89573f285dd91` (`riverst_demo_terminate_with_care`, g4dn.8xlarge, stopped)
  costs ~$10/mo stopped but **~$1,590/mo if started**. Nobody has confirmed what is
  on its 128 GB volume; snapshot it before deciding
- The Lambdas `trigger_riverst` / `stop_riverst` have hardcoded instance IDs and no
  EventBridge rule. `schedule.tf` replaces them; delete them once sandbox is live

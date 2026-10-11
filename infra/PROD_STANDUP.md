# Production stand-up runbook (`envs/prod`)

Stand up the **managed** production environment (`envs/prod`) so prod is reproducible and deployable the
same way as sandbox (SSM, `riverst-deploy`, backups, monitoring), replacing the current hand-built box.
Companion to `infra/README.md` → *"Adopting production"*. **Read fully before applying.**

## Why
`play.kivaproject.org` currently runs the **hand-built instance `i-073f87a2121c96159`** (EIP `3.149.38.210`,
default VPC, launch-wizard, **no IAM role, not SSM-managed, not in Terraform state**). It can only be reached
with its original SSH key and deployed by hand. `envs/prod` replaces it with a managed box controlled by
this repo.

## Decide first (don't apply until settled)
1. **Size / cost.** `envs/prod` is `c6i.2xlarge` **always-on (~$200+/mo)**. Confirm, or downsize / add a
   schedule. (Sandbox is `m6i.xlarge` with a nightly stop.)
2. **`main` is at the intended release.** Prod uses `git_ref = "main"`, so `main` must already contain the
   release you want live before the box boots (e.g. the open `main ← v1.1` promotion PR must be merged).
3. **Prod secrets** available: `OPENAI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY,
   TURN_USER, TURN_PASSWORD`.

## Approach: Option A — parallel build + DNS/EIP cutover (recommended)
Build a fresh managed box on a staging hostname, verify, then move DNS — the live box is untouched until
decommission. (Option B, `terraform import` of the current box, is rejected: it was launch-wizard'd in the
default VPC, so the module's VPC/subnet/SG can never match it.)

## Prerequisites
- AWS creds for account **046959477181** / `us-east-2` (`aws sts get-caller-identity`).
- **OpenTofu/Terraform ≥ 1.6**.
- Remote state bucket `riverst-tfstate-046959477181` exists (sandbox uses it; if not: `cd infra/bootstrap &&
  tofu init && tofu apply`).

## Procedure (from the repo root)
```bash
cd infra/envs/prod

# 1. Remote state — uncomment the backend block in backend.tf, then:
tofu init -migrate-state                      # state key: prod/terraform.tfstate

# 2. tfvars — staging hostname for the parallel build:
cat > terraform.tfvars <<'TF'
certbot_email = "<prod-certbot@…>"
alarm_email   = "<ops-alarms@…>"
hostname      = "play-next.kivaproject.org"
TF

# 3. Create + fill the SecureString params (values never touch tfvars/state):
for k in OPENAI_API_KEY GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET SECRET_KEY TURN_USER TURN_PASSWORD; do
  read -rs -p "$k: " v; echo
  aws ssm put-parameter --region us-east-2 --name "/riverst/prod/$k" --type SecureString --value "$v" --overwrite
done

# 4. Plan → review → apply:
tofu plan      # VPC 10.10.0.0/16, c6i.2xlarge + EIP, SSM role, cloud-init bootstrap (git_ref=main),
               # Route53 A for play-next, DLM 14-snapshot backups, SNS + status/CPU/disk alarms
tofu apply
```

## Verify on the staging hostname (before cutover)
- `tofu output` → `instance_id`, `public_ip`, `url`, `session_command`.
- `curl -s https://play-next.kivaproject.org/api/health` → `{"status":"ok"}`.
- Add a tester to the prod allowlist and **run a real session** (sign-in, mic, a full tutoring turn).
- `aws ssm start-session --target <instance_id> --region us-east-2` → confirm the service + deployed `main`.

## Cutover (short/zero-downtime)
1. Lower the `play.kivaproject.org` DNS TTL ahead of time.
2. Snapshot the current prod volume (safety).
3. Move `play.kivaproject.org` to the new box — re-point the A record to the new EIP, **or** set
   `hostname = "play.kivaproject.org"` in tfvars and `tofu apply`.
4. Verify `https://play.kivaproject.org` serves the new box; confirm alarms stay green.

## Decommission the old box
Once `play` is stable on the managed box, stop/terminate `i-073f87a2121c96159` (keep the volume snapshot for
a rollback window).

## Rollback
Point `play.kivaproject.org` back to `3.149.38.210` (the old box stays up until decommission) — a DNS flip.

## Notes
- `git_ref = "main"` is a moving tag for prod: future releases = merge to `main`, then `riverst-deploy` on
  the box (or `tofu apply` for infra changes). Keep prod on releases, not raw `main` churn.
- `enable_monitoring = true` → confirm the `alarm_email` SNS subscription or alarms read "insufficient data".

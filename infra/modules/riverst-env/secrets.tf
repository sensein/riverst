# Terraform creates each parameter as an empty SecureString placeholder and then
# stops caring about its value -- ignore_changes means a rotated secret never
# shows up as drift, and real values never enter the state file or a .tfvars.
#
# Populate them once per environment with:
#   aws ssm put-parameter --name /riverst/<env>/OPENAI_API_KEY \
#     --type SecureString --value '...' --overwrite --region us-east-2

locals {
  app_secret_names = [
    "OPENAI_API_KEY",
    "GOOGLE_CLIENT_ID",
    # Not currently read by any server code (auth.py uses GOOGLE_CLIENT_ID only),
    # kept because the deploy notes call for it and OAuth may need it later.
    "GOOGLE_CLIENT_SECRET",
    "SECRET_KEY",
    # Names must match exactly what src/server/main.py reads:
    #   turn_url = os.getenv("TURN_URL") / TURN_USERNAME / TURN_CREDENTIAL
    "TURN_USERNAME",
    "TURN_CREDENTIAL",
  ]
}

resource "aws_ssm_parameter" "app" {
  for_each = toset(local.app_secret_names)

  name        = "${local.ssm_prefix}/${each.value}"
  description = "Riverst ${var.environment}: ${each.value}"
  type        = "SecureString"
  value       = "PLACEHOLDER-SET-ME"
  tags        = local.tags

  lifecycle {
    ignore_changes = [value]
  }
}

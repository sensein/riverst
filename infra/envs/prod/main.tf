# NOT YET APPLIED. The live production service is the hand-built instance
# i-073f87a2121c96159 with EIP 3.149.38.210, which this configuration does not
# describe. Applying as-is would build a *parallel* production stack, not adopt
# the existing one.
#
# Two ways forward, both documented in ../../README.md:
#   A. Parallel build + EIP cutover (recommended) -- stand this up on a
#      temporary hostname, verify, then move the DNS record. Matches the
#      zero-downtime procedure already in notes/first_steps_to_deploy.md.
#   B. terraform import -- adopt the running instance, EIP and DNS record into
#      state. Cheaper but the existing box was built by launch-wizard in the
#      default VPC, so the VPC/subnet/SG resources here will never match it.
#
# Validate everything on sandbox first.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "riverst"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-2"
}

variable "certbot_email" {
  type = string
}

variable "alarm_email" {
  type    = string
  default = ""
}

variable "hostname" {
  description = "Set to a staging hostname for the parallel build, then cut over."
  type        = string
  default     = "play.kivaproject.org"
}

module "prod" {
  source = "../../modules/riverst-env"

  environment = "prod"
  vpc_cidr    = "10.10.0.0/16"
  hostname    = var.hostname

  # Matches the current production instance exactly.
  instance_type  = "c6i.2xlarge"
  root_volume_gb = 64
  compute_device = "cpu"

  # Production tracks a tag, never a moving branch.
  git_ref = "main"

  certbot_email = var.certbot_email
  alarm_email   = var.alarm_email

  # On: prod runs continuously, so a missing status check is a real signal.
  enable_monitoring = true

  # Production runs continuously.
  enable_scheduled_shutdown = false

  snapshot_retain_count = 14
}

output "url" { value = module.prod.url }
output "public_ip" { value = module.prod.public_ip }
output "instance_id" { value = module.prod.instance_id }
output "ssm_parameter_prefix" { value = module.prod.ssm_parameter_prefix }
output "session_command" { value = module.prod.session_command }

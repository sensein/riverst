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
      Environment = "sandbox"
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

module "sandbox" {
  source = "../../modules/riverst-env"

  environment = "sandbox"
  vpc_cidr    = "10.20.0.0/16"
  hostname    = "sandbox.kivaproject.org"

  # Half the vCPU of prod at ~55% of the cost; adequate for development.
  instance_type  = "m6i.xlarge"
  root_volume_gb = 64
  # Sandbox tracks its own branch so it can run changes before they reach main.
  git_ref        = "sandbox"
  compute_device = "cpu"

  certbot_email = var.certbot_email

  # Off: this environment is stopped every night on purpose, which the
  # status-check alarm would otherwise report as a failure.
  enable_monitoring = false

  # Up 07:00-00:00 America/New_York, every day including weekends. Testers
  # hitting a dead site with no explanation is worse than the extra uptime cost.
  # Expressed in a real timezone, not UTC, so these local times survive the
  # daylight saving change on 1 November instead of shifting by an hour.
  enable_scheduled_shutdown = true
  schedule_timezone         = "America/New_York"
  startup_cron              = "cron(0 7 ? * * *)" # 07:00 ET daily
  shutdown_cron             = "cron(0 0 ? * * *)" # 00:00 ET (midnight) daily

  # Shorter retention than prod: this data is disposable.
  snapshot_retain_count = 3

  # Durable off-instance copy of session transcripts (specs/009-sandbox-s3-transcripts).
  enable_transcript_storage = true
}

output "url" { value = module.sandbox.url }
output "public_ip" { value = module.sandbox.public_ip }
output "instance_id" { value = module.sandbox.instance_id }
output "ssm_parameter_prefix" { value = module.sandbox.ssm_parameter_prefix }
output "session_command" { value = module.sandbox.session_command }
output "transcripts_bucket" { value = module.sandbox.transcripts_bucket }

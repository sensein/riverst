terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

locals {
  name = "${var.project}-${var.environment}"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Module      = "riverst-env"
  }

  # Parameter Store prefix holding this environment's application secrets.
  # Terraform creates the parameters but never owns their values.
  ssm_prefix = "/${var.project}/${var.environment}"
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# Canonical's published pointer to the current Ubuntu 24.04 AMI, matching the
# noble-24.04 image the existing production instance runs.
data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

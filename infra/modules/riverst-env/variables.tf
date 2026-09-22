variable "environment" {
  description = "Environment name. Used in every resource name and as the Environment tag."
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]{2,16}$", var.environment))
    error_message = "environment must be lowercase alphanumeric/dashes, 2-16 chars."
  }
}

variable "project" {
  description = "Project tag applied to all resources."
  type        = string
  default     = "riverst"
}

variable "vpc_cidr" {
  description = "CIDR for this environment's dedicated VPC. Must not overlap other envs."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type. c6i.2xlarge for prod, m6i.xlarge is adequate for sandbox."
  type        = string
  default     = "m6i.xlarge"
}

variable "root_volume_gb" {
  description = "Root EBS volume size in GiB. 64 matches the current production box."
  type        = number
  default     = 64
}

variable "hostname" {
  description = "Fully qualified hostname to serve, e.g. sandbox.kivaproject.org."
  type        = string
}

variable "route53_zone_name" {
  description = "Existing Route 53 public hosted zone (with trailing dot), e.g. kivaproject.org."
  type        = string
  default     = "kivaproject.org"
}

variable "certbot_email" {
  description = "Contact email for Let's Encrypt expiry notices."
  type        = string
}

variable "git_repo" {
  description = "Riverst git repository to deploy from."
  type        = string
  default     = "https://github.com/sensein/riverst.git"
}

variable "git_ref" {
  description = "Branch or tag to check out. Pin prod to a tag; sandbox can track main."
  type        = string
  default     = "main"
}

variable "ssh_ingress_cidrs" {
  description = <<-EOT
    CIDRs allowed to reach port 22. Defaults to empty: SSM Session Manager is the
    intended access path and needs no inbound rule. Only populate this for a
    specific trusted range, never 0.0.0.0/0.
  EOT
  type        = list(string)
  default     = []
  validation {
    condition     = !contains(var.ssh_ingress_cidrs, "0.0.0.0/0")
    error_message = "Refusing 0.0.0.0/0 on port 22. Use SSM Session Manager instead."
  }
}

variable "compute_device" {
  description = "RIVERST_COMPUTE_DEVICE for the server process."
  type        = string
  default     = "cpu"
}

variable "snapshot_retain_count" {
  description = "How many daily EBS snapshots of the root volume to retain."
  type        = number
  default     = 7
}

variable "snapshot_time_utc" {
  description = "Daily snapshot start time, UTC, HH:MM."
  type        = string
  default     = "07:00"
}

variable "alarm_email" {
  description = "Email subscribed to the CloudWatch alarm SNS topic. Empty disables the subscription."
  type        = string
  default     = ""
}

variable "enable_scheduled_shutdown" {
  description = "Stop the instance nightly and start it each weekday morning. Intended for sandbox."
  type        = bool
  default     = false
}

variable "schedule_timezone" {
  description = <<-EOT
    IANA timezone the power schedules are interpreted in. Using a real zone
    rather than UTC means the local start/stop times stay put across daylight
    saving transitions instead of silently shifting by an hour.
  EOT
  type        = string
  default     = "UTC"
}

variable "shutdown_cron" {
  description = "EventBridge cron for stopping the instance, in schedule_timezone."
  type        = string
  default     = "cron(0 1 ? * * *)"
}

variable "startup_cron" {
  description = "EventBridge cron for starting the instance, in schedule_timezone."
  type        = string
  default     = "cron(0 11 ? * MON-FRI *)"
}

variable "enable_monitoring" {
  description = <<-EOT
    Create the SNS topic and CloudWatch alarms. Off by default: on an environment
    with enable_scheduled_shutdown the status-check alarm treats the nightly
    stop as missing data and would page every night. Turn on for always-on
    environments such as prod.
  EOT
  type        = bool
  default     = false
}

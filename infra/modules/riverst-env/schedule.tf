# Replaces the two hand-made Lambdas (trigger_riverst / stop_riverst), which had
# a hardcoded instance ID and no EventBridge rule attached -- so they only ever
# ran when somebody clicked Test in the console.
#
# Enabled for sandbox, off for prod. A sandbox stopped ~14h/day and all weekend
# costs roughly a third of one running continuously.

resource "aws_scheduler_schedule_group" "this" {
  count = var.enable_scheduled_shutdown ? 1 : 0
  name  = "${local.name}-power"
  tags  = local.tags
}

resource "aws_iam_role" "scheduler" {
  count = var.enable_scheduled_shutdown ? 1 : 0
  name  = "${local.name}-scheduler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "scheduler" {
  count = var.enable_scheduled_shutdown ? 1 : 0
  name  = "${local.name}-scheduler"
  role  = aws_iam_role.scheduler[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ec2:StartInstances", "ec2:StopInstances"]
      Resource = "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:instance/${aws_instance.app.id}"
    }]
  })
}

resource "aws_scheduler_schedule" "stop" {
  count                        = var.enable_scheduled_shutdown ? 1 : 0
  name                         = "${local.name}-stop"
  group_name                   = aws_scheduler_schedule_group.this[0].name
  schedule_expression          = var.shutdown_cron_utc
  schedule_expression_timezone = "UTC"
  flexible_time_window { mode = "OFF" }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:ec2:stopInstances"
    role_arn = aws_iam_role.scheduler[0].arn
    input    = jsonencode({ InstanceIds = [aws_instance.app.id] })
  }
}

resource "aws_scheduler_schedule" "start" {
  count                        = var.enable_scheduled_shutdown ? 1 : 0
  name                         = "${local.name}-start"
  group_name                   = aws_scheduler_schedule_group.this[0].name
  schedule_expression          = var.startup_cron_utc
  schedule_expression_timezone = "UTC"
  flexible_time_window { mode = "OFF" }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:ec2:startInstances"
    role_arn = aws_iam_role.scheduler[0].arn
    input    = jsonencode({ InstanceIds = [aws_instance.app.id] })
  }
}

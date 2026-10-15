# The account currently has no alarms at all: if production stops responding,
# the first signal is a user complaining.

resource "aws_sns_topic" "alarms" {
  count = var.enable_monitoring ? 1 : 0
  name  = "${local.name}-alarms"
  tags = local.tags
}

resource "aws_sns_topic_subscription" "alarm_email" {
  count     = var.enable_monitoring && var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "status_check" {
  count               = var.enable_monitoring ? 1 : 0
  alarm_name          = "${local.name}-status-check-failed"
  alarm_description   = "EC2 or system status check failing for Riverst ${var.environment}"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "breaching"
  dimensions          = { InstanceId = aws_instance.app.id }
  alarm_actions       = [aws_sns_topic.alarms[0].arn]
  ok_actions          = [aws_sns_topic.alarms[0].arn]
  tags                = local.tags
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  count               = var.enable_monitoring ? 1 : 0
  alarm_name          = "${local.name}-cpu-high"
  alarm_description   = "Sustained high CPU -- speech pipeline may be saturated"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 85
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions          = { InstanceId = aws_instance.app.id }
  alarm_actions       = [aws_sns_topic.alarms[0].arn]
  tags                = local.tags
}

# Root volume filling up is a real risk: sessions and uploads accumulate on disk
# with nothing rotating them. Requires the CloudWatch agent, which the instance
# role already permits.
resource "aws_cloudwatch_metric_alarm" "disk_high" {
  count               = var.enable_monitoring ? 1 : 0
  alarm_name          = "${local.name}-disk-high"
  alarm_description   = "Root filesystem above 80% -- session data and uploads accumulate here"
  namespace           = "CWAgent"
  metric_name         = "disk_used_percent"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "missing"
  dimensions = {
    InstanceId = aws_instance.app.id
    path       = "/"
    fstype     = "ext4"
  }
  alarm_actions = [aws_sns_topic.alarms[0].arn]
  tags          = local.tags
}

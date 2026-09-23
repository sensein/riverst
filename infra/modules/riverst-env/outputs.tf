output "instance_id" {
  description = "EC2 instance ID. Connect with: aws ssm start-session --target <id>"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Elastic IP. Stable across instance replacement."
  value       = aws_eip.app.public_ip
}

output "url" {
  description = "Environment URL."
  value       = "https://${var.hostname}"
}

output "vpc_id" {
  value = aws_vpc.this.id
}

output "security_group_id" {
  value = aws_security_group.app.id
}

output "ssm_parameter_prefix" {
  description = "Populate the secrets under this prefix before the app will work."
  value       = local.ssm_prefix
}

output "alarm_topic_arn" {
  description = "Null when enable_monitoring is false."
  value       = one(aws_sns_topic.alarms[*].arn)
}

output "session_command" {
  description = "Shell access without an open SSH port."
  value       = "aws ssm start-session --target ${aws_instance.app.id} --region ${data.aws_region.current.name}"
}

output "transcripts_bucket" {
  description = "Empty string when enable_transcript_storage is false."
  value       = var.enable_transcript_storage ? aws_s3_bucket.transcripts[0].id : ""
}

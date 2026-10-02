# The current instances have no instance profile at all, which is why port 22 is
# open to the world and secrets live in a .env on disk. This role gives the box
# SSM Session Manager access plus read-only access to its own environment's
# parameters -- and nothing from any other environment.

resource "aws_iam_role" "instance" {
  name = "${local.name}-instance"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cw_agent" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

data "aws_iam_policy_document" "instance_secrets" {
  statement {
    sid    = "ReadOwnEnvironmentParameters"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_prefix}",
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_prefix}/*",
    ]
  }

  statement {
    sid       = "DecryptOwnParameters"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["arn:aws:kms:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:alias/aws/ssm"]
  }
}

resource "aws_iam_role_policy" "instance_secrets" {
  name   = "${local.name}-read-own-parameters"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.instance_secrets.json
}

resource "aws_iam_instance_profile" "instance" {
  name = "${local.name}-instance"
  role = aws_iam_role.instance.name
  tags = local.tags
}

# Scoped to exactly this environment's own transcript bucket -- same
# least-privilege shape as instance_secrets above. GetObject is included
# alongside PutObject so a future read-side tool doesn't need a second IAM
# change; it costs nothing extra on this one object prefix.
data "aws_iam_policy_document" "transcript_upload" {
  count = var.enable_transcript_storage ? 1 : 0

  statement {
    sid    = "ReadWriteOwnTranscripts"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
    ]
    resources = ["${aws_s3_bucket.transcripts[0].arn}/*"]
  }
}

resource "aws_iam_role_policy" "transcript_upload" {
  count  = var.enable_transcript_storage ? 1 : 0
  name   = "${local.name}-transcript-upload"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.transcript_upload[0].json
}

# Dedicated bucket for this environment's session transcripts (see
# bot/components/transcript_uploader.py). Off by default -- only sandbox
# turns this on today. Mirrors infra/bootstrap/main.tf's state bucket:
# private, encrypted, no public access under any circumstance.

resource "aws_s3_bucket" "transcripts" {
  count  = var.enable_transcript_storage ? 1 : 0
  bucket = "riverst-${var.environment}-transcripts-${data.aws_caller_identity.current.account_id}"
  tags   = merge(local.tags, { Name = "${local.name}-transcripts" })
}

resource "aws_s3_bucket_versioning" "transcripts" {
  count  = var.enable_transcript_storage ? 1 : 0
  bucket = aws_s3_bucket.transcripts[0].id
  versioning_configuration {
    # Off on purpose: a re-uploaded transcript for the same session is an
    # intentional replace (FR-008), not history worth keeping.
    status = "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "transcripts" {
  count  = var.enable_transcript_storage ? 1 : 0
  bucket = aws_s3_bucket.transcripts[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "transcripts" {
  count                   = var.enable_transcript_storage ? 1 : 0
  bucket                  = aws_s3_bucket.transcripts[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

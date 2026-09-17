resource "aws_eip" "app" {
  domain = "vpc"
  tags   = merge(local.tags, { Name = "${local.name}-eip" })

  # Deliberately no prevent_destroy: lifecycle blocks cannot be conditional on a
  # variable, and sandbox must stay destroyable. Protect the prod EIP instead
  # with `terraform state` care or an SCP -- the DNS cutover procedure in
  # notes/first_steps_to_deploy.md depends on that address never changing.
}

resource "aws_instance" "app" {
  ami                    = data.aws_ssm_parameter.ubuntu.value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name

  root_block_device {
    volume_size           = var.root_volume_gb
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = false # session data and uploads live here
    tags                  = merge(local.tags, { Name = "${local.name}-root" })
  }

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 1
  }

  user_data_replace_on_change = false
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    hostname        = var.hostname
    certbot_email   = var.certbot_email
    git_repo        = var.git_repo
    git_ref         = var.git_ref
    compute_device  = var.compute_device
    ssm_prefix      = local.ssm_prefix
    aws_region      = data.aws_region.current.name
    environment     = var.environment
  })

  tags = merge(local.tags, { Name = "${local.name}" })

  lifecycle {
    # Changing the AMI pointer should not silently replace a running instance
    # holding the only copy of the session data. user_data is ignored too: it
    # only executes at first boot, and letting Terraform "update" it would stop
    # and start the instance to no effect. New instances get the current
    # template; existing ones are re-bootstrapped by hand.
    ignore_changes = [ami, user_data]
  }

  # DNS must already resolve to the EIP before user_data runs certbot.
  depends_on = [aws_route53_record.app]
}

resource "aws_eip_association" "app" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.app.id
}

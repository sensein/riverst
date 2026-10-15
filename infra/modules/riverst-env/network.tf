# Each environment gets its own VPC so a sandbox mistake cannot touch production
# networking. Single public subnet with a direct IGW route: the WebRTC media path
# needs a public address on the host itself, so there is nothing for a NAT gateway
# to do here (and it would add ~$33/mo per environment).

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "${local.name}-vpc" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.name}-igw" })
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, 0)
  availability_zone       = "${data.aws_region.current.name}a"
  # Must be true: user_data needs egress (apt, git, pip, npm) at boot, and the
  # Elastic IP is not associated until after the instance is created. The EIP
  # association then replaces this auto-assigned address.
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "${local.name}-public-a" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(local.tags, { Name = "${local.name}-public-rt" })
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "Riverst ${var.environment}: HTTPS, HTTP redirect, and WebRTC media"
  vpc_id      = aws_vpc.this.id
  tags        = merge(local.tags, { Name = "${local.name}-app" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.app.id
  description       = "HTTPS app and signalling"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
  tags              = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.app.id
  description       = "HTTP: redirect to HTTPS and ACME http-01 challenge"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
  tags              = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "turn" {
  security_group_id = aws_security_group.app.id
  description       = "coturn STUN/TURN"
  ip_protocol       = "udp"
  from_port         = 3478
  to_port           = 3478
  cidr_ipv4         = "0.0.0.0/0"
  tags              = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "turn_tcp" {
  security_group_id = aws_security_group.app.id
  description       = "coturn TCP fallback for restrictive networks"
  ip_protocol       = "tcp"
  from_port         = 3478
  to_port           = 3478
  cidr_ipv4         = "0.0.0.0/0"
  tags              = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "webrtc_media" {
  security_group_id = aws_security_group.app.id
  description       = "WebRTC media: peer-to-peer UDP direct to this host"
  ip_protocol       = "udp"
  from_port         = 10000
  to_port           = 65535
  cidr_ipv4         = "0.0.0.0/0"
  tags              = local.tags
}

# Present only when explicitly configured. SSM Session Manager is the default
# access path and requires no inbound rule at all.
resource "aws_vpc_security_group_ingress_rule" "ssh" {
  for_each          = toset(var.ssh_ingress_cidrs)
  security_group_id = aws_security_group.app.id
  description       = "SSH from trusted range"
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = each.value
  tags              = local.tags
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.app.id
  description       = "All egress: OpenAI APIs, package repos, ACME"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  tags              = local.tags
}

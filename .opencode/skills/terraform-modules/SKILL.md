---
name: terraform-modules
type: skill
description: Design reusable, well-tested Terraform modules with cloud-agnostic interfaces and safe state management.
related-rules:
  - iac-standards.md
  - state-management.md
  - secret-hygiene.md
allowed-tools: Read, Write, Edit, Bash
agentic:
  generated_by: agentic
  source: "areas/devops/infrastructure/skills/terraform-modules/SKILL.md"
  repository: "https://github.com/sawrus/agent-guides"
---

# Skill: Terraform Modules

> **Expertise:** Reusable module design, for_each patterns, remote state, data sources, module testing with Terratest.

## When to load

When writing new Terraform, reviewing IaC PRs, designing module interfaces, or debugging plan/apply failures.

## Module Interface Design

```hcl
# variables.tf — define a clean, minimal interface
variable "project" {
  description = "Project name used in resource naming and tags"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev|staging|production)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be dev, staging, or production."
  }
}

variable "instance_count" {
  description = "Number of instances to create"
  type        = number
  default     = 1
}

# outputs.tf — expose only what callers need
output "instance_ids" {
  description = "List of created instance IDs"
  value       = aws_instance.this[*].id
}

output "private_ips" {
  description = "Private IP addresses"
  value       = aws_instance.this[*].private_ip
  sensitive   = false
}
```

## for_each vs count

```hcl
# ✅ for_each — stable keys, safe to add/remove
resource "aws_security_group_rule" "allow" {
  for_each    = var.allowed_ports   # map: { "http" = 80, "https" = 443 }
  type        = "ingress"
  from_port   = each.value
  to_port     = each.value
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}

# ❌ count — index-based, removing item N shifts all subsequent items
resource "aws_instance" "this" {
  count = var.instance_count   # removing instance 0 destroys ALL and recreates
}

# ✅ for_each with map for instances
resource "aws_instance" "this" {
  for_each      = var.instances   # map: { "web-1" = {...}, "web-2" = {...} }
  instance_type = each.value.instance_type
}
```

## Dynamic Blocks

```hcl
resource "aws_security_group" "this" {
  name = "${var.project}-${var.environment}-sg"

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}
```

## Data Sources (cloud-agnostic patterns)

```hcl
# Latest Ubuntu 22.04 AMI (AWS)
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# Cross-stack reference via SSM (avoid terraform_remote_state across envs)
data "aws_ssm_parameter" "vpc_id" {
  name = "/${var.environment}/network/vpc_id"
}
```

## Locals for DRY Code

```hcl
locals {
  name_prefix = "${var.project}-${var.environment}"
  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = var.owner
  }
}

resource "aws_s3_bucket" "this" {
  bucket = "${local.name_prefix}-assets-${random_id.suffix.hex}"
  tags   = local.common_tags
}
```

## moved Block (safe refactoring)

```hcl
# When renaming a resource — prevents destroy+create
moved {
  from = aws_instance.web
  to   = aws_instance.this["web-1"]
}
```

## CI/CD Integration

```bash
# Standard pipeline steps
terraform init -backend-config=environments/${ENV}/backend.hcl
terraform validate
terraform fmt -check -recursive
terraform plan -var-file=environments/${ENV}/terraform.tfvars -out=tfplan
# After approval:
terraform apply tfplan
```

## Anti-Patterns

| Anti-pattern | Fix |
|:---|:---|
| `count` for multi-instance | Use `for_each` with map keys |
| Hardcoded region/AZ | Use `data` source or variable |
| `?ref=main` module source | Pin to version tag |
| Provider config inside module | Provider in root module only |
| `terraform_remote_state` across envs | SSM / Consul KV for cross-stack values |
| Sensitive values in outputs without `sensitive=true` | Mark all secret outputs as sensitive |

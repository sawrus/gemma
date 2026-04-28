---
name: state-management
type: skill
description: Manage Terraform remote state — backend setup, state isolation, locking, import, mv, and state surgery.
related-rules:
  - state-management.md
  - iac-standards.md
allowed-tools: Read, Write, Edit, Bash
agentic:
  generated_by: agentic
  source: "areas/devops/infrastructure/skills/state-management/SKILL.md"
  repository: "https://github.com/sawrus/agent-guides"
---

# Skill: Terraform State Management

> **Expertise:** Remote backends, state isolation, import, mv, rm, state surgery, cross-stack references.

## When to load

When setting up a new Terraform backend, debugging state lock, importing manually-created resources, or safely moving resources between state files.

## Backend Setup Patterns

```hcl
# AWS S3 + DynamoDB lock
terraform {
  backend "s3" {
    bucket         = "mycompany-terraform-state"
    key            = "${var.environment}/${var.component}/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    kms_key_id     = "alias/terraform-state"
    dynamodb_table = "terraform-state-lock"
  }
}

# GCS (GCP) — built-in locking, no separate lock table needed
terraform {
  backend "gcs" {
    bucket = "mycompany-terraform-state"
    prefix = "${var.environment}/${var.component}"
  }
}

# Terraform Cloud / HCP Terraform
terraform {
  cloud {
    organization = "mycompany"
    workspaces { name = "production-network" }
  }
}
```

## State Isolation (per environment × component)

```
state/
├── staging/
│   ├── network/terraform.tfstate
│   ├── k8s-cluster/terraform.tfstate
│   └── databases/terraform.tfstate
└── production/
    ├── network/terraform.tfstate
    ├── k8s-cluster/terraform.tfstate
    └── databases/terraform.tfstate
```

**Rule**: Staging and production **must** use separate state files (separate key/prefix, ideally separate bucket).

## Cross-Stack Values (avoid `terraform_remote_state`)

```hcl
# ✅ Publish outputs to SSM Parameter Store
resource "aws_ssm_parameter" "vpc_id" {
  name  = "/${var.environment}/network/vpc_id"
  type  = "String"
  value = aws_vpc.this.id
}

# ✅ Consume in another stack via data source
data "aws_ssm_parameter" "vpc_id" {
  name = "/${var.environment}/network/vpc_id"
}

resource "aws_subnet" "app" {
  vpc_id = data.aws_ssm_parameter.vpc_id.value
}
```

## State Import (bring unmanaged resource under TF control)

```bash
# 1. Write the resource block in .tf first
resource "aws_s3_bucket" "legacy" {
  bucket = "my-legacy-bucket"
}

# 2. Import the existing resource
terraform import aws_s3_bucket.legacy my-legacy-bucket

# 3. Run plan — should show no changes if .tf matches reality
terraform plan   # should be: "No changes."
```

## State Move (rename / reorganize)

```hcl
# Safe rename using moved{} block (Terraform 1.1+) — no CLI required
moved {
  from = aws_instance.web
  to   = aws_instance.this["web-01"]
}

# After apply, remove the moved{} block
```

```bash
# Manual state mv (use when moved{} block is not applicable)
# ALWAYS take a backup first
terraform state pull > backup-$(date +%Y%m%d-%H%M%S).tfstate

terraform state mv \
  'aws_security_group.old_name' \
  'aws_security_group.new_name'
```

## State Surgery (break-glass commands)

```bash
# List all resources in state
terraform state list

# Show a specific resource's state
terraform state show 'aws_instance.this["web-01"]'

# Remove a resource from state WITHOUT destroying it (use when managed outside TF)
terraform state rm 'aws_s3_bucket.legacy'

# Force-unlock a stuck state lock (use only when lock is genuinely stale)
terraform force-unlock <LOCK_ID>
# Lock ID from error message: "Error acquiring the state lock"

# Pull state for manual inspection
terraform state pull | jq '.resources[] | {type: .type, name: .name}'

# Replace a resource (force-recreate without destroy first)
terraform apply -replace='aws_instance.this["web-01"]'
```

## Debugging Lock Issues

```bash
# Error: "Error acquiring the state lock" + lock ID
# Check DynamoDB for stale lock:
aws dynamodb get-item \
  --table-name terraform-state-lock \
  --key '{"LockID": {"S": "mycompany-terraform-state/production/network/terraform.tfstate"}}'

# Verify no apply is actually running before force-unlock
# Only force-unlock if you are certain no other process holds the lock
terraform force-unlock <LOCK_ID_FROM_ERROR>
```

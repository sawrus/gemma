---
agentic:
  generated_by: agentic
  source: "areas/devops/infrastructure/rules/iac-standards.md"
  repository: "https://github.com/sawrus/agent-guides"
---
# Rule: IaC Standards

**Priority**: P0 — IaC violations block infrastructure changes.

## Terraform

1. **All infrastructure is code**
   - Every production resource must have a corresponding Terraform resource.
   - Resources created outside Terraform are subject to automated removal within 7 days.
   - Exception process: emergency manual change → IaC PR within 24 hours.

2. **Module structure**
   ```
   terraform/
   ├── modules/           ← reusable, generic (no env-specific values)
   │   ├── vpc/
   │   ├── eks-cluster/ or k8s-node-pool/
   │   ├── rds-postgres/
   │   └── object-storage/
   └── environments/
       ├── staging/       ← tfvars + backend config
       └── production/    ← tfvars + backend config
   ```

3. **Version pinning — mandatory**
   ```hcl
   terraform {
     required_version = ">= 1.9, < 2.0"
     required_providers {
       aws = { source = "hashicorp/aws", version = "~> 5.50" }
     }
   }
   # Module references: use version tags, never ?ref=main in production
   module "vpc" {
     source  = "git::https://git.example.com/infra/modules//vpc?ref=v1.4.2"
   }
   ```

4. **Naming convention**
   ```hcl
   # pattern: {project}-{environment}-{resource}-{optional-suffix}
   name = "${var.project}-${var.environment}-${var.name}"
   # e.g. myapp-production-postgres-primary
   ```

5. **Mandatory tags on every resource**
   ```hcl
   locals {
     common_tags = {
       Project     = var.project
       Environment = var.environment
       ManagedBy   = "terraform"
       Owner       = var.team_name
       CostCenter  = var.cost_center
     }
   }
   ```

## Ansible

6. **Idempotency required** — every task must be safe to run multiple times with identical outcome.

7. **Roles structure**
   ```
   roles/
   └── my-role/
       ├── tasks/main.yml
       ├── defaults/main.yml   ← all variables with safe defaults
       ├── vars/main.yml       ← internal constants
       ├── templates/
       ├── handlers/main.yml
       └── meta/main.yml       ← dependencies declared
   ```

8. **No inline secrets** — use `ansible-vault` or reference from HashiCorp Vault / environment variables. Plain-text secrets in playbooks or vars files are a P0 violation.

## Universal

9. **Peer review required for all IaC changes** — `terraform plan` output attached to PR; `ansible-lint` must pass.
10. **Dry-run before apply** — `terraform plan` / `--check` mode reviewed and approved; never skip in CI.

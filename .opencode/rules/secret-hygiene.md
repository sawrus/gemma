---
agentic:
  generated_by: agentic
  source: "areas/devops/infrastructure/rules/secret-hygiene.md"
  repository: "https://github.com/sawrus/agent-guides"
---
# Rule: Secret Hygiene in IaC

**Priority**: P0 — Secrets in IaC code or state are treated as compromised immediately.

## Forbidden Patterns

1. **No secrets in `.tf` files or `tfvars`**
   ```hcl
   # ❌ NEVER
   resource "aws_db_instance" "this" {
     password = "mypassword123"
   }

   # ✅ Read from Secrets Manager at plan/apply time
   data "aws_secretsmanager_secret_value" "db_password" {
     secret_id = "/${var.environment}/postgres/password"
   }
   resource "aws_db_instance" "this" {
     password = data.aws_secretsmanager_secret_value.db_password.secret_string
   }
   ```

2. **No secrets in Ansible vars, inventory, or group_vars without vault encryption**
   ```yaml
   # ❌ NEVER in plain-text
   db_password: supersecret

   # ✅ Ansible Vault encrypted
   db_password: !vault |
     $ANSIBLE_VAULT;1.1;AES256
     ...
   ```

3. **No `sensitive = false` overrides** — sensitive Terraform outputs stay sensitive.

## Required Patterns

4. **Secret injection at runtime, not provision time**
   - Preferred: External Secrets Operator pulls from Vault/SM into K8s Secrets at pod start.
   - Acceptable: `terraform apply` reads from SM/Vault, writes to K8s secret as part of bootstrap.
   - Never: secrets in container environment variables set from Terraform string literals.

5. **State file protection** — state may contain sensitive values; always encrypt (see state-management.md).

6. **Pre-commit secret scanning** — `git-secrets` or `trufflehog` pre-commit hook required on infra repos.

## Incident Response

If a secret is found in Git history:
1. Rotate the secret immediately (before anything else).
2. Remove from history: `git filter-repo` + force push.
3. Audit access logs for the exposed secret.
4. File security incident report.

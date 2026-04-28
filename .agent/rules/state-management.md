---
agentic:
  generated_by: agentic
  source: "areas/devops/infrastructure/rules/state-management.md"
  repository: "https://github.com/sawrus/agent-guides"
---
# Rule: State Management

**Priority**: P0 — State corruption or conflicts can cause catastrophic resource deletion.

## Remote State (mandatory for all non-local environments)

1. **Backend configuration**
   ```hcl
   # AWS
   terraform {
     backend "s3" {
       bucket         = "${project}-terraform-state"
       key            = "${environment}/${component}/terraform.tfstate"
       region         = "us-east-1"
       encrypt        = true
       kms_key_id     = "arn:aws:kms:..."
       dynamodb_table = "terraform-state-lock"
     }
   }

   # GCS (GCP)
   terraform {
     backend "gcs" {
       bucket = "${project}-terraform-state"
       prefix = "${environment}/${component}"
     }
   }
   ```

2. **State isolation by environment AND component**
   - One state file per `environment/component` (not one global state).
   - Staging and production MUST use separate backends (separate buckets/prefix).
   - Never share state between environments.

3. **State locking** — DynamoDB (AWS) or GCS built-in locking must be enabled. Never disable locking.

4. **No `terraform_remote_state` across environment boundaries**
   - Cross-stack values shared via SSM Parameter Store, Consul KV, or environment-specific outputs file.

## State File Security

5. **State contains secrets** — treat state files with the same security as production secrets:
   - S3 bucket: versioning enabled, public access blocked, KMS encryption.
   - GCS: uniform bucket-level access, CMEK encryption.
   - Access: only CI/CD pipeline roles and on-call engineers (MFA required for humans).

6. **State file backup** — versioned storage satisfies this; never manually delete old versions.

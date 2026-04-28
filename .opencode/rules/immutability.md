---
agentic:
  generated_by: agentic
  source: "areas/devops/infrastructure/rules/immutability.md"
  repository: "https://github.com/sawrus/agent-guides"
---
# Rule: Immutable Infrastructure

**Priority**: P0 — Manual changes to running infrastructure are a critical policy violation.

## Core Constraints

1. **No SSH patching of running servers** — the fix is a new image + redeploy, not in-place modification.

2. **Terraform is the single source of truth** — cloud console, CLI, or SDK changes that bypass Terraform are forbidden in production. Drift = violation.

3. **Immutable image tags** — container images in production always reference content-addressed digest (`image@sha256:...`), never `:latest` or mutable tags.

4. **Module versioning** — all Terraform module references pinned to semantic version tags. `?ref=main` is forbidden in staging and production.

5. **Emergency exception process**
   - Manual change allowed only for P0 incidents.
   - Requires: Slack announcement + ticket + on-call sign-off.
   - IaC PR to codify the change must be merged within **24 hours**.
   - Recurring manual changes for the same resource = architecture review required.

## Drift Policy

6. **Drift detection runs every 6 hours** via CI scheduled job (`terraform plan`).
7. **Detected drift classifications:**
   - `ACCEPT`: approved architectural exception (documented in PR) → suppress alert
   - `REMEDIATE`: unintended change → create ticket, remediate within 48h
   - `INVESTIGATE`: unknown origin → P1 incident, may indicate unauthorized access
8. **Drift in production security groups or IAM** → automatic P1 incident regardless of size.

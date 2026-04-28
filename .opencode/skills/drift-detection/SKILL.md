---
name: drift-detection
type: skill
description: Detect, classify, and automate Terraform drift detection in CI — scheduled plans, drift metrics, cloud-native audit log correlation.
related-rules:
  - immutability.md
  - iac-standards.md
allowed-tools: Read, Write, Edit, Bash
agentic:
  generated_by: agentic
  source: "areas/devops/infrastructure/skills/drift-detection/SKILL.md"
  repository: "https://github.com/sawrus/agent-guides"
---

# Skill: Drift Detection

> **Expertise:** Terraform plan-based drift detection, CI scheduling, cloud audit log correlation, drift classification.

## When to load

When setting up scheduled drift detection, investigating detected drift, or correlating drift with cloud audit events.

## Scheduled Drift Detection (GitHub Actions)

```yaml
# .github/workflows/drift-detection.yml
name: Drift Detection

on:
  schedule:
    - cron: '0 */6 * * *'   # every 6 hours
  workflow_dispatch:          # manual trigger

jobs:
  detect-drift:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        component: [network, k8s-cluster, databases, iam-roles]
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.DRIFT_DETECTOR_ROLE_ARN }}
          aws-region: eu-west-1

      - name: Terraform init
        working-directory: terraform/environments/production/${{ matrix.component }}
        run: terraform init -backend-config=backend.hcl

      - name: Terraform plan (drift check)
        id: plan
        working-directory: terraform/environments/production/${{ matrix.component }}
        run: |
          terraform plan \
            -var-file=terraform.tfvars \
            -detailed-exitcode \
            -out=drift-check.plan \
            2>&1 | tee drift-output.txt
          echo "exit_code=$?" >> $GITHUB_OUTPUT
        continue-on-error: true    # exit 2 = changes, don't fail job

      - name: Classify drift
        if: steps.plan.outputs.exit_code == '2'
        run: |
          # Check for security-sensitive resource changes
          if grep -E "aws_iam|aws_security_group|aws_kms|encryption" drift-output.txt; then
            echo "SEVERITY=INVESTIGATE" >> $GITHUB_ENV
          else
            echo "SEVERITY=REMEDIATE" >> $GITHUB_ENV
          fi

      - name: Create GitHub Issue on drift
        if: steps.plan.outputs.exit_code == '2'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const plan = fs.readFileSync('terraform/environments/production/${{ matrix.component }}/drift-output.txt', 'utf8');
            await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `[DRIFT] ${{ matrix.component }} — ${process.env.SEVERITY}`,
              body: `## Drift detected in \`${{ matrix.component }}\`\n\n**Severity:** ${process.env.SEVERITY}\n\n\`\`\`\n${plan.slice(0, 3000)}\n\`\`\``,
              labels: ['infrastructure', 'drift', process.env.SEVERITY.toLowerCase()]
            });

      - name: Alert on INVESTIGATE drift
        if: env.SEVERITY == 'INVESTIGATE'
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {"text": "🚨 *INVESTIGATE drift* in `${{ matrix.component }}` — may indicate unauthorized change. <${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View>"}
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_ONCALL_WEBHOOK }}
```

## GitLab CI Scheduled Drift

```yaml
# .gitlab-ci.yml — drift detection job (triggered by schedule)
drift-detect:
  stage: audit
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  script:
    - cd terraform/environments/production/${COMPONENT}
    - terraform init -backend-config=backend.hcl
    - terraform plan -var-file=terraform.tfvars -detailed-exitcode
      -out=drift.plan 2>&1 | tee drift-output.txt || EXITCODE=$?
    - |
      if [ "${EXITCODE}" == "2" ]; then
        echo "DRIFT DETECTED in ${COMPONENT}"
        # Post to Slack, create MR, or alert via API
        curl -X POST "$SLACK_WEBHOOK" \
          -H 'Content-type: application/json' \
          --data "{\"text\":\"Drift in ${COMPONENT}\"}"
        exit 1
      fi
  parallel:
    matrix:
      - COMPONENT: [network, k8s-cluster, databases]
```

## Drift Classification Logic

```bash
# Parse terraform plan output for drift classification
classify_drift() {
  local plan_output="$1"

  # INVESTIGATE: security-sensitive resources changed
  if echo "$plan_output" | grep -qE \
    "aws_iam_policy|aws_security_group|kms_key|aws_s3_bucket_server_side_encryption|encryption_at_rest"; then
    echo "INVESTIGATE"
    return
  fi

  # INVESTIGATE: resources deleted unexpectedly
  if echo "$plan_output" | grep -q "# .* will be destroyed"; then
    echo "INVESTIGATE"
    return
  fi

  # REMEDIATE: configuration drift (non-security)
  echo "REMEDIATE"
}
```

## Correlating Drift with Cloud Audit Logs

```bash
# AWS CloudTrail: who changed the drifted resource?
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=<resource-id> \
  --start-time $(date -d '-24 hours' --iso-8601) \
  --query 'Events[*].{User: Username, Time: EventTime, Event: EventName}' \
  --output table

# GCP Audit Logs
gcloud logging read \
  'resource.type="gce_instance" AND protoPayload.methodName:"compute.instances"' \
  --freshness=24h \
  --format='table(timestamp, protoPayload.authenticationInfo.principalEmail, protoPayload.methodName)'
```

## Drift Suppression (accepted exceptions)

```hcl
# lifecycle ignore_changes for intentionally managed-outside-TF fields
resource "aws_autoscaling_group" "workers" {
  # ...
  lifecycle {
    ignore_changes = [
      desired_capacity,    # managed by cluster autoscaler, not TF
      min_size,
    ]
  }
}
```

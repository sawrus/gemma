---
name: cost-optimization
type: skill
description: Identify and reduce cloud infrastructure costs — right-sizing, reserved capacity, waste detection, tagging for cost attribution.
related-rules:
  - iac-standards.md
allowed-tools: Read, Write, Edit, Bash
agentic:
  generated_by: agentic
  source: "areas/devops/infrastructure/skills/cost-optimization/SKILL.md"
  repository: "https://github.com/sawrus/agent-guides"
---

# Skill: Cost Optimization

> **Expertise:** Cloud cost analysis, right-sizing recommendations, reserved/spot instances, tagging strategy, cost alerting.

## When to load

When investigating unexpectedly high cloud bills, right-sizing instances, or setting up cost attribution by team/environment.

## Mandatory Cost Tags (every resource)

```hcl
locals {
  cost_tags = {
    Project     = var.project      # e.g. "checkout"
    Environment = var.environment  # prod / staging / dev
    Team        = var.team         # e.g. "backend-team"
    CostCenter  = var.cost_center  # e.g. "eng-platform"
    ManagedBy   = "terraform"
  }
}
# Apply to every resource via merge(local.cost_tags, {...})
```

## AWS Cost Discovery

```bash
# Top 10 most expensive services this month
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[0].Groups | sort_by(@, &Metrics.BlendedCost.Amount) | reverse(@) | [:10]' \
  --output table

# Cost by tag (Team)
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=TAG,Key=Team

# Idle EC2 instances (< 5% CPU, last 2 weeks)
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=<instance-id> \
  --start-time $(date -d '-14 days' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 1209600 --statistics Average
```

## Right-Sizing Workflow

```bash
# Step 1: Get actual utilisation (Prometheus, last 7 days)
# CPU: avg and p99
avg(avg_over_time(instance:node_cpu_utilisation:rate5m[7d])) by (instance)
quantile_over_time(0.99, instance:node_cpu_utilisation:rate5m[7d])

# Memory: peak working set
max_over_time(node_memory_MemUsed_bytes[7d]) / node_memory_MemTotal_bytes

# Step 2: Recommendation formula
# New CPU = p99_cpu × 1.3 (30% headroom)
# New memory = peak_mem × 1.2 (20% headroom)

# Step 3: Find next smaller instance type
# AWS: use ec2-instance-selector
ec2-instance-selector --vcpus-min 2 --vcpus-max 4 \
  --memory-min 4 --memory-max 8 \
  --region eu-west-1 \
  --output table-wide
```

## Reserved / Spot Instances

```hcl
# Spot instances for non-critical worker nodes (60-80% savings)
resource "aws_launch_template" "workers" {
  instance_market_options {
    market_type = "spot"
    spot_options {
      max_price           = "0.10"      # cap to avoid surprise costs
      spot_instance_type  = "persistent"
      interruption_behavior = "terminate"
    }
  }
}

# Mixed: 70% spot, 30% on-demand for K8s node groups
resource "aws_autoscaling_group" "workers" {
  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 2    # always 2 on-demand
      on_demand_percentage_above_base_capacity = 30   # 30% on-demand, 70% spot
      spot_allocation_strategy                 = "capacity-optimized"
    }
  }
}
```

## Waste Detection Checklist

```bash
# Unattached EBS volumes
aws ec2 describe-volumes \
  --filters Name=status,Values=available \
  --query 'Volumes[*].{ID:VolumeId,Size:Size,Created:CreateTime}' \
  --output table

# Unused Elastic IPs
aws ec2 describe-addresses \
  --query 'Addresses[?AssociationId==null].{IP:PublicIp,AllocationId:AllocationId}'

# Old snapshots (> 90 days, no associated AMI)
aws ec2 describe-snapshots --owner-ids self \
  --query 'Snapshots[?StartTime<`2024-08-01`].{ID:SnapshotId,Size:VolumeSize,Date:StartTime}' \
  --output table

# Unused load balancers (0 healthy targets)
aws elbv2 describe-target-health \
  --target-group-arn <arn> \
  --query 'TargetHealthDescriptions[?TargetHealth.State==`unused`]'
```

## Cost Alerting (AWS Budgets)

```hcl
resource "aws_budgets_budget" "monthly_limit" {
  name         = "${var.project}-${var.environment}-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.billing_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "FORECASTED"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.billing_alert_email]
  }
}
```

## K8s Cost Visibility (Kubecost / OpenCost)

```bash
# Install OpenCost (open-source K8s cost allocation)
helm install opencost opencost/opencost -n opencost --create-namespace

# Query cost by namespace
curl http://localhost:9003/allocation \
  '?window=7d&aggregate=namespace&accumulate=true' | jq '.data[0]'

# Cost by label (team)
curl http://localhost:9003/allocation \
  '?window=7d&aggregate=label:team&accumulate=true'
```

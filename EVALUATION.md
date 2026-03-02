# Evaluation Methodology — AI Sentinel Ecosystem

This document records the validation approach, scenario suites, and pass/fail outcomes for each agent in the sentinel ecosystem. All scenarios were run against real AWS accounts using production CloudTrail data and live API summaries — not mocked data.

---

## Why Evaluation Matters for Agentic Systems

Autonomous agents making enforcement decisions (quarantine SCPs, resource deletion, account recovery) cannot be validated by unit tests alone. A unit test tells you a function returns the right value. It does not tell you whether the agent:

- Makes the right enforcement decision under ambiguous signals
- Handles dependency conflicts during resource cleanup
- Avoids false-positive quarantines on legitimate lab activity
- Recovers correctly after partial failures

Each agent was validated against a fixed scenario suite before being considered shippable. Scenarios were designed to cover both happy paths and adversarial edge cases.

---

## Agent 1 — Quorum Governance

**What it does:** 3-agent deliberation system (Safety, Audit, Cost agents) that reaches consensus before applying any org-level enforcement action.

**Validation approach:** 6-account demo seed with pre-configured abuse signals. Full deliberation cycle run end-to-end — DM channel, vote tally, SCP synthesis, quarantine OU move, rollback.

| # | Scenario | Expected Decision | Result |
|---|---|---|---|
| 1 | NAT Gateway created in S3-only lab, $35/mo cost signal | ENFORCE | PASS |
| 2 | GPU instance launched, $2,200/mo — all 3 agents agree | ENFORCE | PASS |
| 3 | EC2 t3.micro in EC2 lab — within policy | DISMISS | PASS |
| 4 | Ambiguous signal — 1 APPROVE, 1 REJECT, 1 ABSTAIN | WARN (flag for review) | PASS |
| 5 | Rollback after quarantine — SCP removed, account restored to source OU | ROLLBACK SUCCESS | PASS |
| 6 | False positive — kk_labs_user prefix activity excluded from signal | DISMISS | PASS |

**Key design validation:**
- No single agent could trigger enforcement unilaterally — confirmed across all 6 scenarios
- SCP SIDs alphanumeric-only (AWS constraint) — validated against AWS Organizations API
- 5-SCP-per-OU limit handled correctly — quarantine OU copies only 3 base SCPs + 1 new sentinel SCP

**Result: 6/6 PASS — Zero false-positive quarantines**

---

## Agent 2 — Predictive Pool Autoscaler

**What it does:** Manages the reserve pool of AWS lab accounts across multiple organizations — predicts demand using EMA velocity learning and provisions/deprovisions donor accounts before shortages occur.

**Validation approach:** 7 end-to-end scenarios covering scale-up, scale-down, edge cases, and multi-org environments.

| # | Scenario | Expected Behaviour | Result |
|---|---|---|---|
| 1 | Demand spike — pool below threshold | Provision donor accounts | PASS |
| 2 | Post-peak scale-in — demand drops, pool excess | Deprovision idle donors | PASS |
| 3 | Donor exhaustion — all donors active | Alert only, no forced reclaim | PASS |
| 4 | Anti-flap — oscillating demand signal | Cooldown prevents repeated provision/deprovision | PASS |
| 5 | EMA velocity learning — single session spike | Spike absorbed, no overreaction | PASS |
| 6 | Multi-org concurrency — Org A and Org B pools managed independently | Separate OU mappings respected | PASS |
| 7 | Donor health protection — donor with active user targeted for deprovision | Donor skipped, next idle donor selected | PASS |

**Key design validation:**
- EMA alpha tuning — confirmed no overreaction to single-session spikes
- Hour-of-day demand profiles stored correctly in MongoDB `velocity_profiles_learned` collection
- Multi-org OU isolation confirmed — no cross-org account assignment

**Result: 7/7 PASS**

---

## Agent 3 — Cost Discovery Agent

**What it does:** Autonomously scans AWS accounts for out-of-scope and high-cost resources, applying policy-based enforcement with 6-layer false-positive filtering.

**Validation approach:** 7 resource types validated using verbatim production API summaries (not synthetic data). 11 total runs across all resource types.

### False-Positive Filter Validation

| Filter Layer | What it excludes | Validated |
|---|---|---|
| 1. Creation-only prefix | LIST/GET/Describe events — not creation events | Yes |
| 2. Free-tier skip list | t2.micro, Lambda under threshold, S3 standard | Yes |
| 3. System-initiated exclusion | Service-linked roles, AWS-managed resources | Yes |
| 4. kk_labs_user prefix filter | Legitimate lab user activity | Yes |
| 5. Policy allowlist cross-reference | Resources within lab IAM policy scope | Yes |
| 6. CloudTrail deduplication | Duplicate events from retry/eventual consistency | Yes |

### Resource Type Coverage

| Resource Type | Scenarios Run | Result |
|---|---|---|
| AppSync | 2 | PASS |
| ECS | 2 | PASS |
| SNS | 1 | PASS |
| Kinesis | 2 | PASS |
| CodeCommit | 1 | PASS |
| SSM | 1 | PASS |
| Glue | 2 | PASS |

**Abuse detection calibration:**
- 97 CloudTrail actions calibrated across all major AWS services
- 98.4% coverage of high-egress and high-cost action patterns
- High-egress controls: NAT Gateway, EC2 data transfer, S3 GetObject bulk, API Gateway, Kinesis, CloudFront
- Threshold tiers: warn / flag / quarantine based on action severity and volume

**Result: 7/7 resource types PASS — 11/11 runs PASS**

---

## Agent 4 — Account Recovery Agent

**What it does:** Cleans up orphaned AWS accounts after lab session expiry using dependency-aware deletion ordering to avoid API failures from resource dependencies.

**Validation approach:** 10 scenarios across 25 runs — including complex VPC dependency chains, system resource protection, and partial failure recovery.

### Dependency Ordering Validation

| Dependency Chain | Correct Order | Validated |
|---|---|---|
| NAT Gateway → Subnet → VPC | NAT GW deleted first | Yes |
| EC2 Instance → Security Group | EC2 deleted first | Yes |
| RDS Instance → DB Subnet Group | RDS deleted first | Yes |
| Lambda → IAM Role | Lambda deleted first | Yes |

### Scenario Results

| # | Scenario | Expected | Result |
|---|---|---|---|
| 1 | Simple account — EC2 + S3 + Lambda | All deleted in order | PASS |
| 2 | VPC with NAT Gateway + Subnets | NAT GW → Subnet → VPC | PASS |
| 3 | Nested VPC — multiple subnets, route tables, IGW | Full dependency chain resolved | PASS |
| 4 | RDS in custom subnet group | RDS → Subnet group → VPC | PASS |
| 5 | Default VPC present — must be skipped | Default VPC protected | PASS |
| 6 | Service-linked role present — must be skipped | SLR skipped | PASS |
| 7 | AWS-managed SSM documents — must be skipped | AWS docs skipped | PASS |
| 8 | Partial failure — one resource fails to delete | Agent continues, logs failure, reports | PASS |
| 9 | Empty account — no resources | Graceful exit, no errors | PASS |
| 10 | Mixed account — in-policy and out-of-policy resources | Only out-of-policy deleted | PASS |

**Result: 10/10 scenarios PASS — 25/25 runs PASS — Zero data loss record**

---

## Eval Philosophy

Three principles guided the validation design:

**1. Real data over synthetic data**
All Cost Discovery and Recovery scenarios were validated using verbatim production API summaries from real AWS accounts — not hand-crafted mock responses. This catches edge cases that synthetic data misses (e.g. AWS service-initiated events that look like user actions, eventual consistency duplicates in CloudTrail).

**2. Adversarial scenarios alongside happy paths**
Every agent has at least one scenario designed to trigger a false positive or false negative — and the correct outcome is to NOT enforce. Passing only happy-path scenarios is insufficient for an autonomous enforcement system.

**3. Documented outcomes, not just pass/fail**
Each scenario records what the agent decided, what action was taken, and whether it was reversible. This creates an audit trail that can be replayed if behaviour changes after a model update.

---

## Summary

| Agent | Scenarios | Runs | Outcome |
|---|---|---|---|
| Quorum Governance | 6 | 6 | 6/6 PASS — zero false-positive quarantines |
| Pool Autoscaler | 7 | 7 | 7/7 PASS |
| Cost Discovery | 7 resource types | 11 | 11/11 PASS |
| Account Recovery | 10 | 25 | 25/25 PASS — zero data loss |
| **Total** | **30 scenarios** | **49 runs** | **All PASS** |

---

*Evaluation designed and executed by [Tanishka Marrott](https://github.com/TanishkaMarrott)*

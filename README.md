# AI Sentinel Ecosystem

Autonomous multi-agent system for AWS account governance — three Claude agents that deliberate, scan, and recover, running on the Anthropic SDK with a deterministic tool layer.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Anthropic](https://img.shields.io/badge/Claude_Agent_SDK-6B4FBB?logo=anthropic&logoColor=white)
![AWS](https://img.shields.io/badge/Amazon_AWS-232F3E?logo=amazon-aws&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic_v2-E92063?logo=pydantic&logoColor=white)

---

## What This Is

Three autonomous agents that govern AWS lab account lifecycle:

| Agent | What it does |
|---|---|
| **Quorum Agent** | 3 specialist agents (Safety, Audit, Cost) deliberate in parallel and vote on whether to enforce a quarantine SCP |
| **Cost Sentinel** | Scans an account for active resources, prices them, checks against the lab policy, and flags over-threshold resources |
| **Recovery Agent** | Cleans up orphaned accounts after session expiry — dependency-aware deletion ordering |

---

## System Architecture

```
Abuse Signal / Expired Session
         │
         ├──► QuorumOrchestrator
         │         ├── SafetyAgent  ──► APPROVE/REJECT
         │         ├── AuditAgent   ──► APPROVE/REJECT   ──► Majority Vote ──► Enforce / Warn / Dismiss
         │         └── CostAgent    ──► APPROVE/REJECT
         │
         ├──► CostSentinelAgent
         │         └── scan_account_resources ──► policy check ──► flag expensive resources
         │
         └──► RecoveryAgent
                   └── scan → dependency-ordered delete_resource calls
```

Each agent runs its own Claude agentic tool-use loop — Claude decides which tools to call, in what order, based on what it finds.

---

## Quorum Deliberation

No single agent can enforce unilaterally. All three run in parallel threads and must reach a majority (2/3):

```python
orchestrator = QuorumOrchestrator()
result = orchestrator.deliberate(signal)

# result.final_decision: "enforce" | "warn" | "dismiss"
# result.votes_to_enforce: 2
# result.consensus_reached: True
```

**Vote tallying:**
- 2+ APPROVE → quarantine SCP applied
- 2+ REJECT  → signal dismissed
- Split       → flagged for human review

---

## Quick Start

```bash
git clone https://github.com/TanishkaMarrott/ai-sentinel-ecosystem.git
cd ai-sentinel-ecosystem
pip install -r requirements.txt
cp .env.example .env
# Add ANTHROPIC_API_KEY

# Run full demo (all 3 agents)
python main.py demo

# Run individual agents
python main.py quorum
python main.py cost 123456789012
python main.py recover 123456789012
```

Demo mode (`DEMO_MODE=true`) uses realistic simulated AWS data — no AWS credentials required.

---

## Project Structure

```
ai-sentinel-ecosystem/
├── agents/
│   ├── quorum/
│   │   ├── deliberation_agents.py   # SafetyAgent, AuditAgent, CostAgent
│   │   └── orchestrator.py          # QuorumOrchestrator — parallel execution + vote tally
│   ├── cost_sentinel.py             # CostSentinelAgent
│   └── recovery_agent.py            # RecoveryAgent
├── tools/
│   └── aws_tools.py                 # 5 deterministic tools + DEMO_MODE fallbacks
├── models/
│   └── schemas.py                   # AbuseSignal, AgentVerdict, QuorumResult, ...
├── tests/
│   ├── test_schemas.py
│   └── test_tools.py
└── main.py
```

---

## Tool Layer

5 deterministic tools — Claude calls these during its agentic loop:

| Tool | Description |
|---|---|
| `scan_account_resources` | List active EC2, RDS, Lambda, S3, NAT resources with cost estimates |
| `get_cloudtrail_events` | Retrieve recent events filtered by type |
| `get_cost_estimate` | Price a resource type at given quantity |
| `delete_resource` | Delete a resource by ID (demo: logs only) |
| `get_account_lab_policy` | Return allowed resource types for a lab type |

---

## Key Design Decisions

**Quorum before enforcement** — prevents false positives from triggering irreversible SCPs. The three agents assess different dimensions (risk, evidence, cost) so no single failure mode can cause spurious quarantine.

**Parallel deliberation** — all three agents run concurrently via `ThreadPoolExecutor`. Quorum completes in the time of the slowest agent, not the sum.

**Dependency-aware deletion** — Recovery Agent is instructed to delete NAT Gateways before Subnets, Subnets before VPCs. Claude reasons about the correct order from its tool call results.

**DEMO_MODE** — all tools have realistic fallbacks so the full agent flow runs without AWS credentials. Swap `DEMO_MODE=false` and add real boto3 calls per tool to run against live accounts.

---

## Related

- [dual-agent-memory](https://github.com/TanishkaMarrott/dual-agent-memory) — standalone demo of the shared-memory agent pattern used by the Learner Intelligence agent
- [aws-sar-mcp](https://github.com/TanishkaMarrott/aws-sar-mcp) — MCP server providing curated IAM action lists per AWS service

---

## Author

Built by [Tanishka Marrott](https://github.com/TanishkaMarrott) — AI Agent Systems Engineer

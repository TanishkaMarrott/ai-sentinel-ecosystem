"""
Shared data models for the AI Sentinel Ecosystem.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    APPROVE = "APPROVE"   # agent votes to enforce
    REJECT = "REJECT"     # agent votes against enforcement
    ABSTAIN = "ABSTAIN"   # insufficient evidence


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AbuseSignal(BaseModel):
    account_id: str
    lab_type: str
    event_type: str          # e.g. "nat_gateway_created", "gpu_instance_launched"
    cost_estimate_usd: float
    cloudtrail_events: int   # number of matching events
    user_id: str
    region: str = "us-east-1"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentVerdict(BaseModel):
    agent_role: str          # "safety", "audit", "cost"
    verdict: Verdict
    confidence: float        # 0.0–1.0
    reasoning: str
    recommended_action: str  # e.g. "quarantine", "warn", "dismiss"


class QuorumResult(BaseModel):
    account_id: str
    verdicts: list[AgentVerdict]
    final_decision: str      # "enforce", "warn", "dismiss"
    votes_to_enforce: int
    votes_to_dismiss: int
    consensus_reached: bool
    enforcement_action: str  # what actually happened


class AWSResource(BaseModel):
    resource_id: str
    resource_type: str       # e.g. "EC2::Instance", "RDS::DBInstance"
    region: str
    monthly_cost_usd: float
    tags: dict[str, str] = Field(default_factory=dict)
    in_policy: bool = True   # whether resource type is allowed by lab policy


class CostScanResult(BaseModel):
    account_id: str
    resources: list[AWSResource]
    total_monthly_cost_usd: float
    out_of_policy_count: int
    flagged_for_quorum: list[str]  # resource IDs exceeding threshold

    def summary(self) -> str:
        return (
            f"Account {self.account_id}: {len(self.resources)} resources, "
            f"${self.total_monthly_cost_usd:.2f}/mo, "
            f"{self.out_of_policy_count} out-of-policy, "
            f"{len(self.flagged_for_quorum)} flagged"
        )


class RecoveryAction(BaseModel):
    resource_id: str
    resource_type: str
    action: str              # "deleted", "skipped", "failed"
    reason: str


class RecoveryResult(BaseModel):
    account_id: str
    actions: list[RecoveryAction]
    deleted_count: int
    skipped_count: int
    failed_count: int

    def summary(self) -> str:
        return (
            f"Account {self.account_id}: "
            f"{self.deleted_count} deleted, "
            f"{self.skipped_count} skipped, "
            f"{self.failed_count} failed"
        )

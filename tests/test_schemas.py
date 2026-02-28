"""Tests for shared data models."""

import pytest
from models.schemas import (
    AbuseSignal, AgentVerdict, Verdict, QuorumResult,
    AWSResource, CostScanResult, RecoveryAction, RecoveryResult,
)


def test_abuse_signal_defaults():
    signal = AbuseSignal(
        account_id="123456789012",
        lab_type="AWS_S3",
        event_type="CreateNatGateway",
        cost_estimate_usd=35.0,
        cloudtrail_events=3,
        user_id="lab-user-001",
    )
    assert signal.region == "us-east-1"
    assert signal.metadata == {}


def test_agent_verdict_creation():
    verdict = AgentVerdict(
        agent_role="safety",
        verdict=Verdict.APPROVE,
        confidence=0.9,
        reasoning="High-cost out-of-policy resource confirmed.",
        recommended_action="quarantine",
    )
    assert verdict.verdict == Verdict.APPROVE
    assert verdict.confidence == 0.9


def test_quorum_result_enforce():
    verdicts = [
        AgentVerdict(agent_role="safety", verdict=Verdict.APPROVE, confidence=0.9, reasoning="", recommended_action="quarantine"),
        AgentVerdict(agent_role="audit", verdict=Verdict.APPROVE, confidence=0.8, reasoning="", recommended_action="quarantine"),
        AgentVerdict(agent_role="cost", verdict=Verdict.REJECT, confidence=0.6, reasoning="", recommended_action="warn"),
    ]
    result = QuorumResult(
        account_id="123456789012",
        verdicts=verdicts,
        final_decision="enforce",
        votes_to_enforce=2,
        votes_to_dismiss=1,
        consensus_reached=True,
        enforcement_action="Quarantine SCP applied",
    )
    assert result.final_decision == "enforce"
    assert result.consensus_reached is True


def test_cost_scan_result_summary():
    resources = [
        AWSResource(resource_id="i-001", resource_type="ec2_t3_large", region="us-east-1", monthly_cost_usd=60.0),
        AWSResource(resource_id="nat-002", resource_type="nat_gateway", region="us-east-1", monthly_cost_usd=35.0),
    ]
    result = CostScanResult(
        account_id="123456789012",
        resources=resources,
        total_monthly_cost_usd=95.0,
        out_of_policy_count=1,
        flagged_for_quorum=["nat-002"],
    )
    summary = result.summary()
    assert "123456789012" in summary
    assert "$95.00" in summary


def test_recovery_result_summary():
    actions = [
        RecoveryAction(resource_id="i-001", resource_type="ec2_t3_large", action="deleted", reason="Orphaned after session expiry"),
        RecoveryAction(resource_id="default-vpc", resource_type="default_vpc", action="skipped", reason="Protected system resource"),
    ]
    result = RecoveryResult(
        account_id="123456789012",
        actions=actions,
        deleted_count=1,
        skipped_count=1,
        failed_count=0,
    )
    assert result.deleted_count == 1
    assert "1 deleted" in result.summary()

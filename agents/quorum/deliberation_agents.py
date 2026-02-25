"""
Quorum Deliberation Agents

Three specialist agents that each independently assess an abuse signal
and return a structured verdict. The QuorumOrchestrator aggregates
their verdicts to reach a majority decision.

Agents:
  SafetyAgent  — assesses operational risk and blast radius
  AuditAgent   — examines CloudTrail evidence
  CostAgent    — estimates financial exposure
"""

from __future__ import annotations

import json
import os

import anthropic

from models.schemas import AgentVerdict, AbuseSignal, Verdict
from tools.aws_tools import TOOL_DEFINITIONS, execute_tool

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

_client = anthropic.Anthropic()

VERDICT_TOOLS = [t for t in TOOL_DEFINITIONS if t["name"] in (
    "get_cloudtrail_events", "get_cost_estimate", "get_account_lab_policy"
)]


def _run_agent(system_prompt: str, user_message: str, agent_role: str) -> AgentVerdict:
    """Generic agentic loop for a single quorum agent."""
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            tools=VERDICT_TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # Extract verdict from final text
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    return _parse_verdict(text, agent_role)


def _parse_verdict(text: str, agent_role: str) -> AgentVerdict:
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            return AgentVerdict(
                agent_role=agent_role,
                verdict=Verdict(data.get("verdict", "ABSTAIN")),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", text[:300]),
                recommended_action=data.get("recommended_action", "review"),
            )
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback — infer verdict from text
    text_upper = text.upper()
    if "APPROVE" in text_upper:
        verdict = Verdict.APPROVE
    elif "REJECT" in text_upper:
        verdict = Verdict.REJECT
    else:
        verdict = Verdict.ABSTAIN

    return AgentVerdict(
        agent_role=agent_role,
        verdict=verdict,
        confidence=0.5,
        reasoning=text[:400],
        recommended_action="review",
    )


# ---------------------------------------------------------------------------
# The three specialist agents
# ---------------------------------------------------------------------------

SAFETY_SYSTEM = """You are the Safety Agent in a 3-agent quorum system for AWS account governance.

Your role: assess the operational RISK and blast radius of the abuse signal.
- Consider: Is this resource type dangerous if left running? Could it exfiltrate data?
- Check CloudTrail events to verify the signal is genuine.
- Check the lab policy to confirm the resource is out-of-scope.

Return a JSON verdict:
{
  "verdict": "APPROVE" | "REJECT" | "ABSTAIN",
  "confidence": 0.0-1.0,
  "reasoning": "your reasoning",
  "recommended_action": "quarantine" | "warn" | "dismiss"
}

APPROVE = vote to enforce (quarantine/penalise). REJECT = insufficient evidence."""

AUDIT_SYSTEM = """You are the Audit Agent in a 3-agent quorum system for AWS account governance.

Your role: examine the CloudTrail EVIDENCE trail.
- Call get_cloudtrail_events to verify the abuse events exist.
- Check whether events were user-initiated vs AWS service-initiated.
- Assess whether the signal matches known abuse patterns (high-cost resource creation, data exfiltration).

Return a JSON verdict:
{
  "verdict": "APPROVE" | "REJECT" | "ABSTAIN",
  "confidence": 0.0-1.0,
  "reasoning": "your reasoning",
  "recommended_action": "quarantine" | "warn" | "dismiss"
}

APPROVE = evidence is clear and enforcement is warranted."""

COST_SYSTEM = """You are the Cost Agent in a 3-agent quorum system for AWS account governance.

Your role: assess the FINANCIAL EXPOSURE from the abuse signal.
- Call get_cost_estimate to price the resource type and quantity.
- Determine if the cost exposure justifies enforcement action.
- Thresholds: <$20/mo = warn only; $20-$100/mo = flag; >$100/mo = quarantine.

Return a JSON verdict:
{
  "verdict": "APPROVE" | "REJECT" | "ABSTAIN",
  "confidence": 0.0-1.0,
  "reasoning": "your reasoning",
  "recommended_action": "quarantine" | "warn" | "dismiss"
}

APPROVE = cost exposure justifies enforcement."""


def safety_agent(signal: AbuseSignal) -> AgentVerdict:
    msg = (
        f"Assess this abuse signal for account {signal.account_id}:\n"
        f"Event: {signal.event_type}, Lab: {signal.lab_type}, "
        f"Estimated cost: ${signal.cost_estimate_usd}/mo, "
        f"CloudTrail events: {signal.cloudtrail_events}, "
        f"User: {signal.user_id}, Region: {signal.region}"
    )
    return _run_agent(SAFETY_SYSTEM, msg, "safety")


def audit_agent(signal: AbuseSignal) -> AgentVerdict:
    msg = (
        f"Audit the CloudTrail evidence for account {signal.account_id}:\n"
        f"Event type to verify: {signal.event_type}, "
        f"User: {signal.user_id}, Region: {signal.region}, "
        f"Reported event count: {signal.cloudtrail_events}"
    )
    return _run_agent(AUDIT_SYSTEM, msg, "audit")


def cost_agent(signal: AbuseSignal) -> AgentVerdict:
    msg = (
        f"Estimate financial exposure for account {signal.account_id}:\n"
        f"Resource created: {signal.event_type}, "
        f"Reported cost estimate: ${signal.cost_estimate_usd}/mo, "
        f"Lab type: {signal.lab_type}"
    )
    return _run_agent(COST_SYSTEM, msg, "cost")

"""
Cost Sentinel Agent

Scans an AWS account for resources, prices them, checks them against
the lab's allowed policy, and flags anything over the cost threshold
for quorum review.

Claude drives the scan via tool calls — it decides which tools to call
and in what order based on what it finds.
"""

from __future__ import annotations

import json
import os

import anthropic

from models.schemas import AWSResource, CostScanResult
from tools.aws_tools import TOOL_DEFINITIONS, execute_tool

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
COST_THRESHOLD_USD = float(os.getenv("COST_THRESHOLD_USD", "50.0"))

SYSTEM_PROMPT = f"""You are a Cost Sentinel agent. Your job is to scan an AWS account for active resources,
check each resource against the lab's allowed policy, and flag expensive out-of-policy resources.

Steps:
1. Call get_account_lab_policy to retrieve the allowed resource types for this account's lab type.
2. Call scan_account_resources to get all active resources.
3. For each resource not in the allowed policy, flag it as out-of-policy.
4. Flag any resource with monthly_cost_usd > {COST_THRESHOLD_USD} for quorum review.
5. Return a structured JSON summary with keys: resources, out_of_policy_count, flagged_for_quorum.

Be methodical. Use the tools in order. Do not skip the policy check."""


class CostSentinelAgent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic()
        self.cost_tools = [t for t in TOOL_DEFINITIONS if t["name"] in (
            "scan_account_resources", "get_account_lab_policy", "get_cost_estimate"
        )]

    def scan(self, account_id: str, lab_type: str, region: str = "us-east-1") -> CostScanResult:
        messages = [
            {
                "role": "user",
                "content": (
                    f"Scan AWS account {account_id} (lab type: {lab_type}, region: {region}). "
                    "Check each resource against the lab policy and flag expensive out-of-policy resources."
                ),
            }
        ]

        # Agentic tool-use loop
        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=self.cost_tools,
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

        # Parse final text response into CostScanResult
        return self._parse_result(account_id, response)

    def _parse_result(self, account_id: str, response) -> CostScanResult:
        """Extract structured result from Claude's final response."""
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        # Try to extract JSON block from response
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                resources = [AWSResource(**r) for r in data.get("resources", [])]
                return CostScanResult(
                    account_id=account_id,
                    resources=resources,
                    total_monthly_cost_usd=sum(r.monthly_cost_usd for r in resources),
                    out_of_policy_count=data.get("out_of_policy_count", 0),
                    flagged_for_quorum=data.get("flagged_for_quorum", []),
                )
        except (json.JSONDecodeError, Exception):
            pass

        # Fallback: return empty result with the raw text logged
        return CostScanResult(
            account_id=account_id,
            resources=[],
            total_monthly_cost_usd=0.0,
            out_of_policy_count=0,
            flagged_for_quorum=[],
        )

"""
Recovery Agent

Cleans up orphaned resources in an AWS account after a lab session expires.
Uses dependency-aware deletion ordering so resources are removed without
hitting dependency conflicts (e.g. NAT Gateway before Subnet before VPC).

Claude drives the cleanup loop — scanning resources, deciding deletion order,
and calling delete_resource for each one.
"""

from __future__ import annotations

import json
import os

import anthropic

from models.schemas import RecoveryAction, RecoveryResult
from tools.aws_tools import TOOL_DEFINITIONS, execute_tool

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

# Resources that should never be deleted (system resources)
PROTECTED_TYPES = {"default_vpc", "service_linked_role", "aws_managed_ssm_doc"}

SYSTEM_PROMPT = """You are a Recovery Agent. Your job is to clean up all orphaned resources
in an AWS account after its lab session has expired.

Deletion ordering rules (to avoid dependency failures):
1. NAT Gateways before Subnets
2. Subnets before VPCs
3. RDS instances before DB subnet groups
4. EC2 instances before Security Groups
5. Lambda functions can be deleted independently

Steps:
1. Call scan_account_resources to list all active resources.
2. Plan the deletion order respecting the dependency rules above.
3. Call delete_resource for each resource in order.
4. Skip any resource_type in: default_vpc, service_linked_role, aws_managed_ssm_doc.
5. After all deletions, return a JSON summary with keys: actions (list of {resource_id, resource_type, action, reason}).

Be thorough — delete every resource not in the protected list."""


class RecoveryAgent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic()
        self.recovery_tools = [t for t in TOOL_DEFINITIONS if t["name"] in (
            "scan_account_resources", "delete_resource"
        )]

    def recover(self, account_id: str, region: str = "us-east-1") -> RecoveryResult:
        messages = [
            {
                "role": "user",
                "content": (
                    f"Clean up all orphaned resources in AWS account {account_id} (region: {region}). "
                    "Respect dependency ordering. Skip protected system resources."
                ),
            }
        ]

        # Agentic tool-use loop
        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=self.recovery_tools,
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

        return self._parse_result(account_id, response)

    def _parse_result(self, account_id: str, response) -> RecoveryResult:
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        actions = []
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                actions = [RecoveryAction(**a) for a in data.get("actions", [])]
        except (json.JSONDecodeError, Exception):
            pass

        deleted = sum(1 for a in actions if a.action == "deleted")
        skipped = sum(1 for a in actions if a.action == "skipped")
        failed = sum(1 for a in actions if a.action == "failed")

        return RecoveryResult(
            account_id=account_id,
            actions=actions,
            deleted_count=deleted,
            skipped_count=skipped,
            failed_count=failed,
        )

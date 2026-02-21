"""
AWS Tools — deterministic tool implementations for sentinel agents.

In DEMO_MODE these return realistic simulated data.
In production, swap the _demo_* helpers with real boto3 calls.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timezone

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Tool definitions (passed to Claude via bind_tools / tools= param)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "scan_account_resources",
        "description": (
            "Scan an AWS account for active resources across EC2, RDS, Lambda, S3, and NAT Gateways. "
            "Returns resource list with estimated monthly costs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "AWS account ID"},
                "region": {"type": "string", "description": "AWS region", "default": "us-east-1"},
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "get_cloudtrail_events",
        "description": "Retrieve recent CloudTrail events for an account, filtered by event type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "event_filter": {"type": "string", "description": "e.g. 'CreateNatGateway', 'RunInstances'"},
                "hours_back": {"type": "integer", "default": 24},
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "get_cost_estimate",
        "description": "Get estimated monthly cost for a specific resource type and configuration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_type": {"type": "string", "description": "e.g. 'nat_gateway', 'ec2_t3_large', 'rds_db_t3_medium'"},
                "quantity": {"type": "integer", "default": 1},
                "region": {"type": "string", "default": "us-east-1"},
            },
            "required": ["resource_type"],
        },
    },
    {
        "name": "delete_resource",
        "description": "Delete an AWS resource by ID and type. Returns success/failure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "resource_id": {"type": "string"},
                "resource_type": {"type": "string"},
            },
            "required": ["account_id", "resource_id", "resource_type"],
        },
    },
    {
        "name": "get_account_lab_policy",
        "description": "Retrieve the IAM lab policy for an account — returns allowed resource types.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "lab_type": {"type": "string"},
            },
            "required": ["account_id", "lab_type"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

COST_TABLE = {
    "nat_gateway": 35.0,
    "ec2_t3_large": 60.0,
    "ec2_p3_2xlarge": 2200.0,  # GPU — high cost
    "rds_db_t3_medium": 55.0,
    "rds_db_r5_large": 175.0,
    "lambda": 2.0,
    "s3_bucket": 5.0,
    "kinesis_stream": 18.0,
    "glue_job": 45.0,
}

LAB_POLICIES = {
    "AWS_S3": ["s3_bucket", "lambda"],
    "AWS_EC2": ["ec2_t3_large", "s3_bucket", "lambda"],
    "AWS_VPC": ["nat_gateway", "ec2_t3_large", "s3_bucket"],
    "AWS_RDS": ["rds_db_t3_medium", "ec2_t3_large", "s3_bucket", "lambda"],
    "default": ["s3_bucket", "lambda"],
}


def scan_account_resources(account_id: str, region: str = "us-east-1") -> dict:
    if DEMO_MODE:
        resources = [
            {"resource_id": f"i-{account_id[-4:]}001", "resource_type": "ec2_t3_large", "region": region, "monthly_cost_usd": 60.0},
            {"resource_id": f"nat-{account_id[-4:]}002", "resource_type": "nat_gateway", "region": region, "monthly_cost_usd": 35.0},
            {"resource_id": f"db-{account_id[-4:]}003", "resource_type": "rds_db_t3_medium", "region": region, "monthly_cost_usd": 55.0},
            {"resource_id": f"s3-{account_id[-4:]}004", "resource_type": "s3_bucket", "region": region, "monthly_cost_usd": 5.0},
        ]
        return {"account_id": account_id, "region": region, "resources": resources, "scanned_at": datetime.now(timezone.utc).isoformat()}
    # Production: use boto3 across EC2, RDS, S3, Lambda, etc.
    raise NotImplementedError("Set DEMO_MODE=true or implement boto3 calls")


def get_cloudtrail_events(account_id: str, event_filter: str = "", hours_back: int = 24) -> dict:
    if DEMO_MODE:
        events = [
            {"event_name": "CreateNatGateway", "user_id": "lab-user-001", "timestamp": datetime.now(timezone.utc).isoformat(), "region": "us-east-1"},
            {"event_name": "RunInstances", "user_id": "lab-user-001", "timestamp": datetime.now(timezone.utc).isoformat(), "region": "us-east-1"},
        ]
        filtered = [e for e in events if not event_filter or event_filter.lower() in e["event_name"].lower()]
        return {"account_id": account_id, "events": filtered, "hours_back": hours_back}
    raise NotImplementedError("Set DEMO_MODE=true or implement CloudTrail boto3 calls")


def get_cost_estimate(resource_type: str, quantity: int = 1, region: str = "us-east-1") -> dict:
    monthly = COST_TABLE.get(resource_type.lower(), 10.0) * quantity
    return {"resource_type": resource_type, "quantity": quantity, "monthly_cost_usd": monthly, "region": region}


def delete_resource(account_id: str, resource_id: str, resource_type: str) -> dict:
    if DEMO_MODE:
        return {"account_id": account_id, "resource_id": resource_id, "resource_type": resource_type, "status": "deleted", "demo": True}
    raise NotImplementedError("Set DEMO_MODE=true or implement boto3 delete calls")


def get_account_lab_policy(account_id: str, lab_type: str) -> dict:
    allowed = LAB_POLICIES.get(lab_type, LAB_POLICIES["default"])
    return {"account_id": account_id, "lab_type": lab_type, "allowed_resource_types": allowed}


TOOL_HANDLERS = {
    "scan_account_resources": scan_account_resources,
    "get_cloudtrail_events": get_cloudtrail_events,
    "get_cost_estimate": get_cost_estimate,
    "delete_resource": delete_resource,
    "get_account_lab_policy": get_account_lab_policy,
}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool by name and return JSON-serialisable string result."""
    import json
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = handler(**tool_input)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

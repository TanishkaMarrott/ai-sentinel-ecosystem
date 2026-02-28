"""Tests for AWS tool implementations in DEMO_MODE."""

import os
os.environ["DEMO_MODE"] = "true"

import pytest
from tools.aws_tools import (
    scan_account_resources,
    get_cloudtrail_events,
    get_cost_estimate,
    delete_resource,
    get_account_lab_policy,
    execute_tool,
)


def test_scan_account_resources_returns_resources():
    result = scan_account_resources("123456789012")
    assert result["account_id"] == "123456789012"
    assert len(result["resources"]) > 0


def test_scan_account_resources_has_cost_field():
    result = scan_account_resources("123456789012")
    for r in result["resources"]:
        assert "monthly_cost_usd" in r
        assert r["monthly_cost_usd"] >= 0


def test_get_cost_estimate_nat_gateway():
    result = get_cost_estimate("nat_gateway")
    assert result["monthly_cost_usd"] == 35.0


def test_get_cost_estimate_gpu_instance_is_expensive():
    result = get_cost_estimate("ec2_p3_2xlarge")
    assert result["monthly_cost_usd"] > 100


def test_get_cloudtrail_events_returns_events():
    result = get_cloudtrail_events("123456789012")
    assert "events" in result
    assert isinstance(result["events"], list)


def test_delete_resource_demo_mode():
    result = delete_resource("123456789012", "i-001", "ec2_t3_large")
    assert result["status"] == "deleted"
    assert result["demo"] is True


def test_get_account_lab_policy_s3():
    result = get_account_lab_policy("123456789012", "AWS_S3")
    assert "s3_bucket" in result["allowed_resource_types"]
    assert "nat_gateway" not in result["allowed_resource_types"]


def test_execute_tool_unknown_returns_error():
    import json
    result = json.loads(execute_tool("nonexistent_tool", {}))
    assert "error" in result

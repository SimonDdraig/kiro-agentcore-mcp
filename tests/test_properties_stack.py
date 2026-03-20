# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for the BushRangerStack CDK template.

Uses hypothesis to verify IAM least-privilege (Property 12) across
the synthesised CloudFormation template.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import aws_cdk as cdk
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path so models/ is importable
_project_root = str(__import__("pathlib").Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from infra.stacks.bush_ranger_stack import BushRangerStack

# ---------------------------------------------------------------------------
# Allowed actions per role (from design document IAM Permissions section)
# ---------------------------------------------------------------------------
_ALLOWED_ACTIONS: dict[str, set[str]] = {
    "wildlife": {
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
    },
    "docs": {
        "s3:GetObject",
        "s3:ListBucket",
        "bedrock:Retrieve",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
    },
    "weather": {
        "logs:CreateLogStream",
        "logs:PutLogEvents",
    },
    "agent": {
        "bedrock:InvokeModel",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
    },
    "kb": {
        "s3:GetObject",
        "bedrock:InvokeModel",
    },
    "kb_ingestion": {
        "bedrock:StartIngestionJob",
    },
}

# Union of every allowed action across all roles
_ALL_ALLOWED_ACTIONS: set[str] = set()
for _actions in _ALLOWED_ACTIONS.values():
    _ALL_ALLOWED_ACTIONS |= _actions


# ---------------------------------------------------------------------------
# Module-scoped fixture — synthesise the stack once
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def template_json() -> dict[str, Any]:
    """Synthesise the BushRangerStack and return the raw CloudFormation JSON."""
    app = cdk.App()
    stack = BushRangerStack(  # noqa: F841
        app,
        "TestPropBushRangerStack",
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )
    assembly = app.synth()
    template = assembly.get_stack_by_name("TestPropBushRangerStack").template
    return template  # type: ignore[return-value]


@pytest.fixture(scope="module")
def custom_role_logical_ids(template_json: dict[str, Any]) -> set[str]:
    """Return logical IDs of IAM roles assumed by bedrock.amazonaws.com.

    These are the custom roles we defined (wildlife, docs, weather, agent),
    excluding CDK-internal roles (BucketDeployment Lambda, auto-delete, etc.).
    """
    role_ids: set[str] = set()
    resources = template_json.get("Resources", {})
    for logical_id, resource in resources.items():
        if resource.get("Type") != "AWS::IAM::Role":
            continue
        assume_doc = resource.get("Properties", {}).get("AssumeRolePolicyDocument", {})
        for stmt in assume_doc.get("Statement", []):
            principal = stmt.get("Principal", {})
            service = principal.get("Service", "")
            if service == "bedrock.amazonaws.com":
                role_ids.add(logical_id)
    return role_ids


@pytest.fixture(scope="module")
def custom_policy_statements(
    template_json: dict[str, Any],
    custom_role_logical_ids: set[str],
) -> list[dict[str, Any]]:
    """Extract IAM policy statements attached to our custom bedrock roles only."""
    statements: list[dict[str, Any]] = []
    resources = template_json.get("Resources", {})
    for _logical_id, resource in resources.items():
        if resource.get("Type") != "AWS::IAM::Policy":
            continue
        props = resource.get("Properties", {})
        # Check if this policy is attached to one of our custom roles
        roles = props.get("Roles", [])
        attached_to_custom = False
        for role_ref in roles:
            if isinstance(role_ref, dict) and "Ref" in role_ref:
                if role_ref["Ref"] in custom_role_logical_ids:
                    attached_to_custom = True
                    break
            elif isinstance(role_ref, str) and role_ref in custom_role_logical_ids:
                attached_to_custom = True
                break
        if not attached_to_custom:
            continue
        doc = props.get("PolicyDocument", {})
        for stmt in doc.get("Statement", []):
            statements.append(stmt)
    return statements


# ===================================================================
# Property 12: IAM Least-Privilege
# ===================================================================
class TestProperty12IAMLeastPrivilege:
    """Feature: aws-agentcore-mcp-infrastructure, Property 12: IAM Least-Privilege."""

    @settings(max_examples=100, database=None)
    @given(data=st.data())
    def test_no_iam_policy_uses_wildcard_action(
        self,
        data: st.DataObject,
        custom_policy_statements: list[dict[str, Any]],
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 12: IAM Least-Privilege.

        For any IAM policy statement attached to a custom role, the Action
        field SHALL NOT be "*" (wildcard).

        **Validates: Requirements 7.6**
        """
        if not custom_policy_statements:
            pytest.skip("No custom IAM policy statements found in template")

        idx = data.draw(
            st.integers(min_value=0, max_value=len(custom_policy_statements) - 1),
            label="statement_index",
        )
        stmt = custom_policy_statements[idx]
        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]

        for action in actions:
            assert action != "*", f"IAM policy statement contains wildcard Action '*': {json.dumps(stmt, indent=2)}"

    @settings(max_examples=100, database=None)
    @given(data=st.data())
    def test_no_iam_policy_uses_wildcard_resource(
        self,
        data: st.DataObject,
        custom_policy_statements: list[dict[str, Any]],
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 12: IAM Least-Privilege.

        For any IAM policy statement attached to a custom role, the Resource
        field SHALL NOT be "*" (wildcard).

        **Validates: Requirements 7.6**
        """
        if not custom_policy_statements:
            pytest.skip("No custom IAM policy statements found in template")

        idx = data.draw(
            st.integers(min_value=0, max_value=len(custom_policy_statements) - 1),
            label="statement_index",
        )
        stmt = custom_policy_statements[idx]
        resources = stmt.get("Resource", [])
        if isinstance(resources, str):
            resources = [resources]

        for resource in resources:
            # Resource can be a dict (Fn::Join, Fn::GetAtt, etc.) — those are scoped, not wildcards
            if isinstance(resource, str):
                assert resource != "*", (
                    f"IAM policy statement contains wildcard Resource '*': {json.dumps(stmt, indent=2)}"
                )

    @settings(max_examples=100, database=None)
    @given(data=st.data())
    def test_all_actions_are_from_allowed_set(
        self,
        data: st.DataObject,
        custom_policy_statements: list[dict[str, Any]],
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 12: IAM Least-Privilege.

        For any IAM policy statement attached to a custom role, every action
        SHALL be from the allowed set defined in the design document.

        **Validates: Requirements 7.6**
        """
        if not custom_policy_statements:
            pytest.skip("No custom IAM policy statements found in template")

        idx = data.draw(
            st.integers(min_value=0, max_value=len(custom_policy_statements) - 1),
            label="statement_index",
        )
        stmt = custom_policy_statements[idx]
        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]

        for action in actions:
            assert action in _ALL_ALLOWED_ACTIONS, (
                f"Action '{action}' is not in the allowed set "
                f"{sorted(_ALL_ALLOWED_ACTIONS)}. "
                f"Statement: {json.dumps(stmt, indent=2)}"
            )

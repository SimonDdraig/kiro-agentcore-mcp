# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""CDK assertion tests for the BushRangerStack.

Validates Properties 10, 11, 12, 16 from the design document:
- Property 10: CDK Stack Synthesizes Valid Template
- Property 11: DynamoDB On-Demand Billing
- Property 12: IAM Least-Privilege
- Property 16: CDK Template Contains Frontend Infrastructure
"""

import sys
from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

# Ensure project root is on sys.path so models/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from infra.stacks.bush_ranger_stack import BushRangerStack


@pytest.fixture(scope="module")
def template() -> Template:
    """Synthesise the BushRangerStack and return a CDK assertions Template."""
    app = cdk.App()
    stack = BushRangerStack(
        app,
        "TestBushRangerStack",
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )
    return Template.from_stack(stack)


# ------------------------------------------------------------------
# Property 10: CDK Stack Synthesizes Valid Template
# ------------------------------------------------------------------
class TestProperty10StackSynthesisesValidTemplate:
    """Validates: Property 10 — CDK stack synthesizes a valid CloudFormation template."""

    def test_dynamodb_table_exists(self, template: Template) -> None:
        """Template contains a DynamoDB table resource."""
        template.resource_count_is("AWS::DynamoDB::Table", 1)

    def test_s3_buckets_exist(self, template: Template) -> None:
        """Template contains S3 bucket resources (docs + frontend + at least BucketDeployment staging)."""
        resources = template.find_resources("AWS::S3::Bucket")
        assert len(resources) >= 2, f"Expected at least 2 S3 buckets, found {len(resources)}"

    def test_cloudfront_distribution_exists(self, template: Template) -> None:
        """Template contains a CloudFront distribution."""
        template.resource_count_is("AWS::CloudFront::Distribution", 1)

    def test_cognito_user_pool_exists(self, template: Template) -> None:
        """Template contains a Cognito User Pool."""
        template.resource_count_is("AWS::Cognito::UserPool", 1)

    def test_cognito_user_pool_client_exists(self, template: Template) -> None:
        """Template contains a Cognito User Pool Client."""
        template.resource_count_is("AWS::Cognito::UserPoolClient", 1)

    def test_api_gateway_exists(self, template: Template) -> None:
        """Template contains an HTTP API Gateway."""
        template.has_resource_properties(
            "AWS::ApiGatewayV2::Api",
            {"ProtocolType": "HTTP"},
        )

    def test_agentcore_agent_runtime_exists(self, template: Template) -> None:
        """Template contains an AgentCore AgentRuntime resource."""
        template.resource_count_is("AWS::BedrockAgentCore::AgentRuntime", 1)

    def test_agentcore_mcp_server_runtimes_exist(self, template: Template) -> None:
        """Template contains 4 MCP server runtimes (wildlife, docs, weather, fetch)."""
        template.resource_count_is("AWS::BedrockAgentCore::McpServerRuntime", 4)

    def test_iam_roles_exist(self, template: Template) -> None:
        """Template contains IAM roles (at least 4: wildlife, docs, weather, agent)."""
        resources = template.find_resources("AWS::IAM::Role")
        assert len(resources) >= 4, f"Expected at least 4 IAM roles, found {len(resources)}"

    def test_cloudwatch_log_groups_exist(self, template: Template) -> None:
        """Template contains 5 CloudWatch log groups (agent + 4 MCP servers)."""
        template.resource_count_is("AWS::Logs::LogGroup", 5)


# ------------------------------------------------------------------
# Property 11: DynamoDB On-Demand Billing
# ------------------------------------------------------------------
class TestProperty11DynamoDBOnDemandBilling:
    """Validates: Property 11 — DynamoDB table uses PAY_PER_REQUEST billing."""

    def test_billing_mode_pay_per_request(self, template: Template) -> None:
        """DynamoDB table has BillingMode PAY_PER_REQUEST."""
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"BillingMode": "PAY_PER_REQUEST"},
        )

    def test_partition_key_is_species(self, template: Template) -> None:
        """DynamoDB table partition key is 'species' (String)."""
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "KeySchema": Match.array_with(
                    [{"AttributeName": "species", "KeyType": "HASH"}]
                ),
            },
        )

    def test_sort_key_is_date_location(self, template: Template) -> None:
        """DynamoDB table sort key is 'date_location' (String)."""
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "KeySchema": Match.array_with(
                    [{"AttributeName": "date_location", "KeyType": "RANGE"}]
                ),
            },
        )

    def test_gsi_conservation_status_date_index(self, template: Template) -> None:
        """DynamoDB table has GSI 'conservation_status-date-index'."""
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "GlobalSecondaryIndexes": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "IndexName": "conservation_status-date-index",
                                "KeySchema": Match.array_with(
                                    [
                                        {"AttributeName": "conservation_status", "KeyType": "HASH"},
                                        {"AttributeName": "date", "KeyType": "RANGE"},
                                    ]
                                ),
                            }
                        )
                    ]
                ),
            },
        )


# ------------------------------------------------------------------
# Property 12: IAM Least-Privilege
# ------------------------------------------------------------------
class TestProperty12IAMLeastPrivilege:
    """Validates: Property 12 — IAM roles have least-privilege permissions."""

    def test_wildlife_role_has_dynamodb_permissions(self, template: Template) -> None:
        """Wildlife Sightings role has DynamoDB PutItem, Query, Scan permissions."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": Match.array_with(
                                        [
                                            "dynamodb:PutItem",
                                            "dynamodb:Query",
                                            "dynamodb:Scan",
                                        ]
                                    ),
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    ),
                },
            },
        )

    def test_docs_role_has_s3_permissions(self, template: Template) -> None:
        """Conservation Docs role has S3 GetObject and ListBucket permissions."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": Match.array_with(
                                        [
                                            "s3:GetObject",
                                            "s3:ListBucket",
                                        ]
                                    ),
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    ),
                },
            },
        )

    def test_agent_role_has_bedrock_invoke_permission(self, template: Template) -> None:
        """Agent role has bedrock:InvokeModel permission scoped to Claude models."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": "bedrock:InvokeModel",
                                    "Effect": "Allow",
                                    "Resource": Match.array_with(
                                        [
                                            Match.string_like_regexp(
                                                ".*anthropic\\.claude-sonnet.*"
                                            ),
                                            Match.string_like_regexp(
                                                ".*anthropic\\.claude-haiku.*"
                                            ),
                                        ]
                                    ),
                                }
                            )
                        ]
                    ),
                },
            },
        )

    def test_all_roles_assumed_by_bedrock(self, template: Template) -> None:
        """All custom IAM roles are assumed by bedrock.amazonaws.com."""
        roles = template.find_resources(
            "AWS::IAM::Role",
            {
                "Properties": {
                    "AssumeRolePolicyDocument": {
                        "Statement": Match.array_with(
                            [
                                Match.object_like(
                                    {
                                        "Principal": {
                                            "Service": "bedrock.amazonaws.com"
                                        },
                                    }
                                )
                            ]
                        ),
                    },
                },
            },
        )
        # We expect at least 4 roles assumed by bedrock (wildlife, docs, weather, agent)
        assert len(roles) >= 4, f"Expected at least 4 bedrock-assumed roles, found {len(roles)}"

    def test_cloudwatch_logging_permissions_present(self, template: Template) -> None:
        """At least one IAM policy includes CloudWatch log stream/event permissions."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": Match.array_with(
                                        [
                                            "logs:CreateLogStream",
                                            "logs:PutLogEvents",
                                        ]
                                    ),
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    ),
                },
            },
        )


# ------------------------------------------------------------------
# Property 16: CDK Template Contains Frontend Infrastructure
# ------------------------------------------------------------------
class TestProperty16FrontendInfrastructure:
    """Validates: Property 16 — Template contains frontend infrastructure."""

    def test_s3_bucket_blocks_all_public_access(self, template: Template) -> None:
        """An S3 bucket has PublicAccessBlockConfiguration blocking all public access."""
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )

    def test_cloudfront_viewer_protocol_redirect_https(self, template: Template) -> None:
        """CloudFront distribution redirects to HTTPS."""
        template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": Match.object_like(
                    {
                        "DefaultCacheBehavior": Match.object_like(
                            {"ViewerProtocolPolicy": "redirect-to-https"}
                        ),
                    }
                ),
            },
        )

    def test_cloudfront_default_root_object(self, template: Template) -> None:
        """CloudFront distribution has default root object index.html."""
        template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": Match.object_like(
                    {"DefaultRootObject": "index.html"}
                ),
            },
        )

    def test_cloudfront_error_responses_403_404(self, template: Template) -> None:
        """CloudFront distribution has custom error responses for 403 and 404."""
        template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": Match.object_like(
                    {
                        "CustomErrorResponses": Match.array_with(
                            [
                                Match.object_like(
                                    {
                                        "ErrorCode": 403,
                                        "ResponseCode": 200,
                                        "ResponsePagePath": "/index.html",
                                    }
                                ),
                                Match.object_like(
                                    {
                                        "ErrorCode": 404,
                                        "ResponseCode": 200,
                                        "ResponsePagePath": "/index.html",
                                    }
                                ),
                            ]
                        ),
                    }
                ),
            },
        )

    def test_cloudfront_price_class_100(self, template: Template) -> None:
        """CloudFront distribution uses PRICE_CLASS_100."""
        template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": Match.object_like(
                    {"PriceClass": "PriceClass_100"}
                ),
            },
        )

    def test_cognito_user_pool_password_policy(self, template: Template) -> None:
        """Cognito User Pool has password policy: min 8, uppercase, lowercase, digits, symbols."""
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "Policies": {
                    "PasswordPolicy": Match.object_like(
                        {
                            "MinimumLength": 8,
                            "RequireUppercase": True,
                            "RequireLowercase": True,
                            "RequireNumbers": True,
                            "RequireSymbols": True,
                        }
                    ),
                },
            },
        )

    def test_cognito_user_pool_no_self_signup(self, template: Template) -> None:
        """Cognito User Pool has self-signup disabled."""
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "AdminCreateUserConfig": Match.object_like(
                    {"AllowAdminCreateUserOnly": True}
                ),
            },
        )

    def test_cognito_user_pool_client_auth_flows(self, template: Template) -> None:
        """Cognito User Pool Client supports USER_PASSWORD_AUTH and USER_SRP_AUTH."""
        template.has_resource_properties(
            "AWS::Cognito::UserPoolClient",
            {
                "ExplicitAuthFlows": Match.array_with(
                    [
                        "ALLOW_USER_PASSWORD_AUTH",
                        "ALLOW_USER_SRP_AUTH",
                    ]
                ),
            },
        )

    def test_http_api_protocol_http(self, template: Template) -> None:
        """HTTP API Gateway uses HTTP protocol."""
        template.has_resource_properties(
            "AWS::ApiGatewayV2::Api",
            {"ProtocolType": "HTTP"},
        )

    def test_jwt_authorizer_exists(self, template: Template) -> None:
        """HTTP API Gateway has a JWT authorizer."""
        template.has_resource_properties(
            "AWS::ApiGatewayV2::Authorizer",
            {"AuthorizerType": "JWT"},
        )

    def test_cloudwatch_log_group_names(self, template: Template) -> None:
        """CloudWatch log groups have expected names for agent and MCP servers."""
        expected_names = [
            "/bush-ranger/agent",
            "/bush-ranger/mcp/wildlife-sightings",
            "/bush-ranger/mcp/conservation-docs",
            "/bush-ranger/mcp/weather",
            "/bush-ranger/mcp/fetch",
        ]
        for name in expected_names:
            template.has_resource_properties(
                "AWS::Logs::LogGroup",
                {"LogGroupName": name},
            )

    def test_cloudfront_oac_exists(self, template: Template) -> None:
        """CloudFront Origin Access Control resource exists."""
        resources = template.find_resources("AWS::CloudFront::OriginAccessControl")
        assert len(resources) >= 1, f"Expected at least 1 OAC resource, found {len(resources)}"

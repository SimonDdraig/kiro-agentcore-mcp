# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Single CDK stack defining all Bush Ranger AI infrastructure resources."""

import sys
from pathlib import Path
from typing import Any

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    CfnResource,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import (
    aws_cognito as cognito,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_s3_deployment as s3deploy,
)
from constructs import Construct

# Add project root to path so we can import shared models
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from models.documents import DOCS_BUCKET_PREFIX
from models.sightings import GSI_NAME, PARTITION_KEY, SORT_KEY, TABLE_NAME


class BushRangerStack(Stack):
    """Single CDK stack provisioning all Bush Ranger AI resources."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        """Initialise the Bush Ranger AI stack with all resources."""
        super().__init__(scope, construct_id, **kwargs)

        # ----------------------------------------------------------------
        # 7.2  DynamoDB Table
        # ----------------------------------------------------------------
        self.sightings_table = self._create_dynamodb_table()

        # ----------------------------------------------------------------
        # 7.3  S3 Docs Bucket + BucketDeployment
        # ----------------------------------------------------------------
        self.docs_bucket = self._create_docs_bucket()

        # ----------------------------------------------------------------
        # 7.4  S3 Frontend Bucket
        # ----------------------------------------------------------------
        self.frontend_bucket = self._create_frontend_bucket()

        # ----------------------------------------------------------------
        # 7.5  CloudFront Distribution
        # ----------------------------------------------------------------
        self.distribution = self._create_cloudfront_distribution()

        # ----------------------------------------------------------------
        # 7.6  Cognito User Pool
        # ----------------------------------------------------------------
        self.user_pool = self._create_cognito_user_pool()

        # ----------------------------------------------------------------
        # 7.7  Cognito User Pool Client
        # ----------------------------------------------------------------
        self.user_pool_client = self._create_cognito_user_pool_client()

        # ----------------------------------------------------------------
        # 7.8  HTTP API Gateway
        # ----------------------------------------------------------------
        self.http_api = self._create_http_api()

        # ----------------------------------------------------------------
        # 7.11 CloudWatch Log Groups
        # ----------------------------------------------------------------
        self.log_groups = self._create_log_groups()

        # ----------------------------------------------------------------
        # 7.10 IAM Roles (least-privilege)
        # ----------------------------------------------------------------
        self.iam_roles = self._create_iam_roles()

        # ----------------------------------------------------------------
        # 7.9  AgentCore Runtimes
        # ----------------------------------------------------------------
        self.agent_runtime, self.mcp_server_runtimes = self._create_agentcore_runtimes()

        # ----------------------------------------------------------------
        # 7.12 Stack Outputs
        # ----------------------------------------------------------------
        self._create_outputs()

    # ------------------------------------------------------------------
    # 7.2  DynamoDB Table
    # ------------------------------------------------------------------
    def _create_dynamodb_table(self) -> dynamodb.Table:
        """Create the Wildlife Sightings DynamoDB table with GSI."""
        table = dynamodb.Table(
            self,
            "SightingsTable",
            table_name=TABLE_NAME,
            partition_key=dynamodb.Attribute(
                name=PARTITION_KEY,
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name=SORT_KEY,
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        table.add_global_secondary_index(
            index_name=GSI_NAME,
            partition_key=dynamodb.Attribute(
                name="conservation_status",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="date",
                type=dynamodb.AttributeType.STRING,
            ),
        )

        return table

    # ------------------------------------------------------------------
    # 7.3  S3 Docs Bucket + BucketDeployment
    # ------------------------------------------------------------------
    def _create_docs_bucket(self) -> s3.Bucket:
        """Create the conservation documents S3 bucket and deploy sample docs."""
        bucket = s3.Bucket(
            self,
            "DocsBucket",
            bucket_name=f"{DOCS_BUCKET_PREFIX}-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        sample_docs_path = str(Path(__file__).resolve().parent.parent.parent / "config" / "sample_documents")

        s3deploy.BucketDeployment(
            self,
            "DeploySampleDocs",
            sources=[s3deploy.Source.asset(sample_docs_path)],
            destination_bucket=bucket,
        )

        return bucket

    # ------------------------------------------------------------------
    # 7.4  S3 Frontend Bucket
    # ------------------------------------------------------------------
    def _create_frontend_bucket(self) -> s3.Bucket:
        """Create the private S3 bucket for frontend static assets."""
        return s3.Bucket(
            self,
            "FrontendBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

    # ------------------------------------------------------------------
    # 7.5  CloudFront Distribution
    # ------------------------------------------------------------------
    def _create_cloudfront_distribution(self) -> cloudfront.Distribution:
        """Create CloudFront distribution with OAC to the frontend bucket."""
        return cloudfront.Distribution(
            self,
            "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    self.frontend_bucket,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
        )

    # ------------------------------------------------------------------
    # 7.6  Cognito User Pool
    # ------------------------------------------------------------------
    def _create_cognito_user_pool(self) -> cognito.UserPool:
        """Create Cognito User Pool with email sign-in and password policy."""
        return cognito.UserPool(
            self,
            "BushRangerUserPool",
            user_pool_name="BushRangerUserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )

    # ------------------------------------------------------------------
    # 7.7  Cognito User Pool Client
    # ------------------------------------------------------------------
    def _create_cognito_user_pool_client(self) -> cognito.UserPoolClient:
        """Create Cognito User Pool Client for the frontend SPA."""
        return self.user_pool.add_client(
            "BushRangerAppClient",
            user_pool_client_name="BushRangerAppClient",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            access_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            generate_secret=False,
        )

    # ------------------------------------------------------------------
    # 7.8  HTTP API Gateway
    # ------------------------------------------------------------------
    def _create_http_api(self) -> apigwv2.CfnApi:
        """Create HTTP API Gateway with JWT authorizer and CORS."""
        # HTTP API
        api = apigwv2.CfnApi(
            self,
            "BushRangerHttpApi",
            name="BushRangerHttpApi",
            protocol_type="HTTP",
            cors_configuration=apigwv2.CfnApi.CorsProperty(
                allow_origins=[f"https://{self.distribution.distribution_domain_name}"],
                allow_methods=["POST", "OPTIONS"],
                allow_headers=["Authorization", "Content-Type"],
                max_age=3600,
            ),
        )

        # JWT Authorizer (Cognito)
        authorizer = apigwv2.CfnAuthorizer(
            self,
            "CognitoJwtAuthorizer",
            api_id=api.ref,
            authorizer_type="JWT",
            name="CognitoJwtAuthorizer",
            identity_source=["$request.header.Authorization"],
            jwt_configuration=apigwv2.CfnAuthorizer.JWTConfigurationProperty(
                audience=[self.user_pool_client.user_pool_client_id],
                issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}",
            ),
        )

        # POST /invoke route
        apigwv2.CfnRoute(
            self,
            "InvokeRoute",
            api_id=api.ref,
            route_key="POST /invoke",
            authorization_type="JWT",
            authorizer_id=authorizer.ref,
        )

        # Stage (auto-deploy)
        apigwv2.CfnStage(
            self,
            "DefaultStage",
            api_id=api.ref,
            stage_name="$default",
            auto_deploy=True,
        )

        return api

    # ------------------------------------------------------------------
    # 7.11 CloudWatch Log Groups
    # ------------------------------------------------------------------
    def _create_log_groups(self) -> dict[str, logs.LogGroup]:
        """Create CloudWatch log groups for agent and each MCP server."""
        log_group_names = {
            "agent": "/bush-ranger/agent",
            "wildlife_sightings": "/bush-ranger/mcp/wildlife-sightings",
            "conservation_docs": "/bush-ranger/mcp/conservation-docs",
            "weather": "/bush-ranger/mcp/weather",
            "fetch": "/bush-ranger/mcp/fetch",
        }

        groups: dict[str, logs.LogGroup] = {}
        for key, name in log_group_names.items():
            groups[key] = logs.LogGroup(
                self,
                f"LogGroup-{key}",
                log_group_name=name,
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=RemovalPolicy.DESTROY,
            )

        return groups

    # ------------------------------------------------------------------
    # 7.10 IAM Roles (least-privilege)
    # ------------------------------------------------------------------
    def _create_iam_roles(self) -> dict[str, iam.Role]:
        """Create IAM roles with least-privilege permissions per component."""
        roles: dict[str, iam.Role] = {}

        # Wildlife Sightings Server role
        wildlife_role = iam.Role(
            self,
            "WildlifeSightingsRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Wildlife Sightings MCP server",
        )
        wildlife_role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem", "dynamodb:Query", "dynamodb:Scan"],
                resources=[
                    self.sightings_table.table_arn,
                    f"{self.sightings_table.table_arn}/index/{GSI_NAME}",
                ],
            )
        )
        wildlife_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[self.log_groups["wildlife_sightings"].log_group_arn],
            )
        )
        roles["wildlife_sightings"] = wildlife_role

        # Conservation Docs Server role
        docs_role = iam.Role(
            self,
            "ConservationDocsRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Conservation Docs MCP server",
        )
        docs_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[
                    self.docs_bucket.bucket_arn,
                    f"{self.docs_bucket.bucket_arn}/*",
                ],
            )
        )
        docs_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[self.log_groups["conservation_docs"].log_group_arn],
            )
        )
        roles["conservation_docs"] = docs_role

        # Weather Server role (no AWS permissions needed, only logging)
        weather_role = iam.Role(
            self,
            "WeatherServerRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Weather MCP server",
        )
        weather_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[self.log_groups["weather"].log_group_arn],
            )
        )
        roles["weather"] = weather_role

        # Strands Agent role
        agent_role = iam.Role(
            self,
            "StrandsAgentRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Strands Agent (Bush Ranger AI)",
        )
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-sonnet-4-20250514",
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-haiku-4-20250514",
                ],
            )
        )
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[self.log_groups["agent"].log_group_arn],
            )
        )
        roles["agent"] = agent_role

        return roles

    # ------------------------------------------------------------------
    # 7.9  AgentCore Runtimes
    # ------------------------------------------------------------------
    def _create_agentcore_runtimes(
        self,
    ) -> tuple[CfnResource, dict[str, CfnResource]]:
        """Create AgentCore agent runtime and MCP server runtimes.

        Uses CfnResource since L2 constructs for AgentCore may not yet exist.
        """
        mcp_servers: dict[str, CfnResource] = {}

        # Wildlife Sightings MCP Server Runtime
        mcp_servers["wildlife_sightings"] = CfnResource(
            self,
            "WildlifeSightingsMcpRuntime",
            type="AWS::BedrockAgentCore::McpServerRuntime",
            properties={
                "Name": "wildlife-sightings-server",
                "Description": "MCP server for wildlife sighting records backed by DynamoDB",
                "RoleArn": self.iam_roles["wildlife_sightings"].role_arn,
                "LogGroupName": self.log_groups["wildlife_sightings"].log_group_name,
            },
        )

        # Conservation Docs MCP Server Runtime
        mcp_servers["conservation_docs"] = CfnResource(
            self,
            "ConservationDocsMcpRuntime",
            type="AWS::BedrockAgentCore::McpServerRuntime",
            properties={
                "Name": "conservation-docs-server",
                "Description": "MCP server for conservation documents backed by S3",
                "RoleArn": self.iam_roles["conservation_docs"].role_arn,
                "LogGroupName": self.log_groups["conservation_docs"].log_group_name,
            },
        )

        # Weather MCP Server Runtime
        mcp_servers["weather"] = CfnResource(
            self,
            "WeatherMcpRuntime",
            type="AWS::BedrockAgentCore::McpServerRuntime",
            properties={
                "Name": "weather-server",
                "Description": "MCP server for weather data via Open-Meteo API",
                "RoleArn": self.iam_roles["weather"].role_arn,
                "LogGroupName": self.log_groups["weather"].log_group_name,
            },
        )

        # Fetch Server (third-party) MCP Server Runtime
        mcp_servers["fetch"] = CfnResource(
            self,
            "FetchMcpRuntime",
            type="AWS::BedrockAgentCore::McpServerRuntime",
            properties={
                "Name": "fetch-server",
                "Description": "Third-party MCP server (@modelcontextprotocol/server-fetch) for live web content",
                "ThirdPartyPackage": "@modelcontextprotocol/server-fetch",
                "LogGroupName": self.log_groups["fetch"].log_group_name,
            },
        )

        # Strands Agent Runtime
        agent_runtime = CfnResource(
            self,
            "BushRangerAgentRuntime",
            type="AWS::BedrockAgentCore::AgentRuntime",
            properties={
                "Name": "bush-ranger-agent",
                "Description": "Bush Ranger AI - Australian Wildlife & Conservation Agent",
                "RoleArn": self.iam_roles["agent"].role_arn,
                "LogGroupName": self.log_groups["agent"].log_group_name,
                "McpServers": [server.ref for server in mcp_servers.values()],
            },
        )

        return agent_runtime, mcp_servers

    # ------------------------------------------------------------------
    # 7.12 Stack Outputs
    # ------------------------------------------------------------------
    def _create_outputs(self) -> None:
        """Add CDK stack outputs for all key resource identifiers."""
        CfnOutput(
            self,
            "AgentEndpoint",
            value=self.agent_runtime.ref,
            description="AgentCore agent runtime endpoint",
            export_name="BushRangerAgentEndpoint",
        )

        CfnOutput(
            self,
            "DynamoDBTableName",
            value=self.sightings_table.table_name,
            description="DynamoDB sightings table name",
            export_name="BushRangerTableName",
        )

        CfnOutput(
            self,
            "DocsBucketName",
            value=self.docs_bucket.bucket_name,
            description="S3 conservation documents bucket name",
            export_name="BushRangerDocsBucket",
        )

        CfnOutput(
            self,
            "FrontendBucketName",
            value=self.frontend_bucket.bucket_name,
            description="S3 frontend static assets bucket name",
            export_name="BushRangerFrontendBucket",
        )

        CfnOutput(
            self,
            "CloudFrontURL",
            value=f"https://{self.distribution.distribution_domain_name}",
            description="CloudFront distribution URL",
            export_name="BushRangerCloudFrontURL",
        )

        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID",
            export_name="BushRangerUserPoolId",
        )

        CfnOutput(
            self,
            "CognitoUserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
            export_name="BushRangerUserPoolClientId",
        )

        CfnOutput(
            self,
            "ApiGatewayUrl",
            value=cdk.Fn.join("", ["https://", self.http_api.ref, ".execute-api.", self.region, ".amazonaws.com"]),
            description="HTTP API Gateway endpoint URL",
            export_name="BushRangerApiGatewayUrl",
        )

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
    aws_ecr_assets as ecr_assets,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as _lambda,
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
from aws_cdk import (
    custom_resources as cr,
)
from constructs import Construct

# Add project root to path so we can import shared models
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from models.documents import DOCS_BUCKET_PREFIX
from models.rangers import PARTITION_KEY as RANGERS_PARTITION_KEY
from models.rangers import TABLE_NAME as RANGERS_TABLE_NAME
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
        # DynamoDB Rangers Table
        # ----------------------------------------------------------------
        self.rangers_table = self._create_rangers_table()

        # ----------------------------------------------------------------
        # 7.3  S3 Docs Bucket + BucketDeployment
        # ----------------------------------------------------------------
        self.docs_bucket = self._create_docs_bucket()

        # ----------------------------------------------------------------
        # Bedrock Knowledge Base (semantic search)
        # ----------------------------------------------------------------
        self.knowledge_base, self.data_source = self._create_knowledge_base()

        # ----------------------------------------------------------------
        # Bedrock KB ingestion (auto-sync after doc upload)
        # ----------------------------------------------------------------
        self._create_kb_ingestion_trigger()

        # ----------------------------------------------------------------
        # 7.4  S3 Frontend Bucket
        # ----------------------------------------------------------------
        self.frontend_bucket = self._create_frontend_bucket()

        # ----------------------------------------------------------------
        # 7.5  CloudFront Distribution
        # ----------------------------------------------------------------
        self.distribution = self._create_cloudfront_distribution()

        # Deploy frontend build output to the S3 bucket
        frontend_dist = str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist")
        s3deploy.BucketDeployment(
            self,
            "DeployFrontend",
            sources=[s3deploy.Source.asset(frontend_dist)],
            destination_bucket=self.frontend_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )

        # ----------------------------------------------------------------
        # 7.6  Cognito User Pool
        # ----------------------------------------------------------------
        self.user_pool = self._create_cognito_user_pool()

        # ----------------------------------------------------------------
        # 7.7  Cognito User Pool Client
        # ----------------------------------------------------------------
        self.user_pool_client = self._create_cognito_user_pool_client()

        # ----------------------------------------------------------------
        # Cognito M2M (agent-to-MCP auth via client_credentials grant)
        # ----------------------------------------------------------------
        self.m2m_domain, self.m2m_resource_server, self.m2m_client = self._create_cognito_m2m_resources()

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
        # 7.13 API Lambda (proxies to AgentCore Runtime)
        # ----------------------------------------------------------------
        self._create_api_lambda()

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
    # DynamoDB Rangers Table
    # ------------------------------------------------------------------
    def _create_rangers_table(self) -> dynamodb.Table:
        """Create the BushRangers DynamoDB table for ranger profiles."""
        return dynamodb.Table(
            self,
            "RangersTable",
            table_name=RANGERS_TABLE_NAME,
            partition_key=dynamodb.Attribute(
                name=RANGERS_PARTITION_KEY,
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

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
    # Bedrock Knowledge Base
    # ------------------------------------------------------------------
    def _create_knowledge_base(self) -> tuple[CfnResource, CfnResource]:
        """Create a Bedrock Knowledge Base with S3 Vectors store and data source."""
        embedding_model_arn = "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
        vector_bucket_name = f"br-kb-{self.account}-{self.region}"

        # IAM role for the Knowledge Base
        self.kb_role = iam.Role(
            self,
            "KnowledgeBaseRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Bedrock Knowledge Base to read docs and invoke embeddings",
        )
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[
                    self.docs_bucket.bucket_arn,
                    f"{self.docs_bucket.bucket_arn}/*",
                ],
            )
        )
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[embedding_model_arn],
            )
        )
        self.kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vectors:CreateIndex",
                    "s3vectors:GetIndex",
                    "s3vectors:DeleteIndex",
                    "s3vectors:PutVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:QueryVectors",
                    "s3vectors:ListVectors",
                ],
                resources=[
                    f"arn:aws:s3vectors:{self.region}:{self.account}:bucket/{vector_bucket_name}",
                    f"arn:aws:s3vectors:{self.region}:{self.account}:bucket/{vector_bucket_name}/*",
                ],
            )
        )

        # S3 Vector Bucket for KB embeddings
        self.vector_bucket = CfnResource(
            self,
            "KBVectorBucket",
            type="AWS::S3Vectors::VectorBucket",
            properties={
                "VectorBucketName": vector_bucket_name,
            },
        )

        # S3 Vector Index (Titan v2 = 1024 dimensions)
        self.vector_index = CfnResource(
            self,
            "KBVectorIndex",
            type="AWS::S3Vectors::Index",
            properties={
                "VectorBucketName": vector_bucket_name,
                "IndexName": "bush-ranger-kb-index",
                "DataType": "float32",
                "Dimension": 1024,
                "DistanceMetric": "cosine",
            },
        )
        self.vector_index.add_dependency(self.vector_bucket)

        # Knowledge Base
        knowledge_base = CfnResource(
            self,
            "BedrockKnowledgeBase",
            type="AWS::Bedrock::KnowledgeBase",
            properties={
                "Name": "bush-ranger-knowledge-base",
                "Description": "Knowledge Base for Bush Ranger conservation documents",
                "RoleArn": self.kb_role.role_arn,
                "KnowledgeBaseConfiguration": {
                    "Type": "VECTOR",
                    "VectorKnowledgeBaseConfiguration": {
                        "EmbeddingModelArn": embedding_model_arn,
                    },
                },
                "StorageConfiguration": {
                    "Type": "S3_VECTORS",
                    "S3VectorsConfiguration": {
                        "VectorBucketArn": self.vector_bucket.get_att("VectorBucketArn").to_string(),
                        "IndexArn": self.vector_index.get_att("IndexArn").to_string(),
                    },
                },
            },
        )
        knowledge_base.add_dependency(self.vector_index)

        # Ensure IAM policy is fully created before KB validates permissions
        default_policy = self.kb_role.node.try_find_child("DefaultPolicy")
        if default_policy:
            knowledge_base.node.add_dependency(default_policy)

        # Data Source with fixed-size chunking
        data_source = CfnResource(
            self,
            "BedrockDataSource",
            type="AWS::Bedrock::DataSource",
            properties={
                "Name": "bush-ranger-docs-datasource",
                "Description": "Data source for conservation documents from S3",
                "KnowledgeBaseId": knowledge_base.ref,
                "DataSourceConfiguration": {
                    "Type": "S3",
                    "S3Configuration": {
                        "BucketArn": self.docs_bucket.bucket_arn,
                    },
                },
                "VectorIngestionConfiguration": {
                    "ChunkingConfiguration": {
                        "ChunkingStrategy": "FIXED_SIZE",
                        "FixedSizeChunkingConfiguration": {
                            "MaxTokens": 300,
                            "OverlapPercentage": 20,
                        },
                    },
                },
            },
        )

        return knowledge_base, data_source

    def _create_kb_ingestion_trigger(self) -> cr.AwsCustomResource:
        """Trigger a Bedrock Knowledge Base ingestion job after deploy.

        Uses an AwsCustomResource to call StartIngestionJob so the KB
        indexes the sample documents automatically during ``cdk deploy``.
        """
        kb_id = self.knowledge_base.ref
        ds_id = self.data_source.get_att("DataSourceId").to_string()

        return cr.AwsCustomResource(
            self,
            "KBIngestionTrigger",
            on_create=cr.AwsSdkCall(
                service="BedrockAgent",
                action="startIngestionJob",
                parameters={
                    "knowledgeBaseId": kb_id,
                    "dataSourceId": ds_id,
                },
                physical_resource_id=cr.PhysicalResourceId.of("kb-ingestion-trigger"),
            ),
            on_update=cr.AwsSdkCall(
                service="BedrockAgent",
                action="startIngestionJob",
                parameters={
                    "knowledgeBaseId": kb_id,
                    "dataSourceId": ds_id,
                },
                physical_resource_id=cr.PhysicalResourceId.of("kb-ingestion-trigger"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["bedrock:StartIngestionJob"],
                        resources=["*"],
                    ),
                ]
            ),
        )

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
    def _create_cognito_m2m_resources(
        self,
    ) -> tuple[cognito.UserPoolDomain, cognito.UserPoolResourceServer, cognito.UserPoolClient]:
        """Create Cognito domain, resource server, and M2M client for agent-to-MCP auth.

        The client_credentials grant requires a domain (token endpoint),
        a resource server (custom scopes), and an app client with a secret.
        """
        # Cognito domain — required for the OAuth2 token endpoint
        domain = self.user_pool.add_domain(
            "BushRangerDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"bush-ranger-{self.account}",
            ),
        )

        # Resource server with a custom scope for MCP access
        mcp_scope = cognito.ResourceServerScope(
            scope_name="invoke",
            scope_description="Invoke MCP servers",
        )
        resource_server = self.user_pool.add_resource_server(
            "BushRangerMcpResourceServer",
            identifier="mcp",
            scopes=[mcp_scope],
        )

        # M2M app client with secret — uses client_credentials grant
        m2m_client = self.user_pool.add_client(
            "BushRangerM2MClient",
            user_pool_client_name="BushRangerM2MClient",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.resource_server(resource_server, mcp_scope),
                ],
            ),
            access_token_validity=Duration.hours(1),
        )

        return domain, resource_server, m2m_client

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

        # POST /invoke route (target set later by _create_api_lambda)
        self.invoke_route = apigwv2.CfnRoute(
            self,
            "InvokeRoute",
            api_id=api.ref,
            route_key="POST /invoke",
            authorization_type="JWT",
            authorizer_id=authorizer.ref,
        )

        # Access log group for API requests
        api_log_group = logs.LogGroup(
            self,
            "ApiAccessLogGroup",
            log_group_name="/bush-ranger/api-gateway",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Stage (auto-deploy) with access logging and metrics
        apigwv2.CfnStage(
            self,
            "DefaultStage",
            api_id=api.ref,
            stage_name="$default",
            auto_deploy=True,
            access_log_settings=apigwv2.CfnStage.AccessLogSettingsProperty(
                destination_arn=api_log_group.log_group_arn,
                format=(
                    '{"requestId":"$context.requestId",'
                    '"ip":"$context.identity.sourceIp",'
                    '"requestTime":"$context.requestTime",'
                    '"httpMethod":"$context.httpMethod",'
                    '"routeKey":"$context.routeKey",'
                    '"status":"$context.status",'
                    '"protocol":"$context.protocol",'
                    '"responseLength":"$context.responseLength",'
                    '"integrationError":"$context.integrationErrorMessage",'
                    '"errorMessage":"$context.error.message"}'
                ),
            ),
            default_route_settings=apigwv2.CfnStage.RouteSettingsProperty(
                detailed_metrics_enabled=True,
                throttling_burst_limit=50,
                throttling_rate_limit=100,
            ),
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
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock.amazonaws.com"),
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            ),
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
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock.amazonaws.com"),
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            ),
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
                actions=["bedrock:Retrieve"],
                resources=[self.knowledge_base.get_att("KnowledgeBaseArn").to_string()],
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
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock.amazonaws.com"),
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            ),
            description="Role for Weather MCP server",
        )
        weather_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[self.log_groups["weather"].log_group_arn],
            )
        )
        roles["weather"] = weather_role

        # ECR pull permissions — AgentCore needs these on each MCP server
        # execution role to pull the container image during runtime creation.
        _ecr_repo_arn = (
            f"arn:aws:ecr:{self.region}:{self.account}:repository/"
            f"cdk-hnb659fds-container-assets-{self.account}-{self.region}"
        )
        for role_key in ("wildlife_sightings", "conservation_docs", "weather"):
            roles[role_key].add_to_policy(
                iam.PolicyStatement(
                    actions=["ecr:GetAuthorizationToken"],
                    resources=["*"],
                )
            )
            roles[role_key].add_to_policy(
                iam.PolicyStatement(
                    actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                    resources=[_ecr_repo_arn],
                )
            )
            # AgentCore runtime logging — enables container stdout in CloudWatch
            roles[role_key].add_to_policy(
                iam.PolicyStatement(
                    actions=["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                    resources=[
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*",
                    ],
                )
            )
            roles[role_key].add_to_policy(
                iam.PolicyStatement(
                    actions=["logs:DescribeLogGroups"],
                    resources=[
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:*",
                    ],
                )
            )
            roles[role_key].add_to_policy(
                iam.PolicyStatement(
                    actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                    resources=[
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
                    ],
                )
            )

        # Strands Agent role
        agent_role = iam.Role(
            self,
            "StrandsAgentRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock.amazonaws.com"),
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            ),
            description="Role for Strands Agent (Bush Ranger AI)",
        )
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    # Foundation model ARNs
                    "arn:aws:bedrock:*::foundation-model/*anthropic.claude-sonnet-4-5-20250929-v1:0",
                    "arn:aws:bedrock:*::foundation-model/*anthropic.claude-haiku-4-5-20251001-v1:0",
                    # Inference profile ARNs (Bedrock resolves models to these)
                    f"arn:aws:bedrock:*:{self.account}:inference-profile/*",
                ],
            )
        )
        # AgentCore runtime logging — required by the runtime infrastructure
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*",
                ],
            )
        )
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:DescribeLogGroups"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:*",
                ],
            )
        )
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
                ],
            )
        )
        # X-Ray tracing — required by AgentCore observability
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                resources=["*"],
            )
        )
        # CloudWatch metrics — required by AgentCore runtime
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={
                    "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"},
                },
            )
        )
        # Workload identity tokens — needed for agent-to-MCP auth via OAuth
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/*",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default/*",
                ],
            )
        )
        # InvokeAgentRuntime on MCP server runtimes — added after runtimes are created
        # (see _create_agentcore_runtimes)
        # ECR pull permissions for containerised agent
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                resources=[_ecr_repo_arn],
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
        """Create AgentCore runtimes for the agent and MCP servers.

        Architecture:
        - Each MCP server is containerised, pushed to ECR via
          ``DockerImageAsset``, and deployed as an
          ``AWS::BedrockAgentCore::Runtime`` with ``ContainerConfiguration``
          and ``ProtocolConfiguration: MCP``.
        - Inbound auth on MCP servers uses ``CustomJWTAuthorizer`` wired
          to the Cognito User Pool. The agent authenticates using a
          Cognito access token obtained via client_credentials grant.
        - The Strands agent is an ``AWS::BedrockAgentCore::Runtime`` using
          ``ContainerConfiguration`` that connects to MCP servers via
          their runtime ARNs (env vars).
        """
        _network_public: dict[str, str] = {"NetworkMode": "PUBLIC"}
        _services = Path(__file__).resolve().parent.parent.parent / "services"
        _exclude = ["__pycache__", "**/__pycache__", "*.pyc", "**/*.pyc"]

        # -- Cognito JWT authorizer config for MCP server inbound auth --
        _cognito_discovery_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com"
            f"/{self.user_pool.user_pool_id}/.well-known/openid-configuration"
        )
        _mcp_authorizer: dict[str, Any] = {
            "CustomJWTAuthorizer": {
                "DiscoveryUrl": _cognito_discovery_url,
                "AllowedClients": [self.m2m_client.user_pool_client_id],
            },
        }

        # -- Build Docker images for each MCP server and push to ECR --
        wildlife_image = ecr_assets.DockerImageAsset(
            self,
            "WildlifeImage",
            directory=str(_services / "mcp_servers" / "wildlife_sightings"),
            exclude=_exclude,
            platform=ecr_assets.Platform.LINUX_ARM64,
        )
        docs_image = ecr_assets.DockerImageAsset(
            self,
            "DocsImage",
            directory=str(_services / "mcp_servers" / "conservation_docs"),
            exclude=_exclude,
            platform=ecr_assets.Platform.LINUX_ARM64,
        )
        weather_image = ecr_assets.DockerImageAsset(
            self,
            "WeatherImage",
            directory=str(_services / "mcp_servers" / "weather"),
            exclude=_exclude,
            platform=ecr_assets.Platform.LINUX_ARM64,
        )

        # -- Agent code as Docker image (containerised for fast cold start) --
        agent_image = ecr_assets.DockerImageAsset(
            self,
            "AgentImage",
            directory=str(_services / "agent"),
            exclude=_exclude,
            platform=ecr_assets.Platform.LINUX_ARM64,
        )

        mcp_servers: dict[str, CfnResource] = {}

        # Wildlife Sightings MCP Server Runtime (container)
        mcp_servers["wildlife_sightings"] = CfnResource(
            self,
            "WildlifeSightingsMcpRuntime",
            type="AWS::BedrockAgentCore::Runtime",
            properties={
                "AgentRuntimeName": "wildlife_sightings_server",
                "Description": "MCP server for wildlife sighting records backed by DynamoDB",
                "RoleArn": self.iam_roles["wildlife_sightings"].role_arn,
                "NetworkConfiguration": _network_public,
                "ProtocolConfiguration": "MCP",
                "AuthorizerConfiguration": _mcp_authorizer,
                "AgentRuntimeArtifact": {
                    "ContainerConfiguration": {
                        "ContainerUri": wildlife_image.image_uri,
                    },
                },
            },
        )

        # Conservation Docs MCP Server Runtime (container)
        mcp_servers["conservation_docs"] = CfnResource(
            self,
            "ConservationDocsMcpRuntime",
            type="AWS::BedrockAgentCore::Runtime",
            properties={
                "AgentRuntimeName": "conservation_docs_server",
                "Description": "MCP server for conservation documents backed by S3",
                "RoleArn": self.iam_roles["conservation_docs"].role_arn,
                "NetworkConfiguration": _network_public,
                "ProtocolConfiguration": "MCP",
                "AuthorizerConfiguration": _mcp_authorizer,
                "EnvironmentVariables": {
                    "KNOWLEDGE_BASE_ID": self.knowledge_base.ref,
                    "DOCS_BUCKET_NAME": self.docs_bucket.bucket_name,
                },
                "AgentRuntimeArtifact": {
                    "ContainerConfiguration": {
                        "ContainerUri": docs_image.image_uri,
                    },
                },
            },
        )

        # Weather MCP Server Runtime (container)
        mcp_servers["weather"] = CfnResource(
            self,
            "WeatherMcpRuntime",
            type="AWS::BedrockAgentCore::Runtime",
            properties={
                "AgentRuntimeName": "weather_server",
                "Description": "MCP server for weather data via Open-Meteo API",
                "RoleArn": self.iam_roles["weather"].role_arn,
                "NetworkConfiguration": _network_public,
                "ProtocolConfiguration": "MCP",
                "AuthorizerConfiguration": _mcp_authorizer,
                "AgentRuntimeArtifact": {
                    "ContainerConfiguration": {
                        "ContainerUri": weather_image.image_uri,
                    },
                },
            },
        )

        # Ensure IAM policies are fully created before runtimes validate ECR access
        for key in ("wildlife_sightings", "conservation_docs", "weather"):
            role_policy = self.iam_roles[key].node.try_find_child("DefaultPolicy")
            if role_policy:
                mcp_servers[key].node.add_dependency(role_policy)

        # Grant agent role permission to invoke MCP server runtimes
        self.iam_roles["agent"].add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[
                    mcp_servers["wildlife_sightings"].get_att("AgentRuntimeArn").to_string(),
                    mcp_servers["conservation_docs"].get_att("AgentRuntimeArn").to_string(),
                    mcp_servers["weather"].get_att("AgentRuntimeArn").to_string(),
                ],
            )
        )

        # Ensure agent role IAM policy is created before runtime validates ECR
        agent_role_policy = self.iam_roles["agent"].node.try_find_child("DefaultPolicy")

        # Strands Agent Runtime (containerised for fast cold start)
        agent_runtime = CfnResource(
            self,
            "BushRangerAgentRuntime",
            type="AWS::BedrockAgentCore::Runtime",
            properties={
                "AgentRuntimeName": "bush_ranger_agent",
                "Description": "Bush Ranger AI - Australian Wildlife & Conservation Agent",
                "RoleArn": self.iam_roles["agent"].role_arn,
                "NetworkConfiguration": _network_public,
                "EnvironmentVariables": {
                    "WILDLIFE_SIGHTINGS_RUNTIME_ARN": mcp_servers["wildlife_sightings"]
                    .get_att("AgentRuntimeArn")
                    .to_string(),
                    "CONSERVATION_DOCS_RUNTIME_ARN": mcp_servers["conservation_docs"]
                    .get_att("AgentRuntimeArn")
                    .to_string(),
                    "WEATHER_RUNTIME_ARN": mcp_servers["weather"].get_att("AgentRuntimeArn").to_string(),
                    "COGNITO_TOKEN_URL": (
                        f"https://bush-ranger-{self.account}.auth.{self.region}.amazoncognito.com/oauth2/token"
                    ),
                    "COGNITO_M2M_CLIENT_ID": self.m2m_client.user_pool_client_id,
                    "COGNITO_M2M_CLIENT_SECRET": self.m2m_client.user_pool_client_secret.unsafe_unwrap(),
                    "COGNITO_M2M_SCOPE": "mcp/invoke",
                },
                "AgentRuntimeArtifact": {
                    "ContainerConfiguration": {
                        "ContainerUri": agent_image.image_uri,
                    },
                },
            },
        )
        if agent_role_policy:
            agent_runtime.node.add_dependency(agent_role_policy)

        return agent_runtime, mcp_servers

    # ------------------------------------------------------------------
    # 7.13 API Lambda
    # ------------------------------------------------------------------
    def _create_api_lambda(self) -> None:
        """Create a Lambda that proxies API Gateway to the AgentCore Runtime."""
        _services = Path(__file__).resolve().parent.parent.parent / "services"

        api_fn = _lambda.Function(
            self,
            "ApiLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(_services / "api")),
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "AGENT_RUNTIME_ARN": self.agent_runtime.get_att("AgentRuntimeArn").to_string(),
                "CORS_ORIGIN": f"https://{self.distribution.distribution_domain_name}",
            },
        )

        # Permission to invoke the agent runtime (including endpoints)
        _rt_arn = self.agent_runtime.get_att("AgentRuntimeArn").to_string()
        api_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[
                    _rt_arn,
                    cdk.Fn.join("", [_rt_arn, "/*"]),
                ],
            )
        )

        # API Gateway integration → Lambda
        integration = apigwv2.CfnIntegration(
            self,
            "InvokeLambdaIntegration",
            api_id=self.http_api.ref,
            integration_type="AWS_PROXY",
            integration_uri=api_fn.function_arn,
            payload_format_version="2.0",
        )

        # Grant API Gateway permission to invoke the Lambda
        api_fn.add_permission(
            "ApiGwInvoke",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=cdk.Fn.join(
                "",
                [
                    "arn:aws:execute-api:",
                    self.region,
                    ":",
                    self.account,
                    ":",
                    self.http_api.ref,
                    "/*/*/invoke",
                ],
            ),
        )

        # Wire the route to the integration
        self.invoke_route.add_property_override(
            "Target",
            cdk.Fn.join("", ["integrations/", integration.ref]),
        )

    # ------------------------------------------------------------------
    # 7.12 Stack Outputs
    # ------------------------------------------------------------------
    def _create_outputs(self) -> None:
        """Add CDK stack outputs for all key resource identifiers."""
        CfnOutput(
            self,
            "AgentEndpoint",
            value=self.agent_runtime.get_att("AgentRuntimeArn").to_string(),
            description="AgentCore agent runtime ARN",
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

        CfnOutput(
            self,
            "KnowledgeBaseId",
            value=self.knowledge_base.ref,
            description="Bedrock Knowledge Base ID",
            export_name="BushRangerKnowledgeBaseId",
        )

        CfnOutput(
            self,
            "DataSourceId",
            value=self.data_source.get_att("DataSourceId").to_string(),
            description="Bedrock Knowledge Base Data Source ID",
            export_name="BushRangerDataSourceId",
        )

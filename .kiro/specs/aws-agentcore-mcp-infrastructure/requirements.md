# Requirements Document

## Introduction

This project builds "Bush Ranger AI" — an Australian Wildlife & Conservation Agent hosted on AWS AgentCore. The agent assists park rangers by tracking wildlife sightings, checking environmental conditions, and accessing conservation documents. The system consists of three custom MCP (Model Context Protocol) servers, one third-party MCP server, and a Strands-based agent deployed via AWS AgentCore. All infrastructure is defined using AWS CDK (Python) and deployed to the us-east-1 region.

The agent uses Claude Sonnet as the primary reasoning model and Claude Haiku for lighter tasks, keeping costs minimal while following AWS best practices.

## Glossary

- **AgentCore**: AWS service that provides a managed runtime for hosting AI agents and MCP servers, handling scaling, networking, and lifecycle management
- **MCP_Server**: A Model Context Protocol server that exposes a set of tools over a standardized protocol, allowing agents to discover and invoke them
- **Strands_Agent**: An AI agent built with the Strands Agents SDK (Python) that reasons over user requests and invokes tools exposed by MCP servers
- **MCP_Tool**: A discrete capability exposed by an MCP server (e.g., query a database, fetch a document, call an API)
- **Infrastructure_Stack**: The AWS CDK (Python) stack that defines and deploys all cloud components
- **Tool_Registry**: The configuration within AgentCore that maps the Strands Agent to its available MCP servers and their tools
- **Wildlife_Sightings_Server**: MCP server backed by DynamoDB for storing and querying wildlife sighting records
- **Conservation_Docs_Server**: MCP server backed by S3 for retrieving conservation documents (markdown/PDF)
- **Weather_Server**: MCP server that queries the Open-Meteo free API for Australian weather conditions and forecasts
- **Fetch_Server**: Third-party MCP server (@modelcontextprotocol/server-fetch) for fetching live content from government wildlife sites
- **Open_Meteo_API**: Free weather API (no API key required) that provides weather data, forecasts, and climate information for Australian locations
- **Sighting_Record**: A data record containing species name, location (lat/lng), date, conservation status, and observer notes
- **CloudScape_UI**: AWS CloudScape Design System (@cloudscape-design/components), the React component library used for the frontend interface
- **Frontend_App**: The React single-page application that provides the park ranger chat interface for interacting with Bush Ranger AI
- **CloudFront_Distribution**: Amazon CloudFront CDN distribution that serves the Frontend_App and enforces HTTPS
- **Origin_Access_Control**: CloudFront Origin Access Control (OAC) that restricts S3 bucket access to CloudFront only, preventing direct public access
- **Cognito_User_Pool**: Amazon Cognito User Pool that manages park ranger user accounts, authentication, and JWT token issuance
- **HTTP_API_Gateway**: Amazon API Gateway (HTTP API) that serves as the entry point for agent invocation requests from the Frontend_App
- **Cognito_Authorizer**: A JWT authorizer on the HTTP_API_Gateway that validates Cognito-issued tokens before routing requests to the agent
- **Ruff**: Fast Python linter and formatter (written in Rust) that replaces flake8, isort, and black
- **mypy**: Static type checker for Python that enforces type annotations and catches type errors at build time
- **ESLint**: Pluggable JavaScript/TypeScript linter for identifying and fixing code quality issues
- **AgentSkills_Plugin**: Strands SDK plugin that provides modular, on-demand instruction packages (skills) that the agent discovers and activates at runtime
- **Steering_Plugin**: Strands SDK plugin (LLMSteeringHandler) that provides context-aware guidance intercepting agent behavior before tool calls and after model responses
- **SKILL_md**: A markdown file with YAML frontmatter that defines a skill's name, description, allowed tools, and detailed instructions following the Agent Skills specification

## Requirements

### Requirement 1: Wildlife Sightings MCP Server (DynamoDB)

**User Story:** As a park ranger, I want to store and query wildlife sightings by species, location, date, and conservation status, so that I can track animal populations and identify endangered species activity.

#### Acceptance Criteria

1. THE Wildlife_Sightings_Server SHALL expose an MCP_Tool to create a Sighting_Record containing species name, location (latitude and longitude), date, conservation status, and observer notes
2. WHEN a query tool is invoked with a species filter, THE Wildlife_Sightings_Server SHALL return all Sighting_Records matching that species within the specified time range
3. WHEN a query tool is invoked with a location filter, THE Wildlife_Sightings_Server SHALL return all Sighting_Records within the specified geographic radius
4. THE Wildlife_Sightings_Server SHALL expose an MCP_Tool to query sightings filtered by conservation status (e.g., endangered, vulnerable, least concern)
5. THE Infrastructure_Stack SHALL provision a DynamoDB table with partition key and sort key suitable for querying by species and date
6. IF a Sighting_Record is missing required fields (species, location, date), THEN THE Wildlife_Sightings_Server SHALL return a structured error describing the missing fields
7. WHEN a Sighting_Record is created, THE Wildlife_Sightings_Server SHALL return the created record with a generated unique identifier

### Requirement 2: Conservation Documents MCP Server (S3)

**User Story:** As a park ranger, I want to search and retrieve conservation documents including species fact sheets, national park management plans, and emergency procedures, so that I can access reference material in the field.

#### Acceptance Criteria

1. THE Conservation_Docs_Server SHALL expose an MCP_Tool to list available documents filtered by category (species fact sheets, management plans, emergency procedures)
2. WHEN a document retrieval tool is invoked with a document identifier, THE Conservation_Docs_Server SHALL return the document content from S3
3. THE Conservation_Docs_Server SHALL support retrieval of markdown and PDF document formats
4. THE Infrastructure_Stack SHALL provision an S3 bucket for storing conservation documents with appropriate read permissions for the Conservation_Docs_Server
5. WHEN a search tool is invoked with a keyword, THE Conservation_Docs_Server SHALL return a list of matching documents with titles and summaries
6. IF a requested document does not exist in S3, THEN THE Conservation_Docs_Server SHALL return a structured error indicating the document was not found

### Requirement 3: Weather and Climate MCP Server (Open-Meteo API)

**User Story:** As a park ranger, I want to check current weather conditions, forecasts, and fire danger indicators for Australian locations, so that I can plan field activities and assess environmental risks.

#### Acceptance Criteria

1. THE Weather_Server SHALL expose an MCP_Tool to retrieve current weather conditions for a specified Australian location (latitude and longitude)
2. THE Weather_Server SHALL expose an MCP_Tool to retrieve a multi-day weather forecast for a specified Australian location
3. WHEN a weather tool is invoked, THE Weather_Server SHALL query the Open_Meteo_API and return temperature, humidity, wind speed, and precipitation data
4. THE Weather_Server SHALL expose an MCP_Tool to assess fire danger based on temperature, humidity, and wind conditions for a specified location
5. THE Weather_Server SHALL use the Open_Meteo_API which requires no API key and incurs no cost
6. IF the Open_Meteo_API is unreachable, THEN THE Weather_Server SHALL return a structured error indicating the external service is unavailable

### Requirement 4: Third-Party Fetch MCP Server

**User Story:** As a park ranger, I want the agent to fetch live content from government wildlife and conservation websites, so that I can access up-to-date information beyond pre-loaded documents.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL configure the Fetch_Server (@modelcontextprotocol/server-fetch) as a third-party MCP server available to the Strands_Agent
2. THE Fetch_Server SHALL require no API key and incur no cost
3. WHEN the Strands_Agent determines that live web content is needed, THE Strands_Agent SHALL invoke the Fetch_Server to retrieve content from the target URL
4. THE Strands_Agent system prompt SHALL include guidance on which government wildlife URLs are appropriate to fetch

### Requirement 5: Strands Agent Definition (Bush Ranger AI)

**User Story:** As a park ranger, I want an AI assistant that can reason over my requests and coordinate across wildlife sightings, conservation documents, weather data, and live web content, so that I get comprehensive answers to field questions.

#### Acceptance Criteria

1. THE Strands_Agent SHALL be implemented in Python using the Strands Agents SDK
2. THE Strands_Agent SHALL connect to the Wildlife_Sightings_Server, Conservation_Docs_Server, Weather_Server, and Fetch_Server through the AgentCore runtime
3. WHEN a user sends a request, THE Strands_Agent SHALL determine which MCP_Tools to invoke based on the request content
4. WHEN the Strands_Agent invokes an MCP_Tool, THE Strands_Agent SHALL pass validated parameters matching the tool's input schema
5. WHEN the Strands_Agent completes a request, THE Strands_Agent SHALL return a natural language response summarizing the result
6. THE Strands_Agent SHALL use Claude Sonnet (via Amazon Bedrock) as the primary reasoning foundation model
7. THE Strands_Agent SHALL support Claude Haiku (via Amazon Bedrock) for lighter classification and summarization tasks to minimize cost

### Requirement 6: Agent Configuration and System Prompt

**User Story:** As a developer, I want the Bush Ranger AI agent to have a configurable system prompt tailored to Australian wildlife and conservation, so that the agent responds with domain-appropriate context.

#### Acceptance Criteria

1. THE Strands_Agent SHALL load its system prompt from an external configuration file
2. THE Strands_Agent system prompt SHALL instruct the agent to act as an Australian park ranger assistant specializing in wildlife tracking, conservation, and environmental monitoring
3. THE Strands_Agent SHALL support configuring the underlying foundation model (model ID, temperature) via configuration
4. WHEN the system prompt configuration is updated, THE Strands_Agent SHALL use the updated prompt on the next invocation without redeployment

### Requirement 7: Infrastructure as Code (AWS CDK Python)

**User Story:** As a developer, I want the entire infrastructure defined as AWS CDK (Python) code, so that deployments are repeatable, version-controlled, and follow AWS best practices.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL be defined using AWS CDK with Python
2. THE Infrastructure_Stack SHALL be deployable with a single command from the project root
3. THE Infrastructure_Stack SHALL deploy all resources to the us-east-1 region
4. THE Infrastructure_Stack SHALL use parameterized configuration for environment-specific values such as AWS account ID and region
5. IF a deployment fails, THEN THE Infrastructure_Stack SHALL roll back to the previous stable state
6. THE Infrastructure_Stack SHALL define IAM roles with least-privilege permissions for the Strands_Agent and each MCP_Server
7. THE Infrastructure_Stack SHALL provision the DynamoDB table, S3 bucket, and all AgentCore resources in a single stack

### Requirement 8: AgentCore Deployment

**User Story:** As a developer, I want all agent and MCP server components deployed to AWS AgentCore, so that the infrastructure is fully managed and I don't need to handle scaling or networking manually.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL deploy the Strands_Agent to AgentCore as a managed agent runtime
2. THE Infrastructure_Stack SHALL deploy each custom MCP_Server (Wildlife_Sightings_Server, Conservation_Docs_Server, Weather_Server) to AgentCore as managed MCP server runtimes
3. THE Infrastructure_Stack SHALL configure the Fetch_Server as a third-party MCP server within AgentCore
4. WHEN the Infrastructure_Stack is deployed, THE AgentCore runtime SHALL configure network connectivity between the Strands_Agent and all four MCP servers
5. WHEN a deployment completes, THE Infrastructure_Stack SHALL output the AgentCore agent endpoint URL
6. THE Infrastructure_Stack SHALL configure Amazon Bedrock model access for Claude Sonnet and Claude Haiku in us-east-1

### Requirement 9: Observability and Logging

**User Story:** As a developer, I want structured logging and observability for the agent and MCP servers, so that I can monitor system health, track costs, and debug issues.

#### Acceptance Criteria

1. THE Strands_Agent SHALL emit structured logs for each user request, including request ID, timestamp, tools invoked, and response status
2. THE MCP_Server SHALL emit structured logs for each tool invocation, including tool name, request ID, duration, and success or failure status
3. WHEN an error occurs in the Strands_Agent or an MCP_Server, THE affected component SHALL log the error with full context including stack trace and request ID
4. THE Infrastructure_Stack SHALL configure CloudWatch log groups for the Strands_Agent and each MCP_Server

### Requirement 10: Cost Optimization

**User Story:** As a developer, I want the infrastructure to minimize costs by using free-tier services where possible and right-sizing resources, so that the project stays within a minimal budget.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL provision the DynamoDB table in on-demand capacity mode to avoid paying for unused provisioned capacity
2. THE Weather_Server SHALL use only the Open_Meteo_API which is free and requires no API key
3. THE Fetch_Server SHALL be the @modelcontextprotocol/server-fetch package which is free and requires no API key
4. THE Infrastructure_Stack SHALL use Claude Haiku for lighter tasks where Claude Sonnet is not required, to reduce per-invocation model costs

### Requirement 11: React Frontend with CloudScape UI

**User Story:** As a park ranger, I want a web-based chat interface built with AWS CloudScape Design System components, so that I can interact with the Bush Ranger AI agent through a familiar, accessible, and professional UI.

#### Acceptance Criteria

1. THE Frontend_App SHALL be a React single-page application using CloudScape_UI components (@cloudscape-design/components)
2. THE Frontend_App SHALL provide a chat interface where park rangers can type messages and receive agent responses
3. WHEN a user sends a message, THE Frontend_App SHALL display the message in the chat history and show a loading indicator while awaiting the agent response
4. WHEN the agent responds, THE Frontend_App SHALL render the response in the chat history with clear visual distinction between user and agent messages
5. THE Frontend_App SHALL display contextual suggestions or quick-action buttons to help rangers discover available agent capabilities
6. THE Frontend_App SHALL be responsive and usable on both desktop and tablet screen sizes
7. IF the agent request fails, THEN THE Frontend_App SHALL display a user-friendly error message without exposing internal details

### Requirement 12: S3 and CloudFront Hosting (Private)

**User Story:** As a developer, I want the frontend hosted on S3 via CloudFront with the S3 bucket kept private, so that the application is served securely over HTTPS without exposing the bucket to public access.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL provision an S3 bucket for hosting the Frontend_App static assets (HTML, CSS, JS)
2. THE S3 bucket SHALL NOT have public access enabled; all public access SHALL be blocked
3. THE Infrastructure_Stack SHALL provision a CloudFront_Distribution that serves the Frontend_App from the S3 bucket
4. THE CloudFront_Distribution SHALL use Origin_Access_Control (OAC) to grant CloudFront-only read access to the S3 bucket
5. THE CloudFront_Distribution SHALL enforce HTTPS for all requests
6. THE CloudFront_Distribution SHALL be configured with a default root object of `index.html`
7. THE CloudFront_Distribution SHALL return `index.html` for 403/404 errors to support client-side routing in the React SPA

### Requirement 13: Amazon Cognito Authentication

**User Story:** As a park ranger, I want to sign in with a username and password before accessing the Bush Ranger AI interface, so that only authorized rangers can use the system.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL provision a Cognito_User_Pool for managing park ranger user accounts
2. THE Infrastructure_Stack SHALL provision a Cognito User Pool Client configured for the Frontend_App
3. WHEN a user is not authenticated, THE Frontend_App SHALL redirect them to a sign-in page
4. WHEN a user signs in successfully, THE Cognito_User_Pool SHALL issue JWT tokens (ID token, access token, refresh token)
5. THE Frontend_App SHALL store authentication tokens securely and include the access token in API requests to the HTTP_API_Gateway
6. WHEN a user's token expires, THE Frontend_App SHALL attempt to refresh the token using the refresh token before requiring re-authentication
7. THE Cognito_User_Pool SHALL enforce a minimum password length of 8 characters with complexity requirements

### Requirement 14: API Gateway for Agent Invocation

**User Story:** As a developer, I want an API Gateway (HTTP API) as the entry point for agent requests from the frontend, so that requests are authenticated, routed to the Strands Agent on AgentCore, and the frontend is decoupled from the agent runtime.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL provision an HTTP_API_Gateway as the entry point for agent invocation requests
2. THE HTTP_API_Gateway SHALL be configured with a Cognito_Authorizer that validates JWT tokens issued by the Cognito_User_Pool
3. WHEN a request arrives without a valid JWT token, THE HTTP_API_Gateway SHALL return a 401 Unauthorized response
4. THE HTTP_API_Gateway SHALL route authenticated requests to the Strands_Agent on AgentCore
5. THE HTTP_API_Gateway SHALL support CORS to allow requests from the CloudFront_Distribution domain
6. THE Infrastructure_Stack SHALL output the HTTP_API_Gateway endpoint URL
7. IF the AgentCore runtime is unavailable, THEN THE HTTP_API_Gateway SHALL return a 502 or 503 error to the caller

### Requirement 15: Code Quality and Linting

**User Story:** As a developer, I want automated code quality tooling enforced across all Python and TypeScript source files, so that the codebase maintains consistent style, type safety, and licensing compliance from the start.

#### Acceptance Criteria

1. THE project SHALL use Ruff for Python linting and formatting, configured to enforce docstring presence (D100, D101, D102, D103), import ordering, and naming conventions with auto-fix enabled
2. THE project SHALL use mypy in strict mode for Python type checking, ensuring shared model classes (e.g., DynamoDB table definitions) are properly typed and used consistently across all components
3. THE project SHALL use ESLint with @typescript-eslint for TypeScript linting, enforcing naming conventions, file header (copyright/license) presence, and component patterns
4. THE project SHALL use Prettier for TypeScript formatting
5. WHEN any Python or TypeScript source file is created, THE file SHALL include a copyright header comment at the top in the format: `# Copyright 2025 Bush Ranger AI Project. All rights reserved.` (Python) or `// Copyright 2025 Bush Ranger AI Project. All rights reserved.` (TypeScript)
6. DynamoDB table definitions, S3 bucket references, and other shared AWS resource interfaces SHALL be defined as classes in a shared `models/` package, and all components that interact with these resources SHALL import and use the shared model classes
7. Linting (Ruff + mypy for Python, ESLint for TypeScript) SHALL run as part of the build/CI pipeline, and the build SHALL fail if linting errors are present
8. THE project SHALL include a pre-commit hook configuration (`.pre-commit-config.yaml`) for running linters locally before commits

### Requirement 16: Strands Agent Skills (AgentSkills Plugin)

**User Story:** As a park ranger, I want the Bush Ranger AI agent to dynamically load specialized instruction packages for different tasks (wildlife tracking, fire danger assessment, conservation research, web research), so that the agent provides expert-level guidance on-demand without a bloated system prompt.

#### Acceptance Criteria

1. THE Strands_Agent SHALL use the AgentSkills_Plugin from the Strands SDK to register all four custom skills (wildlife-tracking, fire-danger-assessment, conservation-research, web-research)
2. WHEN a skill is defined, THE skill SHALL be a directory containing a SKILL_md file with YAML frontmatter (name, description, allowed-tools) and markdown instructions
3. THE AgentSkills_Plugin SHALL inject skill metadata (name and description) into the system prompt for discovery
4. WHEN the agent determines a skill is relevant, THE agent SHALL activate the skill via the skills tool to load full instructions on-demand
5. THE system prompt SHALL remain lean, containing only the agent's core persona and the auto-injected skill metadata XML
6. WHEN the wildlife-tracking skill is activated, THE skill SHALL provide instructions on recording sightings, IUCN conservation status categories (Critically Endangered, Endangered, Vulnerable, Near Threatened, Least Concern), required sighting record fields, and wildlife observation best practices
7. WHEN the fire-danger-assessment skill is activated, THE skill SHALL provide instructions on interpreting McArthur Forest Fire Danger Index (FFDI) ratings, danger level meanings for field operations (low, moderate, high, very_high, extreme), recommended ranger actions at each level, and escalation criteria
8. WHEN the conservation-research skill is activated, THE skill SHALL provide instructions on searching conservation documents effectively, document categories (species fact sheets, management plans, emergency procedures), cross-referencing species data with management plans, and summarizing findings for field use
9. WHEN the web-research skill is activated, THE skill SHALL provide instructions on authoritative Australian government URLs (bom.gov.au, dcceew.gov.au, parks.vic.gov.au, nsw.gov.au/topics/parks-reserves-and-protected-areas), validating web source information, and when to use the Fetch Server vs conservation docs
10. Each skill directory SHALL follow the Agent Skills specification structure (SKILL_md, optional scripts/, references/, assets/ subdirectories)

### Requirement 17: Strands Steering Plugin (LLMSteeringHandler)

**User Story:** As a park ranger, I want the Bush Ranger AI agent to automatically validate data quality before recording wildlife sightings and include safety warnings when fire danger is high, so that I can trust the data I record and stay safe in the field.

#### Acceptance Criteria

1. THE Strands_Agent SHALL use the LLMSteeringHandler plugin from the Strands SDK for data quality and safety steering
2. THE data quality steering handler SHALL intercept create_sighting tool calls and validate that coordinates are within Australian bounds (latitude: -44 to -10, longitude: 113 to 154)
3. THE data quality steering handler SHALL validate that conservation_status is from the approved IUCN list (critically_endangered, endangered, vulnerable, near_threatened, least_concern)
4. THE data quality steering handler SHALL validate that the sighting date is not in the future
5. IF data quality validation fails, THEN THE steering handler SHALL return a Guide action cancelling the tool call and providing feedback to the agent about what needs correction
6. THE safety steering handler SHALL evaluate agent responses involving fire danger assessments
7. WHEN fire danger is assessed as high, very_high, or extreme, THE safety steering handler SHALL guide the agent to include emergency contact information (Emergency 000) and recommended safety actions in its response
8. THE steering handlers SHALL use natural language system prompts for evaluation (LLMSteeringHandler approach)

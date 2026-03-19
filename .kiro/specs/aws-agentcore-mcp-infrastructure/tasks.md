# Tasks

## Task 1: Project Scaffolding and CDK Bootstrap

- [x] 1.1 Create `infra/app.py`, `infra/cdk.json`, `requirements.txt` with CDK and runtime dependencies
- [x] 1.2 Create `config/agent_config.yaml` with system prompt and model configuration (Claude Sonnet primary, Claude Haiku secondary, temperature 0.3)
- [x] 1.3 Create sample conservation documents in `config/sample_documents/` (species/, management_plans/, emergency/ with placeholder markdown files)

## Task 2: Shared Models Package

- [x] 2.1 Create `models/__init__.py` with copyright header and package docstring
- [x] 2.2 Create `models/sightings.py` with `SightingRecord` dataclass, DynamoDB table constants (`TABLE_NAME`, `PARTITION_KEY`, `SORT_KEY`, `GSI_NAME`)
- [x] 2.3 Create `models/documents.py` with `DocumentMetadata` dataclass, S3 bucket constants (`DOCS_BUCKET_PREFIX`, `CATEGORIES`)
- [x] 2.4 Create `models/agent.py` with agent invocation request/response dataclasses

## Task 3: Wildlife Sightings MCP Server

- [x] 3.1 Create `services/mcp_servers/wildlife_sightings/__init__.py` and `services/mcp_servers/wildlife_sightings/server.py` with MCP server skeleton
- [x] 3.2 Implement `create_sighting` tool: validate required fields (species, location, date), generate unique ID, write to DynamoDB using shared `SightingRecord` model
- [x] 3.3 Implement `query_by_species` tool: query DynamoDB by partition key with date range filter
- [x] 3.4 Implement `query_by_location` tool: scan and filter by haversine distance calculation
- [x] 3.5 Implement `query_by_status` tool: query GSI `conservation_status-date-index` with optional date range
- [x] 3.6 Implement input validation returning structured errors for missing required fields (Req 1.6)

## Task 4: Conservation Documents MCP Server

- [x] 4.1 Create `services/mcp_servers/conservation_docs/__init__.py` and `services/mcp_servers/conservation_docs/server.py` with MCP server skeleton
- [x] 4.2 Implement `list_documents` tool: list S3 objects filtered by category prefix using shared `DocumentMetadata` model
- [x] 4.3 Implement `get_document` tool: retrieve document content from S3 by key (markdown as text, PDF as base64)
- [x] 4.4 Implement `search_documents` tool: list all objects, download text content, substring match on keyword
- [x] 4.5 Implement error handling for missing documents (return structured "not found" error)

## Task 5: Weather & Climate MCP Server

- [x] 5.1 Create `services/mcp_servers/weather/__init__.py` and `services/mcp_servers/weather/server.py` with MCP server skeleton
- [x] 5.2 Implement `get_current_weather` tool: call Open-Meteo API with lat/lng, return temperature, humidity, wind speed, precipitation
- [x] 5.3 Implement `get_forecast` tool: call Open-Meteo API for multi-day forecast (1-16 days)
- [x] 5.4 Implement `assess_fire_danger` tool: calculate fire danger rating using simplified McArthur FFDI from temperature, humidity, wind speed
- [x] 5.5 Implement error handling for Open-Meteo API unavailability (structured "service unavailable" error)

## Task 6: Strands Agent

- [x] 6.1 Create `services/agent/__init__.py`, `services/agent/handler.py`, and `services/agent/prompts.py`
- [x] 6.2 Implement `services/agent/prompts.py`: load system prompt from `config/agent_config.yaml`
- [x] 6.3 Implement `services/agent/handler.py`: Strands Agent entry point connecting to all four MCP servers via AgentCore, using Claude Sonnet as primary and Claude Haiku for light tasks
- [x] 6.4 Update agent initialization to include AgentSkills plugin and both LLMSteeringHandler plugins (data_quality_handler, safety_handler)

## Task 7: CDK Infrastructure Stack

- [x] 7.1 Create `infra/stacks/bush_ranger_stack.py` with single CDK stack class
- [x] 7.2 Define DynamoDB table: partition key `species`, sort key `date_location`, GSI `conservation_status-date-index`, on-demand billing (PAY_PER_REQUEST)
- [x] 7.3 Define S3 docs bucket with BucketDeployment for sample documents from `config/sample_documents/`
- [x] 7.4 Define S3 frontend bucket: `BLOCK_ALL` public access, `DESTROY` removal policy, `autoDeleteObjects`
- [x] 7.5 Define CloudFront distribution: OAC to frontend bucket, HTTPS redirect, default root `index.html`, 403/404 → `index.html`, `PRICE_CLASS_100`
- [x] 7.6 Define Cognito User Pool: email sign-in, no self-signup, password policy (min 8, uppercase, lowercase, numbers, symbols), email recovery
- [x] 7.7 Define Cognito User Pool Client: `USER_PASSWORD_AUTH` + `USER_SRP_AUTH`, 1hr access token, 30-day refresh, no client secret
- [x] 7.8 Define HTTP API Gateway: `POST /invoke` route, JWT authorizer (Cognito issuer + audience), CORS for CloudFront domain
- [x] 7.9 Define AgentCore agent runtime for Strands Agent and MCP server runtimes for 3 custom servers + Fetch Server third-party config
- [x] 7.10 Define IAM roles with least-privilege permissions per component (DynamoDB, S3, Bedrock, CloudWatch scoped to specific ARNs)
- [x] 7.11 Define CloudWatch log groups for agent and each MCP server
- [x] 7.12 Add CDK stack outputs: agent endpoint, DynamoDB table name, S3 bucket names, CloudFront URL, Cognito IDs, API Gateway URL

## Task 8: React Frontend — Project Setup

- [x] 8.1 Create `frontend/package.json` with React 18, CloudScape, Vite, TypeScript, `amazon-cognito-identity-js` dependencies
- [x] 8.2 Create `frontend/tsconfig.json` and `frontend/vite.config.ts`
- [x] 8.3 Create `frontend/public/index.html` entry point
- [x] 8.4 Create `frontend/src/types.ts` with `ChatMessage`, `InvokeRequest`, `InvokeResponse` interfaces (with copyright header)

## Task 9: React Frontend — Auth Components

- [x] 9.1 Create `frontend/src/auth/AuthProvider.tsx`: Cognito session management context, token storage, auto-refresh on 401, redirect to sign-in on expired refresh token
- [x] 9.2 Create `frontend/src/auth/SignIn.tsx`: CloudScape Form with email/password fields, Cognito `USER_PASSWORD_AUTH` flow, error display

## Task 10: React Frontend — Chat Components

- [x] 10.1 Create `frontend/src/App.tsx`: root component with `AppLayout`, `TopNavigation`, auth routing
- [x] 10.2 Create `frontend/src/main.tsx`: React entry point rendering `App`
- [x] 10.3 Create `frontend/src/chat/ChatPage.tsx`: main chat layout with `ContentLayout`, `Container`, `SpaceBetween`
- [x] 10.4 Create `frontend/src/chat/MessageList.tsx`: render chat history with user/agent visual distinction using `Box`, `StatusIndicator`
- [x] 10.5 Create `frontend/src/chat/MessageInput.tsx`: text input with send button, loading indicator while awaiting response
- [x] 10.6 Create `frontend/src/chat/Suggestions.tsx`: quick-action chips using `ButtonGroup` ("Check weather", "Log sighting", etc.)
- [x] 10.7 Create `frontend/src/api/agent.ts`: API client — POST to `/invoke` with Bearer token, error handling (sanitize errors, no internal details exposed), 30s timeout

## Task 11: Code Quality Tooling — Python (Ruff + mypy)

- [x] 11.1 Create `pyproject.toml` with Ruff configuration: target Python 3.11, line-length 120, auto-fix enabled, rule selection (E, W, F, I, N, D, UP, B, S), D100-D103 docstring enforcement, Google convention, isort with known-first-party packages (`models`, `services`, `infra`)
- [x] 11.2 Add mypy configuration to `pyproject.toml`: strict mode, `disallow_untyped_defs`, `disallow_incomplete_defs`, `no_implicit_optional`, overrides for `aws_cdk.*` and `strands.*` to ignore missing imports
- [x] 11.3 Add copyright header (`# Copyright 2025 Bush Ranger AI Project. All rights reserved.`) to all existing Python source files (models/, services/, infra/, tests/)
- [x] 11.4 Run `ruff check --fix` and `ruff format` on all Python files to ensure baseline compliance
- [x] 11.5 Run `mypy --strict` on models/, services/, infra/ and fix any type errors

## Task 12: Code Quality Tooling — TypeScript (ESLint + Prettier)

- [x] 12.1 Create `frontend/.eslintrc.js` with @typescript-eslint parser, plugins (header, react, react-hooks), naming conventions (PascalCase for interfaces/types/enums), copyright header enforcement via `header/header` rule
- [x] 12.2 Create `frontend/.prettierrc` with semi, trailing commas, single quotes, printWidth 100, tabWidth 2
- [x] 12.3 Add ESLint and Prettier dev dependencies to `frontend/package.json`: `eslint`, `@typescript-eslint/parser`, `@typescript-eslint/eslint-plugin`, `eslint-plugin-header`, `eslint-plugin-react`, `eslint-plugin-react-hooks`, `prettier`
- [x] 12.4 Add copyright header (`// Copyright 2025 Bush Ranger AI Project. All rights reserved.`) to all existing TypeScript source files
- [x] 12.5 Run ESLint and Prettier on all frontend source files to ensure baseline compliance

## Task 13: Pre-Commit Hooks and Build Integration

- [x] 13.1 Create `.pre-commit-config.yaml` with hooks: ruff (lint + format), mypy (strict, with boto3-stubs and types-requests), local ESLint hook for frontend, local Prettier hook for frontend
- [x] 13.2 Create `Makefile` with targets: `lint` (ruff check + format), `typecheck` (mypy strict on models/, services/, infra/), `lint-frontend` (eslint + prettier check), `format` (ruff format + prettier write), `check-all` (lint + typecheck + lint-frontend)
- [x] 13.3 Verify `make check-all` runs successfully with zero errors across all Python and TypeScript files

## Task 14: Backend Unit Tests (pytest)

- [x] 14.1 Create `tests/__init__.py` and `tests/test_stack.py`: CDK assertion tests verifying synthesized template contains DynamoDB table, S3 buckets, CloudFront, Cognito, API Gateway, AgentCore resources, IAM roles, CloudWatch log groups (Properties 10, 11, 12, 16)
- [x] 14.2 Create `tests/test_wildlife_sightings.py`: unit tests for each tool with mocked DynamoDB (create, query by species/location/status, validation errors) — tests `services/mcp_servers/wildlife_sightings/server.py`
- [x] 14.3 Create `tests/test_conservation_docs.py`: unit tests for each tool with mocked S3 (list, get, search, not-found error) — tests `services/mcp_servers/conservation_docs/server.py`
- [x] 14.4 Create `tests/test_weather.py`: unit tests for each tool with mocked HTTP responses (current weather, forecast, fire danger, API unavailable error) — tests `services/mcp_servers/weather/server.py`

## Task 15: Backend Property-Based Tests (hypothesis)

- [x] 15.1 Create `tests/test_properties_sightings.py`: Property 1 (sighting round-trip), Property 2 (species filter), Property 3 (location radius), Property 4 (status filter), Property 5 (missing fields error), Property 6 (unique IDs) — each tagged with `Feature: aws-agentcore-mcp-infrastructure, Property N: title`, min 100 iterations
- [x] 15.2 Create `tests/test_properties_docs.py`: Property 7 (document round-trip), Property 8 (search matches content) — tagged, min 100 iterations
- [x] 15.3 Create `tests/test_properties_weather.py`: Property 9 (fire danger monotonicity) — tagged, min 100 iterations
- [x] 15.4 Create `tests/test_properties_stack.py`: Property 12 (IAM least-privilege) — tagged, min 100 iterations
- [x] 15.5 Create `tests/test_properties_copyright.py`: Property 18 (all source files contain copyright header) — scan all .py and .ts/.tsx files, verify each starts with the correct copyright comment, tagged, min 100 iterations

## Task 16: Frontend Unit Tests (Vitest)

- [x] 16.1 Create `tests/frontend/chat.test.tsx`: test message rendering (user vs agent distinction), input handling, loading states, error display (sanitized messages)
- [x] 16.2 Create `tests/frontend/auth.test.tsx`: test sign-in form, token storage, redirect on unauthenticated, token refresh flow

## Task 17: Frontend Property-Based Tests (fast-check)

- [x] 17.1 Create `tests/frontend/properties.test.tsx`: Property 13 (chat message role distinction), Property 14 (error messages don't expose internals), Property 15 (API requests include auth token), Property 17 (unauthenticated requests rejected) — each tagged with `Feature: aws-agentcore-mcp-infrastructure, Property N: title`, min 100 iterations

## Task 18: Strands Agent Skills

- [x] 18.1 Create `skills/wildlife-tracking/SKILL.md` with YAML frontmatter (name, description, allowed-tools: create_sighting, query_by_species, query_by_location, query_by_status) and markdown instructions covering sighting recording procedures, IUCN conservation status categories, required sighting record fields, and wildlife observation best practices
- [x] 18.2 Create `skills/fire-danger-assessment/SKILL.md` with YAML frontmatter (name, description, allowed-tools: assess_fire_danger, get_current_weather, get_forecast) and markdown instructions covering McArthur FFDI interpretation, danger level meanings (low/moderate/high/very_high/extreme), recommended ranger actions at each level, and escalation criteria
- [x] 18.3 Create `skills/conservation-research/SKILL.md` with YAML frontmatter (name, description, allowed-tools: list_documents, get_document, search_documents) and markdown instructions covering effective document search strategies, document categories, cross-referencing species data with management plans, and summarizing findings for field use
- [x] 18.4 Create `skills/web-research/SKILL.md` with YAML frontmatter (name, description, allowed-tools: fetch) and markdown instructions covering authoritative Australian government URLs (bom.gov.au, dcceew.gov.au, parks.vic.gov.au, nsw.gov.au), web source validation, and when to use Fetch Server vs conservation docs

## Task 19: Strands Steering Handlers

- [x] 19.1 Create `services/agent/steering/__init__.py` with copyright header
- [x] 19.2 Create `services/agent/steering/data_quality.py`: implement data quality steering handler using LLMSteeringHandler with system prompt that validates Australian coordinate bounds (lat: -44 to -10, lng: 113 to 154), approved IUCN conservation status list, and date-not-in-future check before create_sighting tool calls
- [x] 19.3 Create `services/agent/steering/safety.py`: implement safety steering handler using LLMSteeringHandler with system prompt that detects high/very_high/extreme fire danger levels and steers the agent to include Emergency 000 contact info and danger-level-appropriate safety actions

## Task 20: Skills and Steering Unit Tests (pytest)

- [x] 20.1 Create `tests/test_skills.py`: unit tests verifying each SKILL.md parses correctly (valid YAML frontmatter with name, description, allowed-tools), skill content contains expected domain keywords (e.g., wildlife-tracking contains "IUCN", fire-danger-assessment contains "FFDI"), and all four skill directories exist
- [x] 20.2 Create `tests/test_steering_data_quality.py`: unit tests for data quality validation — test coordinates within/outside Australian bounds, valid/invalid conservation statuses, past/today/future dates, and verify Guide action returned on validation failure — tests `services/agent/steering/data_quality.py`
- [x] 20.3 Create `tests/test_steering_safety.py`: unit tests for safety steering — test each fire danger level (low, moderate, high, very_high, extreme), verify emergency info (000) included for high+ levels, verify appropriate safety actions per level — tests `services/agent/steering/safety.py`

## Task 21: Skills and Steering Property-Based Tests (hypothesis)

- [x] 21.1 Create `tests/test_properties_skills.py`: Property 19 (skill activation returns full instructions) — for any valid skill, activating it returns complete SKILL.md content with name, description, and allowed-tools; tagged with `Feature: aws-agentcore-mcp-infrastructure, Property 19: Skill activation returns full instructions`, min 100 iterations
- [x] 21.2 Create `tests/test_properties_steering.py`: Property 20 (data quality steering validates sighting inputs) — for any generated lat/lng/status/date combination, validator accepts iff all fields are within valid ranges; Property 21 (safety steering includes emergency info for elevated fire danger) — for any fire danger level in {high, very_high, extreme}, steered response contains "000" and safety actions; each tagged with `Feature: aws-agentcore-mcp-infrastructure, Property N: title`, min 100 iterations

# Implementation Plan: AgentCore Evaluations

## Overview

Integrate Amazon Bedrock AgentCore Evaluations into the Bush Ranger AI project. The implementation adds a custom evaluator and online evaluation config (CDK), a poller Lambda to bridge CloudWatch results to DynamoDB, an evaluations API Lambda, and a dashboard UI section — all following existing codebase patterns.

## Tasks

- [x] 1. Create shared data model and TypeScript types
  - [x] 1.1 Create `models/evaluations.py` with table constants, key names, GSI name, and `EvaluationResult` dataclass
    - Follow the pattern in `models/sightings.py`
    - Define `TABLE_NAME = "BushRangerEvaluations"`, `PARTITION_KEY = "invocation_id"`, `SORT_KEY = "evaluator_ts"`, `GSI_NAME = "evaluator-timestamp-index"`
    - Include the `EvaluationResult` dataclass with all attributes from the design (invocation_id, evaluator_ts, evaluator_name, score, rationale, session_id, prompt_summary, timestamp, ttl)
    - _Requirements: 4.2, 4.3_

  - [x] 1.2 Create `frontend/src/analytics/evaluationTypes.ts` with TypeScript interfaces
    - Define `EvaluationSummary`, `EvaluationResult`, `EvaluationTrendPoint` interfaces per the design
    - Define `EvaluationsResponse<T>` envelope type matching the existing `AnalyticsResponse<T>` pattern in `analyticsTypes.ts`
    - _Requirements: 5.4, 6.1, 6.2, 6.3_

- [x] 2. Implement the poller Lambda (CloudWatch → DynamoDB bridge)
  - [x] 2.1 Create `services/api/evaluation_poller.py` with the poller handler
    - Read last-processed timestamp from the `_POLLER_STATE` control record in DynamoDB
    - Query CloudWatch Logs Insights for new evaluation result events since that timestamp
    - Parse each log event to extract evaluator name, score, rationale, trace ID, session ID, prompt summary
    - Batch-write `EvaluationResult` items to the Evaluations DynamoDB table
    - Update the control record with the latest processed timestamp
    - Handle empty CloudWatch responses, malformed log events (skip + log warning), and DynamoDB write failures gracefully
    - _Requirements: 1.1, 1.3, 2.3, 3.4, 4.1, 4.2_

  - [x] 2.2 Write property test for evaluation result parsing round-trip
    - **Property 1: Evaluation result parsing round-trip**
    - Generate random valid CloudWatch log events with evaluator name, score (0.0–1.0), rationale, trace ID, session ID
    - Assert parsed DynamoDB item contains all required attributes with values matching the original log event
    - **Validates: Requirements 2.3, 3.4, 4.2**

  - [x] 2.3 Write unit tests for the poller Lambda
    - Test poller handles empty CloudWatch response (no new events)
    - Test poller handles malformed log event (missing fields) — skips and logs warning
    - Test poller updates `_POLLER_STATE` control record after successful processing
    - _Requirements: 1.3, 4.1_

- [x] 3. Implement the evaluations API Lambda
  - [x] 3.1 Create `services/api/evaluations_handler.py` with summary and recent endpoints
    - Follow the `analytics_handler.py` pattern: route map, `_cors_headers()`, `_success_response()`, `_error_response()`, `_parse_filters()`
    - Implement `_handle_summary()`: query the `evaluator-timestamp-index` GSI for each evaluator within the time range, compute average score and count per evaluator
    - Implement `_handle_recent()`: scan/query the table for recent results ordered by timestamp descending, apply configurable limit (default 20)
    - Parse and validate `start_date`, `end_date` (ISO-8601), and `limit` query parameters
    - Return responses in the `{ data, count, filters_applied }` JSON envelope format
    - Return 400 for invalid date formats with descriptive error message
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 3.2 Write property test for summary endpoint average computation
    - **Property 2: Summary endpoint computes correct averages**
    - Generate random sets of evaluation results with varying evaluator names and scores (0.0–1.0)
    - Assert the summary returns one entry per distinct evaluator with correct arithmetic mean and count
    - **Validates: Requirements 5.1**

  - [x] 3.3 Write property test for recent results ordering and limit
    - **Property 3: Recent results ordering and limit**
    - Generate random sets of evaluation results with varying timestamps and a random positive limit
    - Assert at most `limit` results returned, ordered by timestamp descending, no newer result omitted while older one included
    - **Validates: Requirements 5.2**

  - [x] 3.4 Write property test for invalid date parameter rejection
    - **Property 4: Invalid date parameters are rejected**
    - Generate random strings that do not match `YYYY-MM-DD` pattern
    - Assert handler returns 400 status code with JSON body containing `error` field
    - **Validates: Requirements 5.5**

  - [x] 3.5 Write unit tests for the evaluations API handler
    - Test summary endpoint with no data returns empty array
    - Test recent endpoint with default limit returns up to 20 results
    - Test API handler routes to correct handler function based on path
    - Test CORS headers are present on all responses
    - _Requirements: 5.1, 5.2, 5.4_

- [x] 4. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Add CDK infrastructure for evaluations
  - [x] 5.1 Create the Evaluations DynamoDB table in `bush_ranger_stack.py`
    - Add `_create_evaluations_table()` method following the `_create_dynamodb_table()` pattern
    - Use on-demand billing, DESTROY removal policy
    - Partition key: `invocation_id` (String), Sort key: `evaluator_ts` (String)
    - Add GSI `evaluator-timestamp-index` with partition key `evaluator_name` and sort key `timestamp`
    - Enable TTL on the `ttl` attribute
    - Import constants from `models/evaluations.py`
    - _Requirements: 4.2, 4.3, 4.4, 7.1_

  - [x] 5.2 Create the Custom Evaluator and Online Evaluation Config CDK resources
    - Add `_create_evaluation_resources()` method
    - Create `AWS::BedrockAgentCore::Evaluator` CfnResource for `BushRangerDomainRules` with LLM-as-a-Judge config and the three-dimension scoring rubric (fire safety, content guardrails, location context)
    - Create an IAM role for the online evaluation config to invoke foundation models
    - Create `AWS::BedrockAgentCore::OnlineEvaluationConfig` CfnResource wiring the agent runtime's CloudWatch log group to all three evaluators (Helpfulness, ToolSelection, custom) with 100% sampling
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 3.3, 7.2_

  - [x] 5.3 Create the Poller Lambda and EventBridge schedule in CDK
    - Add `_create_evaluation_poller()` method
    - Create a Lambda function for `evaluation_poller.handler` with environment variables for the evaluations table name and the CloudWatch results log group name
    - Grant IAM permissions: CloudWatch Logs read on the results log group, DynamoDB read/write on the evaluations table
    - Create an EventBridge rule triggering the poller every 1 minute
    - _Requirements: 7.2, 7.5_

  - [x] 5.4 Create the Evaluations API Lambda and API Gateway routes in CDK
    - Add `_create_evaluations_lambda()` method following the `_create_analytics_lambda()` pattern
    - Create a Lambda function for `evaluations_handler.handler` with read-only DynamoDB permissions on the evaluations table and GSI
    - Create API Gateway routes for `GET /evaluations/summary` and `GET /evaluations/recent` with JWT authorization
    - Grant API Gateway permission to invoke the Lambda
    - _Requirements: 5.3, 7.3, 7.4_

  - [x] 5.5 Wire evaluation infrastructure into the stack constructor
    - Call `_create_evaluations_table()`, `_create_evaluation_resources()`, `_create_evaluation_poller()`, and `_create_evaluations_lambda()` from `__init__`
    - Ensure correct dependency ordering (table before poller/API, agent runtime before online eval config)
    - Add stack outputs for the evaluations table name and evaluator ARN
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 6. Checkpoint — Ensure CDK synth succeeds and all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement the dashboard evaluations UI
  - [x] 7.1 Create `frontend/src/analytics/evaluationsApi.ts` with API fetch functions
    - Follow the `analyticsApi.ts` pattern
    - Implement `fetchEvaluationSummary()` calling `GET /evaluations/summary` with date range params
    - Implement `fetchRecentEvaluations()` calling `GET /evaluations/recent` with limit param
    - Use the same `API_ENDPOINT`, timeout, auth header, and error handling patterns
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 7.2 Create `frontend/src/analytics/EvaluationScoreCards.tsx` component
    - Display average scores for each evaluator (Helpfulness, Tool Selection, Custom) as Cloudscape `Box` score cards
    - Accept evaluation summary data as props
    - Use Cloudscape design components consistent with existing dashboard sections
    - _Requirements: 6.1, 6.5_

  - [x] 7.3 Create `frontend/src/analytics/EvaluationTrendChart.tsx` component
    - Display a Recharts `LineChart` with one line per evaluator showing scores over time
    - Accept trend data as props
    - _Requirements: 6.2, 6.5_

  - [x] 7.4 Create `frontend/src/analytics/RecentEvaluationsTable.tsx` component
    - Display a Cloudscape `Table` showing recent evaluations with prompt summary, evaluator scores, and timestamp
    - Accept recent evaluation data as props
    - _Requirements: 6.3, 6.5_

  - [x] 7.5 Integrate evaluation components into `DashboardPage.tsx`
    - Add a new "Agent Quality Metrics" section to the existing dashboard page
    - Wire up 30-second polling interval via `setInterval` + `useEffect` to fetch summary and recent data
    - Pass fetched data to `EvaluationScoreCards`, `EvaluationTrendChart`, and `RecentEvaluationsTable`
    - Use Cloudscape `Container` and `Header` components consistent with existing sections
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 7.6 Write frontend tests for evaluation components
    - Test component rendering with mock data for score cards, trend chart, and recent table
    - Verify 30-second polling interval is configured
    - Verify Cloudscape components are used
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the four correctness properties from the design document using Hypothesis
- The poller Lambda and evaluations API Lambda follow existing patterns (`analytics_handler.py`, `gallery_handler.py`)
- CDK resources follow existing patterns in `bush_ranger_stack.py`
- Frontend components follow existing patterns in `frontend/src/analytics/`

# Requirements Document

## Introduction

This feature integrates Amazon Bedrock AgentCore Evaluations into the Bush Ranger AI project to provide automated, real-time quality assessment of every agent invocation. The system uses LLM-as-a-Judge techniques with both built-in evaluators (Helpfulness, Tool Selection) and a custom evaluator for Bush Ranger-specific rules (fire safety compliance, content guardrails, location context). Evaluation results are stored immediately in DynamoDB and displayed as live quality metrics on the existing Dashboard page. This is a workshop project — the design prioritises demonstrability and real-time feedback during workshop sessions over production-grade scalability.

## Glossary

- **Evaluation_Service**: The backend component (Lambda function) that calls the AgentCore Evaluations API to score agent invocations and stores results in DynamoDB.
- **Evaluations_Table**: The DynamoDB table that stores evaluation results for every scored agent invocation.
- **Dashboard_Evaluations_Section**: The new section added to the existing DashboardPage that displays real-time agent quality metrics.
- **Agent_Handler**: The Strands agent entry point (`services/agent/handler.py`) running on AgentCore Runtime that processes user requests.
- **Evaluations_API**: The Lambda-backed API Gateway endpoints that serve evaluation metrics to the frontend.
- **Built_In_Evaluator**: A pre-built AgentCore evaluator (Helpfulness or Tool Selection) identified by an evaluator ARN such as `arn:aws:bedrock-agentcore:::evaluator/Builtin.Helpfulness`.
- **Custom_Evaluator**: A project-specific evaluator that scores agent responses against Bush Ranger domain rules (fire safety compliance, content guardrails, location context accuracy).
- **Online_Evaluation**: Real-time scoring of every agent invocation as it happens, as opposed to batch evaluation on a schedule.
- **Evaluation_Result**: A single scored record containing the invocation identifier, evaluator name, numeric score, and optional textual rationale.

## Requirements

### Requirement 1: Online Evaluation Trigger

**User Story:** As a workshop facilitator, I want every agent invocation to be automatically evaluated in real-time, so that quality metrics accumulate live as participants interact with the agent.

#### Acceptance Criteria

1. WHEN the Agent_Handler returns a response to a user invocation, THE Evaluation_Service SHALL submit the invocation input, agent response, and tool usage trace to the AgentCore Evaluations API for scoring.
2. THE Evaluation_Service SHALL invoke all configured evaluators (Helpfulness, Tool Selection, and Custom_Evaluator) for each agent invocation.
3. IF the AgentCore Evaluations API call fails, THEN THE Evaluation_Service SHALL log the error and allow the agent response to be returned to the user without delay.
4. THE Evaluation_Service SHALL execute evaluation scoring asynchronously so that the agent response latency is not increased by the evaluation process.

### Requirement 2: Built-In Evaluators

**User Story:** As a workshop facilitator, I want the agent scored on Helpfulness and Tool Selection using AgentCore's built-in evaluators, so that I can demonstrate standard quality metrics out of the box.

#### Acceptance Criteria

1. THE Evaluation_Service SHALL invoke the Helpfulness built-in evaluator (ARN: `arn:aws:bedrock-agentcore:::evaluator/Builtin.Helpfulness`) for each agent invocation.
2. THE Evaluation_Service SHALL invoke the Tool Selection built-in evaluator for each agent invocation.
3. WHEN a built-in evaluator returns a score, THE Evaluation_Service SHALL store the evaluator name, numeric score, and textual rationale in the Evaluation_Result.

### Requirement 3: Custom Bush Ranger Evaluator

**User Story:** As a workshop facilitator, I want a custom evaluator that checks Bush Ranger-specific rules, so that I can demonstrate domain-specific quality assessment.

#### Acceptance Criteria

1. THE Custom_Evaluator SHALL score agent responses for fire safety compliance by verifying that responses include safety warnings when fire danger levels are high, very high, or extreme.
2. THE Custom_Evaluator SHALL score agent responses for content guardrails by verifying that responses stay within the conservation and wildlife domain.
3. THE Custom_Evaluator SHALL score agent responses for location context accuracy by verifying that location references in responses are consistent with the user's stated or GPS-derived location.
4. WHEN the Custom_Evaluator completes scoring, THE Evaluation_Service SHALL store the custom evaluator name, numeric score, and textual rationale in the Evaluation_Result.

### Requirement 4: Evaluation Results Storage

**User Story:** As a developer, I want evaluation results stored immediately in DynamoDB as they happen, so that the dashboard can display live metrics without waiting for a batch process.

#### Acceptance Criteria

1. WHEN an evaluator returns a score, THE Evaluation_Service SHALL write the Evaluation_Result to the Evaluations_Table within 5 seconds of receiving the score.
2. THE Evaluations_Table SHALL store each Evaluation_Result with the following attributes: invocation identifier, timestamp, evaluator name, numeric score (0.0 to 1.0), textual rationale, session identifier, and user prompt summary.
3. THE Evaluations_Table SHALL use the invocation identifier as the partition key and a composite of evaluator name and timestamp as the sort key, enabling efficient queries by invocation and by evaluator.
4. THE Evaluations_Table SHALL be provisioned with on-demand billing mode consistent with the existing sightings table pattern.

### Requirement 5: Evaluations API Endpoints

**User Story:** As a frontend developer, I want API endpoints that serve aggregated evaluation metrics, so that the dashboard can fetch and display quality data.

#### Acceptance Criteria

1. THE Evaluations_API SHALL expose a `GET /evaluations/summary` endpoint that returns average scores per evaluator over a configurable time range.
2. THE Evaluations_API SHALL expose a `GET /evaluations/recent` endpoint that returns the most recent Evaluation_Results with a configurable limit (default: 20).
3. THE Evaluations_API SHALL require JWT authentication via the existing Cognito authorizer, consistent with the existing analytics endpoints.
4. THE Evaluations_API SHALL return responses in the same JSON envelope format (`{ data, count, filters_applied }`) used by the existing analytics endpoints.
5. IF the Evaluations_API receives an invalid time range parameter, THEN THE Evaluations_API SHALL return a 400 status code with a descriptive error message.

### Requirement 6: Dashboard Quality Metrics Display

**User Story:** As a workshop facilitator, I want to see real-time agent quality metrics on the existing Dashboard page, so that I can demonstrate evaluation results accumulating live during a workshop session.

#### Acceptance Criteria

1. THE Dashboard_Evaluations_Section SHALL display average scores for each evaluator (Helpfulness, Tool Selection, Custom) as numeric gauges or score cards.
2. THE Dashboard_Evaluations_Section SHALL display a time-series chart showing evaluation scores over time, with one line per evaluator.
3. THE Dashboard_Evaluations_Section SHALL display a list of the most recent evaluations showing the prompt summary, evaluator scores, and timestamp.
4. THE Dashboard_Evaluations_Section SHALL auto-refresh evaluation data on a polling interval of 30 seconds to show scores accumulating in near real-time.
5. THE Dashboard_Evaluations_Section SHALL use Cloudscape design components consistent with the existing dashboard sections.

### Requirement 7: Infrastructure Provisioning

**User Story:** As a developer, I want all evaluation infrastructure defined in the CDK stack, so that the feature deploys with a single `cdk deploy` command.

#### Acceptance Criteria

1. THE CDK stack SHALL create the Evaluations_Table as a DynamoDB table with on-demand billing and DESTROY removal policy, following the same pattern as the existing sightings table.
2. THE CDK stack SHALL create a Lambda function for the Evaluation_Service with IAM permissions to call the AgentCore Evaluations API and write to the Evaluations_Table.
3. THE CDK stack SHALL create a Lambda function for the Evaluations_API with read-only IAM permissions on the Evaluations_Table, following the same pattern as the existing analytics Lambda.
4. THE CDK stack SHALL create API Gateway routes for `GET /evaluations/summary` and `GET /evaluations/recent` with JWT authorization, following the same pattern as the existing analytics routes.
5. THE CDK stack SHALL grant the Agent_Handler's IAM role permission to invoke the Evaluation_Service Lambda function asynchronously.

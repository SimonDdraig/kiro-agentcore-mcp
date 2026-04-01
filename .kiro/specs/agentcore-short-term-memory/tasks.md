# Implementation Plan: AgentCore Short-Term Memory

## Overview

Add turn-by-turn conversational memory to the Bush Ranger AI agent by integrating AgentCore Memory across four layers: frontend session tracking, API Lambda passthrough, agent handler memory wiring, and CDK infrastructure provisioning. Tasks are ordered for incremental development — backend infrastructure first, then agent integration, then API passthrough, then frontend, and finally wiring everything together.

## Tasks

- [x] 1. Update agent dependencies and add memory helper
  - [x] 1.1 Add `bedrock-agentcore[strands]` to `services/agent/requirements.txt`
    - Replace the existing `bedrock-agentcore` line with `bedrock-agentcore[strands]` to include the Strands SDK memory integration extras
    - _Requirements: 7.1, 7.2_

  - [x] 1.2 Implement `_build_session_manager` helper in `services/agent/handler.py`
    - Add `MEMORY_ID = os.environ.get("MEMORY_ID", "")` at module level
    - Add imports for `AgentCoreMemoryConfig` from `bedrock_agentcore.memory.integrations.strands.config` and `AgentCoreMemorySessionManager` from `bedrock_agentcore.memory.integrations.strands.session_manager`
    - Implement `_build_session_manager(session_id: str, actor_id: str | None) -> AgentCoreMemorySessionManager | None`
    - If `MEMORY_ID` is empty, log a warning and return `None`
    - If construction fails, log the exception and return `None`
    - On success, create `AgentCoreMemoryConfig(memory_id=MEMORY_ID, session_id=session_id, actor_id=actor_id or "anonymous")` and return `AgentCoreMemorySessionManager(config=config)`
    - _Requirements: 4.1, 4.2, 4.4, 4.5_

  - [x] 1.3 Wire session manager into the `invoke` entrypoint in `services/agent/handler.py`
    - Add `import uuid` at the top of the file
    - Extract `session_id` from `payload.get("session_id", str(uuid.uuid4()))` and `actor_id` from `payload.get("actor_id")`
    - Call `_build_session_manager(session_id, actor_id)` to get the session manager
    - Pass `session_manager=session_manager` to the `Agent()` constructor (None means stateless fallback)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 1.4 Write property test for memory config construction (Property 6)
    - **Property 6: Memory config construction**
    - Generate random (memory_id, session_id, actor_id) triples using Hypothesis
    - Verify `_build_session_manager` creates a config with matching `memory_id`, `session_id`, and `actor_id` attributes
    - `# Feature: agentcore-short-term-memory, Property 6: Memory config construction`
    - **Validates: Requirements 4.1**

- [x] 2. Checkpoint — Agent handler memory integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Update API Lambda to pass session and identity fields
  - [x] 3.1 Modify `services/api/handler.py` to forward `session_id` and `actor_id` in the agent payload
    - Extract `actor_id = body.get("actorId")` from the request body
    - Add `agent_payload["session_id"] = session_id` to the payload dict (session_id already extracted)
    - Add `agent_payload["actor_id"] = actor_id` if actor_id is present
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 3.2 Write property test for Lambda payload passthrough (Property 4)
    - **Property 4: Lambda payload passthrough**
    - Generate random request bodies with/without `sessionId` and `actorId` using Hypothesis
    - Verify the handler constructs the correct agent payload with `session_id` and `actor_id` fields matching the input
    - `# Feature: agentcore-short-term-memory, Property 4: Lambda payload passthrough`
    - **Validates: Requirements 3.1, 3.2**

  - [x] 3.3 Write property test for Lambda fallback session ID (Property 5)
    - **Property 5: Lambda fallback session ID**
    - Generate random request bodies without `sessionId` using Hypothesis
    - Verify the Lambda generates a valid UUID v4 string as `session_id` in the payload
    - `# Feature: agentcore-short-term-memory, Property 5: Lambda fallback session ID`
    - **Validates: Requirements 3.3**

- [x] 4. Checkpoint — API Lambda passthrough
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update frontend to track sessions and extract actor identity
  - [x] 5.1 Add `extractActorId` utility function to `frontend/src/chat/ChatPage.tsx`
    - Implement `extractActorId(token: string | null): string | undefined` that base64-decodes the JWT payload and returns the `sub` claim
    - Return `undefined` if token is null, malformed, or missing `sub`
    - _Requirements: 2.1, 2.2_

  - [x] 5.2 Add `sessionId` state and lifecycle management to `ChatPage`
    - Add `const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID())` to generate a session ID on mount
    - Reset `sessionId` on sign-out by calling `setSessionId(crypto.randomUUID())` after the existing `signOut()` call
    - Generate a new `sessionId` on sign-in
    - _Requirements: 1.1, 1.3, 1.4_

  - [x] 5.3 Update `invokeAgent` in `frontend/src/api/agent.ts` to accept and send `sessionId` and `actorId`
    - Add optional `sessionId?: string` and `actorId?: string` parameters to the function signature
    - Include `sessionId` and `actorId` in the request body when present
    - _Requirements: 1.2, 2.1_

  - [x] 5.4 Wire `sessionId` and `actorId` into `sendMessage` in `ChatPage`
    - Compute `actorId` via `extractActorId(accessToken)` before each call to `invokeAgent`
    - Pass `sessionId` and `actorId` to `invokeAgent()` in both the initial call and the 401-retry call
    - _Requirements: 1.2, 2.1_

  - [x] 5.5 Write property test for actor ID extraction (Property 2)
    - **Property 2: Actor ID extraction from JWT**
    - Generate random JWT payloads with `sub` claims using fast-check, encode as base64 JWT tokens
    - Verify `extractActorId` returns the exact `sub` value
    - `// Feature: agentcore-short-term-memory, Property 2: Actor ID extraction from JWT`
    - **Validates: Requirements 2.1**

  - [x] 5.6 Write property test for invalid token handling (Property 3)
    - **Property 3: Invalid token yields no actor ID**
    - Generate random invalid inputs (null, empty string, malformed base64, JWTs without sub) using fast-check
    - Verify `extractActorId` returns `undefined`
    - `// Feature: agentcore-short-term-memory, Property 3: Invalid token yields no actor ID`
    - **Validates: Requirements 2.2**

- [x] 6. Checkpoint — Frontend session tracking and identity
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Provision AgentCore Memory resource and IAM permissions in CDK
  - [x] 7.1 Add `_create_memory_resource` method to `infra/stacks/bush_ranger_stack.py`
    - Use `AwsCustomResource` to call `CreateMemory` via the `BedrockAgentCore` boto3 API with `on_create` and `on_delete` SDK calls
    - Set `physical_resource_id` from the `memoryId` response field
    - Grant the custom resource IAM permissions for `bedrock-agentcore:CreateMemory` and `bedrock-agentcore:DeleteMemory`
    - _Requirements: 5.1_

  - [x] 7.2 Pass `MEMORY_ID` environment variable to the agent runtime
    - Wire the memory resource's `memoryId` (from `PhysicalResourceId`) as the `MEMORY_ID` environment variable on the agent runtime configuration
    - _Requirements: 5.2_

  - [x] 7.3 Add IAM permissions for memory operations to the agent role
    - Grant the agent runtime IAM role `bedrock-agentcore:InvokeMemory` and `bedrock-agentcore:RetrieveMemory` actions
    - Scope permissions to the specific memory resource ARN: `arn:aws:bedrock-agentcore:{region}:{account}:memory/{memoryId}`
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 7.4 Add `MEMORY_ID` as a CloudFormation stack output
    - Add a `CfnOutput` for the memory resource identifier
    - _Requirements: 5.3_

  - [x] 7.5 Write unit tests for CDK memory resource provisioning
    - Verify synthesized template contains the custom resource for memory creation
    - Verify `MEMORY_ID` env var is wired to the agent runtime
    - Verify IAM policy contains `InvokeMemory` and `RetrieveMemory` actions scoped to the memory resource ARN
    - Verify stack output for memory ID exists
    - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3_

- [x] 8. Final checkpoint — Full integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The agent gracefully degrades to stateless operation if memory is unavailable

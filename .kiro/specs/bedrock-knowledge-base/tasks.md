# Implementation Plan: Bedrock Knowledge Base Semantic Search

## Overview

Replace the string-matching `search_documents` tool with semantic search powered by a Bedrock Knowledge Base. Implementation proceeds in three phases: CDK infrastructure (Knowledge Base, S3 vector store, data source, IAM), MCP server updates (semantic search with fallback), and test coverage (unit + property-based tests).

## Tasks

- [x] 1. Add Bedrock Knowledge Base infrastructure to CDK stack
  - [x] 1.1 Create `_create_knowledge_base()` method in `BushRangerStack`
    - Add a new private method `_create_knowledge_base()` to `infra/stacks/bush_ranger_stack.py`
    - Create an IAM role for the Knowledge Base with `s3:GetObject` on the docs bucket and `bedrock:InvokeModel` on the Titan embeddings model ARN (`arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0`)
    - Create a `AWS::Bedrock::KnowledgeBase` CfnResource with S3 vector store storage config and the Titan embeddings model
    - Create a `AWS::Bedrock::DataSource` CfnResource referencing the docs bucket with fixed-size chunking (300 tokens, 20% overlap)
    - Call `_create_knowledge_base()` in `__init__` after `_create_docs_bucket()`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [x] 1.2 Update conservation docs IAM role with `bedrock:Retrieve` permission
    - In `_create_iam_roles()`, add a policy statement to the `conservation_docs` role granting `bedrock:Retrieve` on the Knowledge Base ARN
    - Ensure existing S3 permissions are preserved
    - _Requirements: 4.1, 4.2_

  - [x] 1.3 Add stack outputs and MCP server runtime environment variable
    - Add `KnowledgeBaseId` and `DataSourceId` CfnOutputs in `_create_outputs()`
    - Add `KNOWLEDGE_BASE_ID` environment variable to the conservation docs MCP server runtime properties
    - _Requirements: 1.5, 5.1_

  - [x] 1.4 Write CDK template unit tests for Knowledge Base resources (P1–P4)
    - Add tests to `tests/test_stack.py` verifying:
      - `AWS::Bedrock::KnowledgeBase` resource exists with Titan embeddings v2 model and S3 storage config
      - `AWS::Bedrock::DataSource` resource exists with docs bucket reference and chunking config (300 tokens, 20% overlap)
      - KB IAM role has `s3:GetObject` and `bedrock:InvokeModel` permissions
      - Conservation docs role has `bedrock:Retrieve` permission
      - Stack outputs include KnowledgeBaseId and DataSourceId
    - **Property 1: Knowledge Base resource is correctly configured**
    - **Property 2: Data Source references docs bucket with correct chunking**
    - **Property 3: IAM roles have correct least-privilege permissions**
    - **Property 4: Stack outputs include Knowledge Base and Data Source IDs**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 4.1, 4.2**

- [x] 2. Checkpoint — Verify CDK infrastructure
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Update MCP server with semantic search
  - [x] 3.1 Add Bedrock agent runtime client and helpers
    - In `services/mcp_servers/conservation_docs/server.py`, add `_KNOWLEDGE_BASE_ID` from `os.environ.get("KNOWLEDGE_BASE_ID")`
    - Add `_get_bedrock_agent_runtime_client()` returning `boto3.client("bedrock-agent-runtime")`
    - Add `_parse_s3_uri(uri: str) -> tuple[str, str]` helper that extracts `(object_key, category)` from an S3 URI
    - Extract existing substring-matching logic into `_fallback_search(query: str) -> dict[str, Any]`
    - _Requirements: 2.3, 2.6, 5.2_

  - [x] 3.2 Rewrite `search_documents` tool with semantic search and fallback
    - Rename parameter from `keyword` to `query`, add optional `max_results` parameter (default 5, capped at [1, 20])
    - When `_KNOWLEDGE_BASE_ID` is set: call `bedrock-agent-runtime.retrieve()` with the query and `numberOfResults`, map results to response structure with `source_uri`, `document_key`, `category`, `text`, `score`
    - When `_KNOWLEDGE_BASE_ID` is not set: log warning and delegate to `_fallback_search()`
    - Handle `ClientError` by returning `{"error": "retrieval_error", "message": "..."}`
    - Handle unparseable S3 URIs by skipping the result and logging a warning
    - Handle empty `retrievalResults` by returning `{"results": [], "count": 0}`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.2_

  - [x] 3.3 Write property tests for MCP server (P5–P8)
    - Add tests to `tests/test_properties_docs.py`:
    - **Property 5: Semantic search returns correctly structured results** — generate random query strings and mock Bedrock responses, verify each result has `source_uri`, `document_key`, `category`, `text`, `score`
    - **Validates: Requirements 2.1, 2.2**
    - **Property 6: S3 URI parsing round-trip** — generate random (category, filename) pairs, build S3 URI, parse with `_parse_s3_uri`, verify original key and category recovered
    - **Validates: Requirements 2.3**
    - **Property 7: max_results parameter clamping** — generate random integers, mock Bedrock client, verify `numberOfResults` passed to retrieve is clamped to [1, 20] and defaults to 5
    - **Validates: Requirements 2.4**
    - **Property 8: Fallback to substring matching without Knowledge Base ID** — generate random query strings with `KNOWLEDGE_BASE_ID` unset, verify only S3 is called and Bedrock is not
    - **Validates: Requirements 5.2**

  - [x] 3.4 Write unit tests for semantic search, error handling, and fallback
    - Add tests to `tests/test_conservation_docs.py`:
    - Test semantic search returns structured results with mocked Bedrock retrieve
    - Test `search_documents` returns structured error on `ClientError`
    - Test fallback logs warning when `KNOWLEDGE_BASE_ID` is not set
    - Test `list_documents` and `get_document` still work unchanged
    - Test `list_documents` and `get_document` do not use Bedrock client
    - Test unparseable URI in results is skipped
    - Test empty retrieval results returns `{"results": [], "count": 0}`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 2.5, 3.1, 3.2, 3.3_

- [x] 4. Checkpoint — Verify MCP server and all tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update IAM allowed actions in property test fixture
  - [x] 5.1 Update `_ALLOWED_ACTIONS` in `tests/test_properties_stack.py`
    - Add `bedrock:Retrieve` to the `docs` role allowed actions set
    - Add the KB role's allowed actions (`s3:GetObject`, `bedrock:InvokeModel`, `logs:CreateLogStream`, `logs:PutLogEvents`) to the allowed set
    - _Requirements: 4.1, 1.4_

- [x] 6. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- CDK uses `CfnResource` for Bedrock resources since L2 constructs aren't available yet
- Property tests use Hypothesis with `@settings(max_examples=100, database=None)`
- Tests run with: `bush-ranger-venv/bin/python -m pytest tests/ -v`
- Frontend tests: `cd frontend && npx vitest --run`

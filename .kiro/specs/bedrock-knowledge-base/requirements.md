# Requirements Document

## Introduction

Replace the current string-matching document search in the conservation_docs MCP server with semantic search powered by Amazon Bedrock Knowledge Base backed by an S3 vector store. The existing S3 docs bucket already contains conservation documents (species info, management plans, emergency procedures). CDK infrastructure will provision the Knowledge Base and S3 vector store, and the MCP server will be updated to query the Knowledge Base instead of performing naive substring matching.

## Glossary

- **Knowledge_Base**: An Amazon Bedrock Knowledge Base resource that ingests documents from a data source, chunks them, generates vector embeddings, and stores them in a vector store for semantic retrieval.
- **S3_Vector_Store**: An Amazon S3-based vector store used by the Knowledge_Base to persist document embeddings. This is the storage backend for the vector index.
- **Data_Source**: A Bedrock Knowledge Base data source configuration that points to the existing S3 docs bucket so the Knowledge_Base can ingest conservation documents.
- **MCP_Server**: The conservation_docs FastMCP server (`services/mcp_servers/conservation_docs/server.py`) that exposes document tools to the Bush Ranger AI agent.
- **Docs_Bucket**: The existing S3 bucket (`bush-ranger-docs-{account}-{region}`) containing conservation documents organised by category (species, management_plans, emergency).
- **CDK_Stack**: The existing AWS CDK stack (`infra/stacks/bush_ranger_stack.py`) that provisions all Bush Ranger AI infrastructure.
- **Semantic_Search**: A search method that uses vector embeddings to find documents by meaning rather than exact keyword matching.
- **Chunking_Strategy**: The method used by the Knowledge_Base to split documents into smaller segments before embedding. Bedrock supports fixed-size, default, and semantic chunking.
- **Retrieval_Response**: The structured result returned by the Bedrock `retrieve` API, containing matched text passages, source metadata, and relevance scores.

## Requirements

### Requirement 1: Provision Bedrock Knowledge Base Infrastructure

**User Story:** As a platform engineer, I want CDK to provision a Bedrock Knowledge Base with an S3 vector store, so that conservation documents are automatically indexed for semantic search.

#### Acceptance Criteria

1. WHEN the CDK_Stack is synthesised, THE CDK_Stack SHALL create a Knowledge_Base resource configured with an Amazon Titan Text Embeddings v2 foundation model in us-east-1.
2. WHEN the CDK_Stack is synthesised, THE CDK_Stack SHALL create an S3_Vector_Store resource as the storage configuration for the Knowledge_Base.
3. WHEN the CDK_Stack is synthesised, THE CDK_Stack SHALL create a Data_Source resource that references the existing Docs_Bucket as the ingestion source for the Knowledge_Base.
4. WHEN the CDK_Stack is synthesised, THE CDK_Stack SHALL create an IAM role for the Knowledge_Base with least-privilege permissions to read from the Docs_Bucket and invoke the embedding model.
5. WHEN the CDK_Stack is synthesised, THE CDK_Stack SHALL output the Knowledge_Base ID and Data_Source ID as CloudFormation stack outputs.
6. THE CDK_Stack SHALL configure the Data_Source with a Chunking_Strategy that uses fixed-size chunking with a maximum token size of 300 and an overlap of 20 percent.

### Requirement 2: Update MCP Server with Semantic Search Tool

**User Story:** As a conservation ranger using the AI agent, I want to search documents by meaning rather than exact keywords, so that I get relevant results even when my query wording differs from the document text.

#### Acceptance Criteria

1. WHEN a user calls the search_documents tool with a query string, THE MCP_Server SHALL send the query to the Knowledge_Base `retrieve` API instead of performing substring matching against S3 objects.
2. WHEN the Knowledge_Base returns a Retrieval_Response, THE MCP_Server SHALL return each result with the document source URI, the matched text passage, and the relevance score.
3. WHEN the Knowledge_Base returns a Retrieval_Response, THE MCP_Server SHALL map each result source URI back to the original S3 object key and document category.
4. WHEN the search_documents tool is called, THE MCP_Server SHALL accept an optional `max_results` parameter that defaults to 5 and caps at 20.
5. IF the Knowledge_Base `retrieve` API call fails, THEN THE MCP_Server SHALL return a structured error dict with an "error" key and a descriptive "message" key.
6. THE MCP_Server SHALL read the Knowledge_Base ID from the `KNOWLEDGE_BASE_ID` environment variable.

### Requirement 3: Preserve Existing MCP Tools

**User Story:** As a conservation ranger, I want to continue listing and retrieving individual documents by category and key, so that direct document access still works alongside semantic search.

#### Acceptance Criteria

1. THE MCP_Server SHALL continue to expose the `list_documents` tool that lists documents by category from the Docs_Bucket via S3.
2. THE MCP_Server SHALL continue to expose the `get_document` tool that retrieves a single document by S3 key from the Docs_Bucket.
3. WHEN the `list_documents` or `get_document` tools are called, THE MCP_Server SHALL use the existing S3 client logic without depending on the Knowledge_Base.

### Requirement 4: Update IAM Permissions for MCP Server Role

**User Story:** As a platform engineer, I want the conservation docs IAM role to have permissions to query the Bedrock Knowledge Base, so that the MCP server can perform semantic search at runtime.

#### Acceptance Criteria

1. WHEN the CDK_Stack is synthesised, THE CDK_Stack SHALL grant the conservation docs IAM role permission to call `bedrock:Retrieve` on the Knowledge_Base resource.
2. WHEN the CDK_Stack is synthesised, THE CDK_Stack SHALL retain the existing S3 read permissions on the conservation docs IAM role for the `list_documents` and `get_document` tools.

### Requirement 5: Pass Knowledge Base Configuration to MCP Server

**User Story:** As a platform engineer, I want the Knowledge Base ID to be passed to the MCP server runtime as an environment variable, so that the server can locate the correct Knowledge Base at runtime.

#### Acceptance Criteria

1. WHEN the CDK_Stack is synthesised, THE CDK_Stack SHALL configure the conservation docs MCP server runtime with a `KNOWLEDGE_BASE_ID` environment variable set to the Knowledge_Base resource ID.
2. IF the `KNOWLEDGE_BASE_ID` environment variable is not set, THEN THE MCP_Server SHALL log a warning and fall back to the existing substring-matching search behaviour for the `search_documents` tool.

### Requirement 6: Test Coverage for Semantic Search

**User Story:** As a developer, I want unit tests that verify the semantic search integration with mocked Bedrock calls, so that regressions are caught without requiring live AWS resources.

#### Acceptance Criteria

1. THE test suite SHALL include unit tests for the updated `search_documents` tool that mock the Bedrock `retrieve` API and verify the response structure contains source URI, matched text, and relevance score.
2. THE test suite SHALL include a unit test that verifies the `search_documents` tool returns a structured error when the Bedrock `retrieve` API call raises a `ClientError`.
3. THE test suite SHALL include a unit test that verifies the `search_documents` tool falls back to substring matching when the `KNOWLEDGE_BASE_ID` environment variable is not set.
4. THE test suite SHALL include unit tests that verify the existing `list_documents` and `get_document` tools continue to function with mocked S3.

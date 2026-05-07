# Implementation Plan: Art Gallery

## Overview

Implement the Art Gallery feature for Bush Ranger AI: a new MCP server for AI image generation of Australian wildlife/nature using Stability AI Stable Image Core, with async background processing, S3 storage, CloudFront serving, and a React gallery page. Tasks are ordered so each builds on the previous, starting with the backend MCP server, then CDK infrastructure, then frontend, then wiring everything together.

## Tasks

- [x] 1. Create the Art Gallery MCP server with content validation and job management
  - [x] 1.1 Create `services/mcp_servers/art_gallery/` directory with `__init__.py`, `server.py`, `requirements.txt`, `logging_config.py`, and `Dockerfile`
    - In `server.py`, implement the `ContentValidator` class with `ALLOWED_TOPICS` list, `SYSTEM_PROMPT_PREFIX`, `validate(prompt)` method (checks lowercased prompt for keyword match), and `build_full_prompt(prompt)` method (prepends prefix, enforces 512-char max)
    - Implement the `Job` dataclass with fields: `job_id`, `status`, `prompt`, `created_at`, `s3_key`, `cloudfront_url`, `error`
    - Implement the in-memory `_jobs` dict with `threading.Lock` for thread-safe access
    - Create the FastMCP server instance (`mcp = FastMCP("art-gallery", host="0.0.0.0", stateless_http=True)`)
    - `requirements.txt` should include: `mcp>=1.19.0`, `boto3`, `Pillow`
    - `Dockerfile` follows the existing pattern (python:3.12-slim, EXPOSE 8000)
    - Copy `logging_config.py` from an existing MCP server
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 6.4_

  - [x] 1.2 Implement the `generate_image` tool
    - Validate prompt via `ContentValidator.validate()`, return error if rejected
    - Check prompt length after prefix (max 512 chars), return error if too long
    - Create a `Job` with unique UUID4 `job_id` and status `"generating"`
    - Spawn a background thread calling `_generate_image_background(job_id, full_prompt)`
    - Return `{job_id, status: "generating"}` immediately
    - _Requirements: 1.1, 1.2, 1.3, 2.3, 2.4, 2.5, 6.1, 6.2, 6.3_

  - [x] 1.3 Implement the `_generate_image_background` function
    - Call `bedrock_runtime.invoke_model()` with Stable Image Core payload (model ID: `us.stability.stable-image-style-guide-v1:0`)
    - Decode base64 response to PNG bytes
    - Use Pillow to create 200×200 thumbnail
    - Upload full-size image to S3 at `ArtGallery/{job_id}.png` with Content-Type `image/png` and metadata (`x-amz-meta-prompt`, `x-amz-meta-timestamp`)
    - Upload thumbnail to S3 at `ArtGallery/{job_id}_thumb.png` with same metadata
    - Update job status to `"completed"` with `s3_key` and `cloudfront_url`, or `"failed"` with error message
    - All job dict access must use the threading lock
    - _Requirements: 1.3, 1.4, 1.5, 5.1, 5.2, 5.4, 5.5, 5.6_

  - [x] 1.4 Implement the `get_job_status` tool
    - Look up job by ID in `_jobs` dict (thread-safe)
    - Return status-dependent response per design: generating → `{job_id, status}`, completed → `{job_id, status, s3_key, cloudfront_url}`, failed → `{job_id, status, error}`
    - Return `{error: "job_not_found"}` if job ID not in store
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 1.5 Implement the `list_gallery_images` tool
    - Call `s3.list_objects_v2(Bucket=..., Prefix="ArtGallery/")`
    - Filter out `_thumb.png` keys (only return full-size images)
    - For each image, read S3 object metadata (prompt, timestamp) via `head_object`
    - Build CloudFront URLs for thumbnail and full-size images
    - Return list of `{s3_key, prompt, timestamp, thumbnail_url, full_url}`
    - Return empty list with count 0 if no images exist
    - _Requirements: 4.1, 4.2, 4.3, 5.7_

  - [x] 1.6 Write property tests for content validation (Properties 1 & 2)
    - **Property 1: Content validation correctness** — Generate random strings with Hypothesis, verify `validate()` returns True iff lowercased prompt contains at least one allowed keyword
    - **Validates: Requirements 2.2, 2.3**
    - **Property 2: System prompt prefix is prepended** — Generate random valid prompts, verify `build_full_prompt()` output starts with the prefix and total length ≤ 512
    - **Validates: Requirements 2.4**

  - [x] 1.7 Write property tests for job management (Properties 3 & 5)
    - **Property 3: Job creation returns unique IDs with generating status** — Submit multiple valid prompts, verify all returned job IDs are unique and status is "generating"
    - **Validates: Requirements 1.2**
    - **Property 5: Job status response contains correct fields per status** — Create jobs in each status, verify `get_job_status` returns correct fields
    - **Validates: Requirements 3.2, 3.3, 3.4**

  - [x] 1.8 Write property tests for image storage and thumbnails (Properties 6 & 7)
    - **Property 6: Image storage uses correct key pattern and metadata** — Generate random job IDs and prompts, verify S3 key pattern and metadata
    - **Validates: Requirements 5.1, 5.4**
    - **Property 7: Thumbnail generation produces correct dimensions and key** — Generate random image sizes, verify thumbnail is 200×200 and key pattern is correct
    - **Validates: Requirements 5.5, 5.7**

  - [x] 1.9 Write property test for job completion (Property 4)
    - **Property 4: Job completion reflects Bedrock outcome** — Mock Bedrock success/failure, verify job status transitions correctly
    - **Validates: Requirements 1.4, 1.5**

  - [x] 1.10 Write property test for gallery listing (Property 8)
    - **Property 8: Gallery listing returns complete entries** — Generate random S3 object listings with moto, verify `list_gallery_images` returns one entry per full-size image with all required fields
    - **Validates: Requirements 4.2**

- [x] 2. Checkpoint - Verify MCP server implementation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Add CDK infrastructure for the Art Gallery MCP server
  - [x] 3.1 Add IAM role, log group, and ECR image for the art-gallery MCP server
    - Create `art_gallery` IAM role with `bedrock.amazonaws.com` and `bedrock-agentcore.amazonaws.com` principals
    - Grant `bedrock:InvokeModel` on `arn:aws:bedrock:*::foundation-model/us.stability.stable-image-style-guide-v1:0`
    - Grant `s3:PutObject` on `{frontend_bucket_arn}/ArtGallery/*`
    - Grant `s3:ListBucket` on `{frontend_bucket_arn}` (for `list_objects_v2`)
    - Grant `s3:GetObject` on `{frontend_bucket_arn}/ArtGallery/*` (for `head_object` metadata reads)
    - Add ECR pull permissions and AgentCore runtime logging permissions (same pattern as existing roles)
    - Add log group `/bush-ranger/mcp/art-gallery` to `_create_log_groups`
    - Grant log write permissions to the art-gallery role
    - Build Docker image asset for `services/mcp_servers/art_gallery`
    - _Requirements: 8.1, 8.2, 8.4_

  - [x] 3.2 Register the art-gallery AgentCore runtime and update agent runtime
    - Create `AWS::BedrockAgentCore::Runtime` for art-gallery with container config, MCP protocol, Cognito JWT authorizer, and environment variables (`S3_BUCKET_NAME`, `CLOUDFRONT_DOMAIN`)
    - Add `ART_GALLERY_RUNTIME_ARN` env var to the agent runtime
    - Grant agent role `bedrock-agentcore:InvokeAgentRuntime` on the art-gallery runtime ARN
    - _Requirements: 8.5_

  - [x] 3.3 Add CloudFront `/gallery/*` cache behavior with OAC
    - Add an additional behavior to the existing CloudFront distribution for path pattern `/gallery/*`
    - Point to the frontend S3 bucket origin with OAC (same origin as default behavior)
    - Use `CACHING_OPTIMIZED` cache policy
    - _Requirements: 5.3, 8.3_

- [x] 4. Update the agent handler to connect to the art-gallery MCP server
  - Add `ART_GALLERY_RUNTIME_ARN` env var reading in `handler.py`
  - Add `("art_gallery", ART_GALLERY_RUNTIME_ARN)` to the `endpoints` list in `_build_mcp_clients()`
  - Update the `SYSTEM_PROMPT` to mention the art-gallery MCP server and its tools (`generate_image`, `get_job_status`, `list_gallery_images`)
  - Add `art-gallery` to the tool attribution footer in the system prompt
  - _Requirements: 8.5_

- [x] 5. Checkpoint - Verify backend and infrastructure
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement the frontend Gallery page
  - [x] 6.1 Create `frontend/src/gallery/GalleryPage.tsx`
    - Fetch gallery images by sending a chat message to the agent (e.g., "list gallery images") or via a dedicated API call
    - Display thumbnails in a Cloudscape `Grid` with responsive column definitions
    - Each card shows the thumbnail image, prompt text, and formatted generation date
    - Show Cloudscape `Spinner` while loading
    - Show Cloudscape `Box` with informational message when gallery is empty
    - Implement click-to-expand: clicking a thumbnail opens a Cloudscape `Modal` displaying the full-size image via the CloudFront URL
    - _Requirements: 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 6.2 Add Gallery page to App routing and SideNavigation
    - Add `{ type: 'link', text: 'Gallery', href: '/gallery' }` to `NAV_ITEMS` in `App.tsx`
    - Add `'gallery'` to the `PageId` type
    - Add Gallery page rendering in the `AppContent` component (same pattern as Dashboard)
    - Import `GalleryPage` from `./gallery/GalleryPage`
    - _Requirements: 7.1_

  - [x] 6.3 Write property test for gallery card rendering (Property 9)
    - **Property 9: Gallery card renders prompt and date** — Generate random gallery entries with fast-check, verify the rendered card displays prompt text and formatted date
    - **Validates: Requirements 7.6**

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The MCP server uses Python (pytest + Hypothesis for testing), the frontend uses TypeScript (vitest + fast-check)
- Backend tests should use `moto` for S3 mocking and `unittest.mock` for Bedrock mocking

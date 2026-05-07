# Requirements Document

## Introduction

The Art Gallery feature adds an image generation capability to Bush Ranger AI. A new MCP server called "art-gallery" uses Stability AI Stable Image Core via Bedrock to generate images of Australian wildlife and nature. Image generation runs asynchronously in a background thread so the agent can respond immediately with a job ID. Generated images are stored in S3 under an "ArtGallery" prefix and displayed on a new Art Gallery page in the frontend. Content guardrails restrict generation to Australian wildlife and nature themes to stay on-brand with the Bush Ranger application.

## Glossary

- **Art_Gallery_Server**: The FastMCP server that exposes tools for generating images and browsing the gallery
- **Image_Generator**: The component within the Art_Gallery_Server that invokes Stability AI Stable Image Core via Bedrock InvokeModel to produce images
- **Job**: A unit of work representing a single image generation request, identified by a unique job ID and tracked through statuses (generating, completed, failed)
- **Job_Store**: An in-memory dictionary within the Art_Gallery_Server that tracks the status and metadata of all image generation jobs
- **Content_Validator**: The component within the Art_Gallery_Server that checks user prompts against allowed Australian wildlife and nature topics before forwarding to Bedrock
- **System_Prompt_Prefix**: A fixed text string prepended to every user prompt before sending to Stable Image Core, constraining output to Australian wildlife and nature imagery
- **Gallery_Page**: The React frontend page that displays generated images in a browsable gallery layout
- **S3_Gallery_Store**: The S3 bucket location under the "ArtGallery/" prefix where generated images are stored
- **Gallery_CloudFront_Path**: The CloudFront distribution path `/gallery/` that serves images from the S3_Gallery_Store via Origin Access Control (OAC), with no expiry and no public bucket access

## Requirements

### Requirement 1: Image Generation Tool

**User Story:** As a park ranger, I want to ask the agent to generate images of Australian wildlife and nature, so that I can create visual materials for educational displays and reports.

#### Acceptance Criteria

1. WHEN a user submits a prompt to the generate_image tool, THE Art_Gallery_Server SHALL validate the prompt using the Content_Validator before invoking the Image_Generator
2. WHEN the Content_Validator approves a prompt, THE Art_Gallery_Server SHALL create a new Job with a unique job ID and a status of "generating", and return the job ID and status to the caller within 2 seconds
3. WHEN a Job is created, THE Image_Generator SHALL invoke Stability AI Stable Image Core (us.stability.stable-image-style-guide-v1:0) via Bedrock InvokeModel in a background thread
4. WHEN the Image_Generator completes successfully, THE Art_Gallery_Server SHALL decode the base64 image data, store the image as a PNG file in the S3_Gallery_Store under the "ArtGallery/" prefix, and update the Job status to "completed"
5. IF the Image_Generator invocation fails, THEN THE Art_Gallery_Server SHALL update the Job status to "failed" and record the error message in the Job metadata

### Requirement 2: Content Guardrails

**User Story:** As a product owner, I want image generation restricted to Australian wildlife and nature themes, so that the feature stays on-brand with the Bush Ranger application.

#### Acceptance Criteria

1. THE Content_Validator SHALL maintain a list of allowed topics including Australian animals, Australian plants, Australian landscapes, Australian national parks, and Australian marine life
2. WHEN a prompt is submitted, THE Content_Validator SHALL check the prompt text against the allowed topics list
3. IF the Content_Validator determines a prompt does not relate to Australian wildlife or nature, THEN THE Art_Gallery_Server SHALL reject the request and return a descriptive error message explaining the allowed topics
4. THE System_Prompt_Prefix SHALL prepend the text "Generate a realistic image of Australian wildlife or nature: " to every approved prompt before sending to Bedrock
5. WHEN a prompt passes validation, THE Content_Validator SHALL log the original prompt for audit purposes

### Requirement 3: Job Status Polling

**User Story:** As a park ranger, I want to check the status of my image generation request, so that I know when the image is ready to view.

#### Acceptance Criteria

1. THE Art_Gallery_Server SHALL expose a get_job_status tool that accepts a job ID and returns the current Job status
2. WHEN a Job has status "completed", THE get_job_status tool SHALL return the job ID, status, the S3 object key, and the CloudFront URL for the generated image
3. WHEN a Job has status "generating", THE get_job_status tool SHALL return the job ID and status "generating"
4. WHEN a Job has status "failed", THE get_job_status tool SHALL return the job ID, status "failed", and the recorded error message
5. IF a job ID does not exist in the Job_Store, THEN THE get_job_status tool SHALL return an error indicating the job was not found

### Requirement 4: Gallery Browsing Tool

**User Story:** As a park ranger, I want to browse all previously generated images, so that I can find and reuse images from past requests.

#### Acceptance Criteria

1. THE Art_Gallery_Server SHALL expose a list_gallery_images tool that lists all images stored under the "ArtGallery/" prefix in S3
2. WHEN the list_gallery_images tool is called, THE Art_Gallery_Server SHALL return a list of image entries, each containing the S3 object key, the original prompt, the generation timestamp, a thumbnail CloudFront URL, and a full-size CloudFront URL
3. IF no images exist in the S3_Gallery_Store, THEN THE list_gallery_images tool SHALL return an empty list with a count of zero

### Requirement 5: S3 Image Storage

**User Story:** As a system operator, I want generated images stored durably in S3, so that images persist across server restarts and are accessible via the frontend.

#### Acceptance Criteria

1. THE Art_Gallery_Server SHALL store each generated image as a PNG file in S3 under the key pattern "ArtGallery/{job_id}.png"
2. THE Art_Gallery_Server SHALL set the S3 object Content-Type metadata to "image/png" for each stored image
3. THE S3_Gallery_Store SHALL be served via the existing CloudFront distribution under the "/gallery/" path using Origin Access Control (OAC), with the S3 bucket remaining private
4. WHEN storing an image, THE Art_Gallery_Server SHALL include the original prompt and generation timestamp as S3 object metadata
5. WHEN storing an image, THE Art_Gallery_Server SHALL generate a thumbnail by resizing the image to 200x200 pixels and store it under the key pattern "ArtGallery/{job_id}_thumb.png"
6. THE Art_Gallery_Server SHALL use the Pillow (PIL) library for thumbnail generation
7. WHEN the list_gallery_images tool returns image entries, THE thumbnail URL for each entry SHALL reference the CloudFront path for the thumbnail image

### Requirement 6: Asynchronous Generation

**User Story:** As a park ranger interacting with the agent, I want the agent to respond immediately when I request an image, so that I am not blocked waiting for generation to complete.

#### Acceptance Criteria

1. WHEN the generate_image tool is called, THE Art_Gallery_Server SHALL return the job ID and "generating" status before the Bedrock InvokeModel call completes
2. THE Art_Gallery_Server SHALL execute the Bedrock InvokeModel call and S3 upload in a separate background thread
3. WHILE a background generation thread is running, THE Art_Gallery_Server SHALL continue to accept and process new tool calls without blocking
4. IF the Art_Gallery_Server process restarts while a Job has status "generating", THEN THE Art_Gallery_Server SHALL treat the Job as lost (the in-memory Job_Store does not persist across restarts)

### Requirement 7: Frontend Gallery Page

**User Story:** As a park ranger, I want a dedicated gallery page on the website to view all generated images, so that I can browse and appreciate the generated artwork.

#### Acceptance Criteria

1. THE Gallery_Page SHALL be accessible via a "Gallery" link in the SideNavigation component
2. WHEN the Gallery_Page loads, THE Gallery_Page SHALL fetch the list of gallery images from the backend and display thumbnail images in a responsive grid layout
3. WHEN a user clicks on an image thumbnail, THE Gallery_Page SHALL display the full-size image using the full-size CloudFront URL in a modal or expanded view
4. WHILE images are loading, THE Gallery_Page SHALL display a loading spinner
5. IF no images are available, THEN THE Gallery_Page SHALL display an informational message indicating the gallery is empty
6. THE Gallery_Page SHALL display the original prompt text and generation date beneath each image thumbnail

### Requirement 8: Infrastructure and Permissions

**User Story:** As a system operator, I want the Art Gallery MCP server provisioned with correct IAM permissions and infrastructure, so that the server can access Bedrock and S3 securely.

#### Acceptance Criteria

1. THE CDK stack SHALL create an IAM role for the Art_Gallery_Server with permissions to invoke Bedrock model us.stability.stable-image-style-guide-v1:0
2. THE CDK stack SHALL grant the Art_Gallery_Server IAM role permissions to put objects in the S3_Gallery_Store under the "ArtGallery/" prefix
3. THE CDK stack SHALL add a CloudFront origin and cache behavior for the "/gallery/*" path, pointing to the S3_Gallery_Store with OAC, so images are served without public bucket access or presigned URLs
4. THE CDK stack SHALL create a CloudWatch log group for the Art_Gallery_Server at "/bush-ranger/mcp/art-gallery"
4. THE CDK stack SHALL register the Art_Gallery_Server as an AgentCore MCP server runtime with the appropriate container image and environment variables
5. THE agent handler SHALL include the Art_Gallery_Server runtime in the list of MCP clients connected at invocation time

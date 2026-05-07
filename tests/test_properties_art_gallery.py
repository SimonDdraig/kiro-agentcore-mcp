# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for the Art Gallery MCP server.

Uses hypothesis to verify correctness properties across randomised inputs.
Tests ContentValidator, ALLOWED_TOPICS, and SYSTEM_PROMPT_PREFIX from
services/mcp_servers/art_gallery/server.py.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path so services/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.mcp_servers.art_gallery.server import (
    ALLOWED_TOPICS,
    SYSTEM_PROMPT_PREFIX,
    ContentValidator,
    Job,
    _generate_image_background,
    _jobs,
    _jobs_lock,
)

_validator = ContentValidator()


# ===================================================================
# Property 1: Content validation correctness
# ===================================================================
class TestProperty1ContentValidationCorrectness:
    """Feature: art-gallery, Property 1: Content validation correctness."""

    @settings(max_examples=20, database=None)
    @given(prompt=st.text(min_size=0, max_size=300))
    def test_validate_matches_keyword_presence(self, prompt: str) -> None:
        """Feature: art-gallery, Property 1: Content validation correctness.

        For any prompt string, validate() returns True if and only if the
        lowercased prompt contains at least one keyword from ALLOWED_TOPICS.

        **Validates: Requirements 2.2, 2.3**
        """
        lowered = prompt.lower()
        has_keyword = any(topic in lowered for topic in ALLOWED_TOPICS)
        result = _validator.validate(prompt)
        assert result == has_keyword, f"validate() returned {result} but expected {has_keyword} for prompt: {prompt!r}"


# ===================================================================
# Property 2: System prompt prefix is prepended
# ===================================================================
class TestProperty2SystemPromptPrefixPrepended:
    """Feature: art-gallery, Property 2: System prompt prefix is prepended."""

    @settings(max_examples=20, database=None)
    @given(prompt=st.text(min_size=1, max_size=500))
    def test_build_full_prompt_starts_with_prefix_and_within_limit(self, prompt: str) -> None:
        """Feature: art-gallery, Property 2: System prompt prefix is prepended.

        For any approved prompt, build_full_prompt() returns a string that
        starts with the SYSTEM_PROMPT_PREFIX followed by the original prompt,
        and the total length does not exceed 512 characters.

        **Validates: Requirements 2.4**
        """
        result = _validator.build_full_prompt(prompt)

        # Must start with the system prompt prefix
        assert result.startswith(SYSTEM_PROMPT_PREFIX), (
            f"build_full_prompt() result does not start with prefix. Got: {result[:80]!r}"
        )

        # Total length must not exceed 512
        assert len(result) <= 512, f"build_full_prompt() result length {len(result)} exceeds 512"

        # The content after the prefix should be the prompt (possibly truncated)
        expected_full = SYSTEM_PROMPT_PREFIX + prompt
        expected_truncated = expected_full[:512]
        assert result == expected_truncated, (
            f"build_full_prompt() result does not match expected truncation. "
            f"Got length {len(result)}, expected {len(expected_truncated)}"
        )


# ===================================================================
# Property 3: Job creation returns unique IDs with generating status
# ===================================================================
class TestProperty3JobCreationReturnsUniqueIDs:
    """Feature: art-gallery, Property 3: Job creation returns unique IDs."""

    @settings(max_examples=20, database=None, deadline=None)
    @given(prompts=st.lists(st.text(min_size=1, max_size=200), min_size=2, max_size=10))
    def test_generate_image_returns_unique_ids_with_generating_status(self, prompts: list[str]) -> None:
        """Feature: art-gallery, Property 3: Job creation returns unique IDs.

        For any list of valid prompts submitted to generate_image, each
        returned response SHALL contain a unique job_id and status "generating".

        **Validates: Requirements 1.2**
        """
        from unittest.mock import MagicMock, patch

        from services.mcp_servers.art_gallery.server import (
            _jobs,
            _jobs_lock,
            generate_image,
        )

        # Mock threading.Thread to prevent actual background threads
        mock_thread = MagicMock()
        mock_thread_class = MagicMock(return_value=mock_thread)

        # Ensure each prompt contains an allowed keyword so validation passes
        valid_prompts = [f"koala {p}" for p in prompts]

        # Clear the job store before each test run
        with _jobs_lock:
            _jobs.clear()

        job_ids: list[str] = []
        with patch("services.mcp_servers.art_gallery.server.threading.Thread", mock_thread_class):
            for prompt in valid_prompts:
                result = generate_image(prompt)
                # Must not be an error response
                assert "error" not in result, f"generate_image returned error for valid prompt: {result}"
                assert "job_id" in result, f"Missing job_id in response: {result}"
                assert result["status"] == "generating", f"Expected status 'generating', got '{result['status']}'"
                job_ids.append(result["job_id"])

        # All job IDs must be unique
        assert len(set(job_ids)) == len(job_ids), f"Duplicate job IDs found: {job_ids}"


# ===================================================================
# Property 4: Job completion reflects Bedrock outcome
# ===================================================================
class TestProperty4JobCompletionReflectsBedrockOutcome:
    """Feature: art-gallery, Property 4: Job completion reflects Bedrock outcome."""

    @settings(max_examples=100, database=None, deadline=None)
    @given(
        job_id=st.uuids().map(str),
        prompt=st.text(min_size=1, max_size=200),
    )
    def test_bedrock_success_sets_completed_with_s3_key_and_url(
        self,
        job_id: str,
        prompt: str,
    ) -> None:
        """Feature: art-gallery, Property 4: Job completion reflects Bedrock outcome.

        For any job where Bedrock returns a valid base64 image response, the
        job status SHALL be "completed" with a non-null s3_key and
        cloudfront_url.

        **Validates: Requirements 1.4, 1.5**
        """
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        from PIL import Image as PILImage

        # Create a small valid PNG for the mock Bedrock response
        img = PILImage.new("RGB", (64, 64), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        now = datetime.now(UTC).isoformat()
        with _jobs_lock:
            _jobs[job_id] = Job(
                job_id=job_id,
                status="generating",
                prompt=prompt,
                created_at=now,
            )

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps({"images": [base64.b64encode(png_bytes).decode()]}).encode()),
        }
        mock_s3 = MagicMock()
        cf_domain = "d123.cloudfront.net"

        with (
            patch(
                "services.mcp_servers.art_gallery.server._get_bedrock_runtime_client",
                return_value=mock_bedrock,
            ),
            patch(
                "services.mcp_servers.art_gallery.server._get_s3_client",
                return_value=mock_s3,
            ),
            patch(
                "services.mcp_servers.art_gallery.server._S3_BUCKET_NAME",
                "test-bucket",
            ),
            patch(
                "services.mcp_servers.art_gallery.server._CLOUDFRONT_DOMAIN",
                cf_domain,
            ),
        ):
            _generate_image_background(job_id, f"Generate: {prompt}", "outback")

        with _jobs_lock:
            job = _jobs[job_id]

        assert job.status == "completed", f"Expected status 'completed', got '{job.status}'"
        assert job.s3_key is not None, "s3_key should not be None on success"
        assert job.cloudfront_url is not None, "cloudfront_url should not be None on success"

        # Cleanup
        with _jobs_lock:
            _jobs.pop(job_id, None)

    @settings(max_examples=100, database=None, deadline=None)
    @given(
        job_id=st.uuids().map(str),
        prompt=st.text(min_size=1, max_size=200),
        error_msg=st.text(min_size=1, max_size=200),
    )
    def test_bedrock_failure_sets_failed_with_error(
        self,
        job_id: str,
        prompt: str,
        error_msg: str,
    ) -> None:
        """Feature: art-gallery, Property 4: Job completion reflects Bedrock outcome.

        For any job where Bedrock raises an exception, the job status SHALL
        be "failed" with a non-null error message.

        **Validates: Requirements 1.4, 1.5**
        """
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        now = datetime.now(UTC).isoformat()
        with _jobs_lock:
            _jobs[job_id] = Job(
                job_id=job_id,
                status="generating",
                prompt=prompt,
                created_at=now,
            )

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.side_effect = RuntimeError(error_msg)

        with (
            patch(
                "services.mcp_servers.art_gallery.server._get_bedrock_runtime_client",
                return_value=mock_bedrock,
            ),
            patch(
                "services.mcp_servers.art_gallery.server._S3_BUCKET_NAME",
                "test-bucket",
            ),
            patch(
                "services.mcp_servers.art_gallery.server._CLOUDFRONT_DOMAIN",
                "d123.cloudfront.net",
            ),
        ):
            _generate_image_background(job_id, f"Generate: {prompt}", "outback")

        with _jobs_lock:
            job = _jobs[job_id]

        assert job.status == "failed", f"Expected status 'failed', got '{job.status}'"
        assert job.error is not None, "error should not be None on failure"
        assert job.error == error_msg, f"Expected error '{error_msg}', got '{job.error}'"

        # Cleanup
        with _jobs_lock:
            _jobs.pop(job_id, None)


# ===================================================================
# Property 5: Job status response contains correct fields per status
# ===================================================================
class TestProperty5JobStatusResponseFields:
    """Feature: art-gallery, Property 5: Job status response contains correct fields."""

    @settings(max_examples=20, database=None)
    @given(
        job_id=st.uuids().map(str),
        prompt=st.text(min_size=1, max_size=200),
        s3_key=st.text(min_size=1, max_size=100).map(lambda t: f"ArtGallery/{t}.png"),
        cf_url=st.text(min_size=1, max_size=100).map(lambda t: f"https://example.cloudfront.net/{t}.png"),
        error_msg=st.text(min_size=1, max_size=200),
    )
    def test_get_job_status_returns_correct_fields_per_status(
        self,
        job_id: str,
        prompt: str,
        s3_key: str,
        cf_url: str,
        error_msg: str,
    ) -> None:
        """Feature: art-gallery, Property 5: Job status response contains correct fields.

        For any job in each status, get_job_status SHALL return the correct
        fields: generating -> {job_id, status}; completed -> {job_id, status,
        s3_key, cloudfront_url}; failed -> {job_id, status, error}.

        **Validates: Requirements 3.2, 3.3, 3.4**
        """
        from datetime import datetime

        from services.mcp_servers.art_gallery.server import (
            Job,
            _jobs,
            _jobs_lock,
            get_job_status,
        )

        now = datetime.now(UTC).isoformat()

        # --- Test "generating" status ---
        with _jobs_lock:
            _jobs[job_id] = Job(job_id=job_id, status="generating", prompt=prompt, created_at=now)
        result = get_job_status(job_id)
        assert result["job_id"] == job_id
        assert result["status"] == "generating"
        # generating responses should NOT contain s3_key, cloudfront_url, or error
        assert "s3_key" not in result
        assert "cloudfront_url" not in result
        assert "error" not in result

        # --- Test "completed" status ---
        with _jobs_lock:
            _jobs[job_id] = Job(
                job_id=job_id,
                status="completed",
                prompt=prompt,
                created_at=now,
                s3_key=s3_key,
                cloudfront_url=cf_url,
            )
        result = get_job_status(job_id)
        assert result["job_id"] == job_id
        assert result["status"] == "completed"
        assert result["s3_key"] == s3_key
        assert result["cloudfront_url"] == cf_url
        assert "error" not in result

        # --- Test "failed" status ---
        with _jobs_lock:
            _jobs[job_id] = Job(
                job_id=job_id,
                status="failed",
                prompt=prompt,
                created_at=now,
                error=error_msg,
            )
        result = get_job_status(job_id)
        assert result["job_id"] == job_id
        assert result["status"] == "failed"
        assert result["error"] == error_msg
        assert "s3_key" not in result
        assert "cloudfront_url" not in result

        # --- Cleanup ---
        with _jobs_lock:
            _jobs.pop(job_id, None)


# ===================================================================
# Property 6: Image storage uses correct key pattern and metadata
# ===================================================================
class TestProperty6ImageStorageKeyPatternAndMetadata:
    """Feature: art-gallery, Property 6: Image storage correctness."""

    @settings(max_examples=100, database=None, deadline=None)
    @given(
        job_id=st.uuids().map(str),
        prompt=st.text(min_size=1, max_size=200),
    )
    def test_image_storage_uses_correct_key_and_metadata(
        self,
        job_id: str,
        prompt: str,
    ) -> None:
        """Feature: art-gallery, Property 6: Image storage correctness.

        For any job ID and prompt, the full-size image SHALL be stored at S3
        key "ArtGallery/{job_id}.png" with Content-Type "image/png", and the
        S3 object metadata SHALL include the original prompt and an ISO 8601
        timestamp.

        **Validates: Requirements 5.1, 5.4**
        """
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        from PIL import Image as PILImage

        from services.mcp_servers.art_gallery.server import (
            Job,
            _generate_image_background,
            _jobs,
            _jobs_lock,
        )

        # Create a small valid PNG image for the mock Bedrock response
        img = PILImage.new("RGB", (64, 64), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        # Seed the job in the in-memory store
        now = datetime.now(UTC).isoformat()
        with _jobs_lock:
            _jobs[job_id] = Job(
                job_id=job_id,
                status="generating",
                prompt=prompt,
                created_at=now,
            )

        # Mock Bedrock and S3
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps({"images": [base64.b64encode(png_bytes).decode()]}).encode()),
        }

        mock_s3 = MagicMock()

        with (
            patch(
                "services.mcp_servers.art_gallery.server._get_bedrock_runtime_client",
                return_value=mock_bedrock,
            ),
            patch(
                "services.mcp_servers.art_gallery.server._get_s3_client",
                return_value=mock_s3,
            ),
            patch(
                "services.mcp_servers.art_gallery.server._S3_BUCKET_NAME",
                "test-bucket",
            ),
            patch(
                "services.mcp_servers.art_gallery.server._CLOUDFRONT_DOMAIN",
                "d123.cloudfront.net",
            ),
        ):
            _generate_image_background(job_id, f"Generate: {prompt}", "outback")

        # Verify S3 was called with correct key pattern and metadata
        assert mock_s3.put_object.call_count == 2, (
            f"Expected 2 S3 put_object calls, got {mock_s3.put_object.call_count}"
        )

        full_call = mock_s3.put_object.call_args_list[0]

        # S3 key must follow ArtGallery/{job_id}.png pattern
        expected_key = f"ArtGallery/{job_id}.png"
        assert full_call.kwargs["Key"] == expected_key, (
            f"Expected S3 key '{expected_key}', got '{full_call.kwargs['Key']}'"
        )

        # Content-Type must be image/png
        assert full_call.kwargs["ContentType"] == "image/png", (
            f"Expected ContentType 'image/png', got '{full_call.kwargs['ContentType']}'"
        )

        # Metadata must include prompt and timestamp
        metadata = full_call.kwargs["Metadata"]
        assert metadata["x-amz-meta-prompt"] == prompt, (
            f"Expected prompt '{prompt}' in metadata, got '{metadata.get('x-amz-meta-prompt')}'"
        )
        assert metadata["x-amz-meta-timestamp"] == now, (
            f"Expected timestamp '{now}' in metadata, got '{metadata.get('x-amz-meta-timestamp')}'"
        )

        # Cleanup
        with _jobs_lock:
            _jobs.pop(job_id, None)


# ===================================================================
# Property 7: Thumbnail generation produces correct dimensions and key
# ===================================================================
class TestProperty7ThumbnailDimensionsAndKey:
    """Feature: art-gallery, Property 7: Thumbnail generation correctness."""

    @settings(max_examples=100, database=None, deadline=None)
    @given(
        job_id=st.uuids().map(str),
        width=st.integers(min_value=10, max_value=4096),
        height=st.integers(min_value=10, max_value=4096),
    )
    def test_thumbnail_is_200x200_with_correct_key_and_url(
        self,
        job_id: str,
        width: int,
        height: int,
    ) -> None:
        """Feature: art-gallery, Property 7: Thumbnail generation correctness.

        For any generated image of arbitrary dimensions, the thumbnail SHALL
        be exactly 200x200 pixels (or smaller if the source is smaller),
        stored at S3 key "ArtGallery/{job_id}_thumb.png", and the
        corresponding CloudFront URL SHALL follow the pattern
        https://<cf-domain>/ArtGallery/{job_id}_thumb.png.

        **Validates: Requirements 5.5, 5.7**
        """
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        from PIL import Image as PILImage

        from services.mcp_servers.art_gallery.server import (
            Job,
            _generate_image_background,
            _jobs,
            _jobs_lock,
        )

        # Create a test image with the random dimensions
        img = PILImage.new("RGB", (width, height), color="green")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        # Seed the job
        now = datetime.now(UTC).isoformat()
        with _jobs_lock:
            _jobs[job_id] = Job(
                job_id=job_id,
                status="generating",
                prompt="A koala",
                created_at=now,
            )

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.side_effect = lambda **_kwargs: {
            "body": io.BytesIO(json.dumps({"images": [base64.b64encode(png_bytes).decode()]}).encode()),
        }

        mock_s3 = MagicMock()
        cf_domain = "d123.cloudfront.net"

        with (
            patch(
                "services.mcp_servers.art_gallery.server._get_bedrock_runtime_client",
                return_value=mock_bedrock,
            ),
            patch(
                "services.mcp_servers.art_gallery.server._get_s3_client",
                return_value=mock_s3,
            ),
            patch(
                "services.mcp_servers.art_gallery.server._S3_BUCKET_NAME",
                "test-bucket",
            ),
            patch(
                "services.mcp_servers.art_gallery.server._CLOUDFRONT_DOMAIN",
                cf_domain,
            ),
        ):
            _generate_image_background(job_id, "Generate: A koala", "outback")

        # Verify thumbnail S3 key pattern
        assert mock_s3.put_object.call_count == 2, (
            f"Expected 2 S3 put_object calls, got {mock_s3.put_object.call_count}"
        )

        thumb_call = mock_s3.put_object.call_args_list[1]
        expected_thumb_key = f"ArtGallery/{job_id}_thumb.png"
        assert thumb_call.kwargs["Key"] == expected_thumb_key, (
            f"Expected thumb key '{expected_thumb_key}', got '{thumb_call.kwargs['Key']}'"
        )

        # Verify thumbnail dimensions are at most 200x200
        thumb_bytes = thumb_call.kwargs["Body"]
        thumb_img = PILImage.open(io.BytesIO(thumb_bytes))
        assert thumb_img.size[0] <= 200, f"Thumbnail width {thumb_img.size[0]} exceeds 200"
        assert thumb_img.size[1] <= 200, f"Thumbnail height {thumb_img.size[1]} exceeds 200"

        # Verify CloudFront URL pattern for the completed job
        with _jobs_lock:
            job = _jobs[job_id]
        assert job.status == "completed"
        expected_cf_url = f"https://{cf_domain}/ArtGallery/{job_id}.png"
        assert job.cloudfront_url == expected_cf_url, (
            f"Expected CloudFront URL '{expected_cf_url}', got '{job.cloudfront_url}'"
        )

        # Cleanup
        with _jobs_lock:
            _jobs.pop(job_id, None)


# ===================================================================
# Property 8: Gallery listing returns complete entries
# ===================================================================
class TestProperty8GalleryListingReturnsCompleteEntries:
    """Feature: art-gallery, Property 8: Gallery listing completeness."""

    @settings(max_examples=100, database=None, deadline=None)
    @given(
        job_ids=st.lists(
            st.uuids().map(str),
            min_size=0,
            max_size=8,
            unique=True,
        ),
        prompts=st.lists(
            st.text(
                alphabet=st.characters(
                    codec="ascii",
                    whitelist_categories=("L", "N", "Zs"),
                    min_codepoint=32,
                    max_codepoint=126,
                ),
                min_size=1,
                max_size=80,
            ),
            min_size=8,
            max_size=8,
        ),
        timestamps=st.lists(
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2030, 1, 1),
            ).map(lambda dt: dt.isoformat()),
            min_size=8,
            max_size=8,
        ),
    )
    def test_list_gallery_images_returns_one_entry_per_full_size_image(
        self,
        job_ids: list[str],
        prompts: list[str],
        timestamps: list[str],
    ) -> None:
        """Feature: art-gallery, Property 8: Gallery listing completeness.

        For any set of images stored in S3 under the ArtGallery/ prefix,
        list_gallery_images SHALL return one entry per full-size image
        (excluding thumbnails), and each entry SHALL contain s3_key, prompt,
        timestamp, thumbnail_url, and full_url.

        **Validates: Requirements 4.2**
        """
        from unittest.mock import patch

        import boto3
        from moto import mock_aws

        from services.mcp_servers.art_gallery.server import list_gallery_images

        bucket_name = "test-gallery-bucket"
        cf_domain = "d123test.cloudfront.net"

        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket=bucket_name)

            # Upload full-size images and their thumbnails
            for i, job_id in enumerate(job_ids):
                prompt = prompts[i]
                ts = timestamps[i]
                full_key = f"ArtGallery/{job_id}.png"
                thumb_key = f"ArtGallery/{job_id}_thumb.png"

                metadata = {
                    "x-amz-meta-prompt": prompt,
                    "x-amz-meta-timestamp": ts,
                }

                # Upload full-size image
                s3.put_object(
                    Bucket=bucket_name,
                    Key=full_key,
                    Body=b"fake-png-data",
                    ContentType="image/png",
                    Metadata=metadata,
                )
                # Upload thumbnail
                s3.put_object(
                    Bucket=bucket_name,
                    Key=thumb_key,
                    Body=b"fake-thumb-data",
                    ContentType="image/png",
                    Metadata=metadata,
                )

            # Patch the server to use our mocked S3
            with (
                patch(
                    "services.mcp_servers.art_gallery.server._get_s3_client",
                    return_value=s3,
                ),
                patch(
                    "services.mcp_servers.art_gallery.server._S3_BUCKET_NAME",
                    bucket_name,
                ),
                patch(
                    "services.mcp_servers.art_gallery.server._CLOUDFRONT_DOMAIN",
                    cf_domain,
                ),
            ):
                result = list_gallery_images()

            # --- Assertions ---

            if len(job_ids) == 0:
                # Empty gallery case
                assert result["images"] == [], f"Expected empty images list, got {result['images']}"
                assert result["count"] == 0, f"Expected count 0, got {result['count']}"
                return

            assert "images" in result, f"Missing 'images' key in result: {result}"
            assert "count" in result, f"Missing 'count' key in result: {result}"

            images = result["images"]

            # One entry per full-size image
            assert len(images) == len(job_ids), f"Expected {len(job_ids)} entries, got {len(images)}"
            assert result["count"] == len(job_ids), f"Expected count {len(job_ids)}, got {result['count']}"

            # Build a lookup for verification
            entry_by_key = {img["s3_key"]: img for img in images}

            required_fields = {"s3_key", "prompt", "timestamp", "thumbnail_url", "full_url"}

            for i, job_id in enumerate(job_ids):
                full_key = f"ArtGallery/{job_id}.png"
                assert full_key in entry_by_key, f"Missing entry for full-size key {full_key}"

                entry = entry_by_key[full_key]

                # Each entry must contain all 5 required fields
                missing = required_fields - set(entry.keys())
                assert not missing, f"Entry for {full_key} missing fields: {missing}"

                # Verify field values
                assert entry["prompt"] == prompts[i], f"Expected prompt {prompts[i]!r}, got {entry['prompt']!r}"
                assert entry["timestamp"] == timestamps[i], (
                    f"Expected timestamp {timestamps[i]!r}, got {entry['timestamp']!r}"
                )

                expected_thumb_url = f"https://{cf_domain}/ArtGallery/{job_id}_thumb.png"
                assert entry["thumbnail_url"] == expected_thumb_url, (
                    f"Expected thumbnail_url {expected_thumb_url!r}, got {entry['thumbnail_url']!r}"
                )

                expected_full_url = f"https://{cf_domain}/{full_key}"
                assert entry["full_url"] == expected_full_url, (
                    f"Expected full_url {expected_full_url!r}, got {entry['full_url']!r}"
                )

                # Thumbnails must NOT appear as entries
                thumb_key = f"ArtGallery/{job_id}_thumb.png"
                assert thumb_key not in entry_by_key, f"Thumbnail key {thumb_key} should not appear as an entry"

# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for the Art Gallery MCP server _generate_image_background function.

Tests services/mcp_servers/art_gallery/server.py background image generation
with mocked Bedrock and S3 clients.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.mcp_servers.art_gallery.server import (
    Job,
    _generate_image_background,
    _jobs,
    _jobs_lock,
)


def _create_test_png_bytes() -> bytes:
    """Create a small valid PNG image and return its raw bytes."""
    img = Image.new("RGB", (64, 64), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mock_bedrock_response(png_bytes: bytes) -> dict:
    """Create a mock Bedrock response with base64 image in JSON."""
    import base64
    import json

    img_b64 = base64.b64encode(png_bytes).decode("utf-8")
    body = json.dumps({"images": [img_b64]})
    return {"body": io.BytesIO(body.encode())}


def _seed_job(job_id: str, prompt: str = "A koala") -> None:
    """Insert a generating job into the in-memory store."""
    with _jobs_lock:
        _jobs[job_id] = Job(
            job_id=job_id,
            status="generating",
            prompt=prompt,
            created_at="2025-07-15T10:00:00+00:00",
        )


def _clear_jobs() -> None:
    with _jobs_lock:
        _jobs.clear()


class TestBackgroundSuccess:
    """Successful end-to-end background generation."""

    def setup_method(self) -> None:
        _clear_jobs()

    @patch("services.mcp_servers.art_gallery.server._get_s3_client")
    @patch("services.mcp_servers.art_gallery.server._get_bedrock_runtime_client")
    @patch("services.mcp_servers.art_gallery.server._S3_BUCKET_NAME", "test-bucket")
    @patch("services.mcp_servers.art_gallery.server._CLOUDFRONT_DOMAIN", "d123.cloudfront.net")
    def test_successful_generation(self, mock_bedrock_fn, mock_s3_fn) -> None:
        job_id = "test-job-001"
        _seed_job(job_id, prompt="A koala in a tree")

        bedrock = MagicMock()
        mock_bedrock_fn.return_value = bedrock
        bedrock.invoke_model.return_value = _mock_bedrock_response(_create_test_png_bytes())

        s3 = MagicMock()
        mock_s3_fn.return_value = s3

        _generate_image_background(job_id, "Generate a realistic image: A koala in a tree", "outback")

        with _jobs_lock:
            job = _jobs[job_id]
        assert job.status == "completed"
        assert job.s3_key == f"ArtGallery/{job_id}.png"
        assert job.cloudfront_url == f"https://d123.cloudfront.net/ArtGallery/{job_id}.png"
        assert job.error is None

        assert s3.put_object.call_count == 2
        calls = s3.put_object.call_args_list

        full_call = calls[0]
        assert full_call.kwargs["Bucket"] == "test-bucket"
        assert full_call.kwargs["Key"] == f"ArtGallery/{job_id}.png"
        assert full_call.kwargs["ContentType"] == "image/png"
        assert full_call.kwargs["Metadata"]["x-amz-meta-prompt"] == "A koala in a tree"
        assert full_call.kwargs["Metadata"]["x-amz-meta-timestamp"] == "2025-07-15T10:00:00+00:00"

        thumb_call = calls[1]
        assert thumb_call.kwargs["Key"] == f"ArtGallery/{job_id}_thumb.png"
        assert thumb_call.kwargs["ContentType"] == "image/png"

    @patch("services.mcp_servers.art_gallery.server._get_s3_client")
    @patch("services.mcp_servers.art_gallery.server._get_bedrock_runtime_client")
    @patch("services.mcp_servers.art_gallery.server._S3_BUCKET_NAME", "test-bucket")
    @patch("services.mcp_servers.art_gallery.server._CLOUDFRONT_DOMAIN", "d123.cloudfront.net")
    def test_thumbnail_is_200x200(self, mock_bedrock_fn, mock_s3_fn) -> None:
        job_id = "test-job-thumb"
        _seed_job(job_id)

        bedrock = MagicMock()
        mock_bedrock_fn.return_value = bedrock
        bedrock.invoke_model.return_value = _mock_bedrock_response(_create_test_png_bytes())

        s3 = MagicMock()
        mock_s3_fn.return_value = s3

        _generate_image_background(job_id, "Generate: A koala", "outback")

        thumb_bytes = s3.put_object.call_args_list[1].kwargs["Body"]
        thumb_img = Image.open(io.BytesIO(thumb_bytes))
        assert thumb_img.size[0] <= 200
        assert thumb_img.size[1] <= 200


class TestBackgroundBedrockFailure:
    """Bedrock invocation failures."""

    def setup_method(self) -> None:
        _clear_jobs()

    @patch("services.mcp_servers.art_gallery.server._get_bedrock_runtime_client")
    def test_bedrock_exception_sets_failed(self, mock_bedrock_fn) -> None:
        job_id = "test-job-bedrock-fail"
        _seed_job(job_id)

        bedrock = MagicMock()
        mock_bedrock_fn.return_value = bedrock
        bedrock.invoke_model.side_effect = RuntimeError("Bedrock unavailable")

        _generate_image_background(job_id, "Generate: A koala", "outback")

        with _jobs_lock:
            job = _jobs[job_id]
        assert job.status == "failed"
        assert "Bedrock unavailable" in job.error

    @patch("services.mcp_servers.art_gallery.server._get_bedrock_runtime_client")
    def test_empty_images_sets_failed(self, mock_bedrock_fn) -> None:
        job_id = "test-job-empty"
        _seed_job(job_id)

        bedrock = MagicMock()
        mock_bedrock_fn.return_value = bedrock
        # Return JSON with empty images array to simulate no output
        bedrock.invoke_model.return_value = {
            "body": io.BytesIO(b'{"images": []}'),
        }

        _generate_image_background(job_id, "Generate: A koala", "outback")

        with _jobs_lock:
            job = _jobs[job_id]
        assert job.status == "failed"
        assert job.error == "Image generation produced no output."


class TestBackgroundS3Failure:
    """S3 upload failures."""

    def setup_method(self) -> None:
        _clear_jobs()

    @patch("services.mcp_servers.art_gallery.server._get_s3_client")
    @patch("services.mcp_servers.art_gallery.server._get_bedrock_runtime_client")
    @patch("services.mcp_servers.art_gallery.server._S3_BUCKET_NAME", "test-bucket")
    def test_s3_upload_failure_sets_failed(self, mock_bedrock_fn, mock_s3_fn) -> None:
        job_id = "test-job-s3-fail"
        _seed_job(job_id)

        bedrock = MagicMock()
        mock_bedrock_fn.return_value = bedrock
        bedrock.invoke_model.return_value = _mock_bedrock_response(_create_test_png_bytes())

        s3 = MagicMock()
        mock_s3_fn.return_value = s3
        s3.put_object.side_effect = RuntimeError("S3 error")

        _generate_image_background(job_id, "Generate: A koala", "outback")

        with _jobs_lock:
            job = _jobs[job_id]
        assert job.status == "failed"
        assert job.error == "Failed to store image"


class TestBackgroundThumbnailFailure:
    """Pillow thumbnail generation failures."""

    def setup_method(self) -> None:
        _clear_jobs()

    @patch("services.mcp_servers.art_gallery.server.Image.open")
    @patch("services.mcp_servers.art_gallery.server._get_bedrock_runtime_client")
    def test_pillow_failure_sets_failed(self, mock_bedrock_fn, mock_pil_open) -> None:
        job_id = "test-job-thumb-fail"
        _seed_job(job_id)

        bedrock = MagicMock()
        mock_bedrock_fn.return_value = bedrock
        bedrock.invoke_model.return_value = _mock_bedrock_response(_create_test_png_bytes())

        mock_pil_open.side_effect = OSError("Corrupt image data")

        _generate_image_background(job_id, "Generate: A koala", "outback")

        with _jobs_lock:
            job = _jobs[job_id]
        assert job.status == "failed"
        assert job.error == "Thumbnail generation failed"

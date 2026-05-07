# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for the Art Gallery MCP server generate_image tool.

Tests services/mcp_servers/art_gallery/server.py generate_image function
with concrete fixtures. Complements the property-based tests in
test_properties_art_gallery.py (tasks 1.6–1.10).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

# Ensure project root is on sys.path so services/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.mcp_servers.art_gallery.server import (
    SYSTEM_PROMPT_PREFIX,
    Job,
    _jobs,
    _jobs_lock,
    generate_image,
    get_job_status,
    list_gallery_images,
)


def _clear_jobs() -> None:
    """Remove all jobs from the in-memory store between tests."""
    with _jobs_lock:
        _jobs.clear()


class TestGenerateImageValidation:
    """Content validation and prompt length checks."""

    def setup_method(self) -> None:
        _clear_jobs()

    def test_rejects_prompt_without_allowed_topic(self) -> None:
        result = generate_image("a picture of a car")
        assert result["error"] == "content_validation_failed"
        assert "Australian wildlife or nature" in result["message"]

    def test_rejects_empty_prompt(self) -> None:
        result = generate_image("")
        assert result["error"] == "content_validation_failed"

    def test_rejects_prompt_too_long(self) -> None:
        # Build a prompt that exceeds 512 chars after prefix
        max_user_len = 512 - len(SYSTEM_PROMPT_PREFIX)
        long_prompt = "koala " + "x" * max_user_len
        result = generate_image(long_prompt)
        assert result["error"] == "prompt_too_long"
        assert "512 characters" in result["message"]

    def test_accepts_prompt_exactly_at_limit(self) -> None:
        max_user_len = 512 - len(SYSTEM_PROMPT_PREFIX)
        # "koala" is 5 chars, pad the rest
        prompt = "koala" + "a" * (max_user_len - 5)
        result = generate_image(prompt)
        assert "job_id" in result
        assert result["status"] == "generating"


class TestGenerateImageSuccess:
    """Successful generation flow."""

    def setup_method(self) -> None:
        _clear_jobs()

    def test_returns_job_id_and_generating_status(self) -> None:
        result = generate_image("A koala in a eucalyptus tree")
        assert "job_id" in result
        assert result["status"] == "generating"

    def test_job_stored_in_memory(self) -> None:
        result = generate_image("A kangaroo at sunset")
        job_id = result["job_id"]
        with _jobs_lock:
            assert job_id in _jobs
            job = _jobs[job_id]
        assert job.status == "generating"
        assert job.prompt == "A kangaroo at sunset"
        assert job.created_at is not None

    def test_unique_job_ids(self) -> None:
        ids = set()
        for _ in range(10):
            result = generate_image("A wombat in the bush")
            ids.add(result["job_id"])
        assert len(ids) == 10

    @patch("services.mcp_servers.art_gallery.server._generate_image_background")
    def test_background_thread_spawned(self, mock_bg) -> None:
        result = generate_image("A platypus swimming")
        # Give the thread a moment to start
        time.sleep(0.1)
        mock_bg.assert_called_once()
        args = mock_bg.call_args[0]
        assert args[0] == result["job_id"]
        assert args[1].startswith(SYSTEM_PROMPT_PREFIX)

    def test_case_insensitive_validation(self) -> None:
        result = generate_image("A KOALA in the OUTBACK")
        assert "job_id" in result
        assert result["status"] == "generating"


class TestGetJobStatus:
    """Tests for the get_job_status tool."""

    def setup_method(self) -> None:
        _clear_jobs()

    def test_not_found_returns_error(self) -> None:
        result = get_job_status("nonexistent-id")
        assert result["error"] == "job_not_found"
        assert "nonexistent-id" in result["message"]

    def test_generating_status(self) -> None:
        job = Job(
            job_id="gen-1",
            status="generating",
            prompt="A koala",
            created_at="2025-01-01T00:00:00+00:00",
        )
        with _jobs_lock:
            _jobs["gen-1"] = job

        result = get_job_status("gen-1")
        assert result == {"job_id": "gen-1", "status": "generating"}

    def test_completed_status(self) -> None:
        job = Job(
            job_id="done-1",
            status="completed",
            prompt="A kangaroo",
            created_at="2025-01-01T00:00:00+00:00",
            s3_key="ArtGallery/done-1.png",
            cloudfront_url="https://example.com/ArtGallery/done-1.png",
        )
        with _jobs_lock:
            _jobs["done-1"] = job

        result = get_job_status("done-1")
        assert result == {
            "job_id": "done-1",
            "status": "completed",
            "s3_key": "ArtGallery/done-1.png",
            "cloudfront_url": "https://example.com/ArtGallery/done-1.png",
        }

    def test_failed_status(self) -> None:
        job = Job(
            job_id="fail-1",
            status="failed",
            prompt="A wombat",
            created_at="2025-01-01T00:00:00+00:00",
            error="Bedrock timeout",
        )
        with _jobs_lock:
            _jobs["fail-1"] = job

        result = get_job_status("fail-1")
        assert result == {
            "job_id": "fail-1",
            "status": "failed",
            "error": "Bedrock timeout",
        }

    def test_completed_does_not_include_error(self) -> None:
        job = Job(
            job_id="c-1",
            status="completed",
            prompt="A platypus",
            created_at="2025-01-01T00:00:00+00:00",
            s3_key="ArtGallery/c-1.png",
            cloudfront_url="https://example.com/ArtGallery/c-1.png",
        )
        with _jobs_lock:
            _jobs["c-1"] = job

        result = get_job_status("c-1")
        assert "error" not in result

    def test_failed_does_not_include_s3_key(self) -> None:
        job = Job(
            job_id="f-1",
            status="failed",
            prompt="A wombat",
            created_at="2025-01-01T00:00:00+00:00",
            error="Some error",
        )
        with _jobs_lock:
            _jobs["f-1"] = job

        result = get_job_status("f-1")
        assert "s3_key" not in result
        assert "cloudfront_url" not in result


class TestListGalleryImages:
    """Tests for the list_gallery_images tool."""

    @patch("services.mcp_servers.art_gallery.server._get_s3_client")
    def test_empty_gallery_returns_empty_list(self, mock_get_s3):
        mock_s3 = mock_get_s3.return_value
        mock_s3.list_objects_v2.return_value = {}

        result = list_gallery_images()
        assert result == {"images": [], "count": 0}

    @patch("services.mcp_servers.art_gallery.server._get_s3_client")
    def test_filters_out_thumbnails(self, mock_get_s3):
        mock_s3 = mock_get_s3.return_value
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "ArtGallery/abc.png"},
                {"Key": "ArtGallery/abc_thumb.png"},
            ]
        }
        mock_s3.head_object.return_value = {
            "Metadata": {
                "x-amz-meta-prompt": "A koala",
                "x-amz-meta-timestamp": "2025-07-15T10:30:00Z",
            }
        }

        result = list_gallery_images()
        assert result["count"] == 1
        assert result["images"][0]["s3_key"] == "ArtGallery/abc.png"

    @patch("services.mcp_servers.art_gallery.server._get_s3_client")
    def test_returns_correct_entry_fields(self, mock_get_s3):
        mock_s3 = mock_get_s3.return_value
        mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "ArtGallery/img1.png"}]}
        mock_s3.head_object.return_value = {
            "Metadata": {
                "x-amz-meta-prompt": "A wombat",
                "x-amz-meta-timestamp": "2025-01-01T00:00:00Z",
            }
        }

        result = list_gallery_images()
        entry = result["images"][0]
        assert entry["s3_key"] == "ArtGallery/img1.png"
        assert entry["prompt"] == "A wombat"
        assert entry["timestamp"] == "2025-01-01T00:00:00Z"
        assert "img1_thumb.png" in entry["thumbnail_url"]
        assert "img1.png" in entry["full_url"]

    @patch("services.mcp_servers.art_gallery.server._get_s3_client")
    def test_s3_error_returns_gallery_unavailable(self, mock_get_s3):
        mock_s3 = mock_get_s3.return_value
        mock_s3.list_objects_v2.side_effect = Exception("S3 down")

        result = list_gallery_images()
        assert result["error"] == "gallery_unavailable"
        assert result["message"] == "Unable to retrieve gallery images."

    @patch("services.mcp_servers.art_gallery.server._get_s3_client")
    def test_multiple_images_returned(self, mock_get_s3):
        mock_s3 = mock_get_s3.return_value
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "ArtGallery/a.png"},
                {"Key": "ArtGallery/a_thumb.png"},
                {"Key": "ArtGallery/b.png"},
                {"Key": "ArtGallery/b_thumb.png"},
            ]
        }
        mock_s3.head_object.return_value = {
            "Metadata": {
                "x-amz-meta-prompt": "test",
                "x-amz-meta-timestamp": "2025-01-01T00:00:00Z",
            }
        }

        result = list_gallery_images()
        assert result["count"] == 2
        keys = [img["s3_key"] for img in result["images"]]
        assert "ArtGallery/a.png" in keys
        assert "ArtGallery/b.png" in keys

    @patch("services.mcp_servers.art_gallery.server._get_s3_client")
    def test_head_object_failure_skips_entry(self, mock_get_s3):
        mock_s3 = mock_get_s3.return_value
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "ArtGallery/good.png"},
                {"Key": "ArtGallery/bad.png"},
            ]
        }
        mock_s3.head_object.side_effect = [
            {
                "Metadata": {
                    "x-amz-meta-prompt": "A koala",
                    "x-amz-meta-timestamp": "2025-01-01T00:00:00Z",
                }
            },
            Exception("head_object failed"),
        ]

        result = list_gallery_images()
        assert result["count"] == 1
        assert result["images"][0]["s3_key"] == "ArtGallery/good.png"

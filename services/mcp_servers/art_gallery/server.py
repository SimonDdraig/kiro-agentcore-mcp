# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Art Gallery MCP server — AI image generation of Australian wildlife and nature."""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from mcp.server.fastmcp import FastMCP
from PIL import Image

try:
    from logging_config import setup_logging
except ModuleNotFoundError:
    from services.shared.logging_config import setup_logging

# ---------------------------------------------------------------------------
# AgentCore Runtime app + MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP("art-gallery", host="0.0.0.0", stateless_http=True)

setup_logging()
logger = logging.getLogger(__name__)

# Force immediate flush on all log output so nothing is lost
for handler in logging.getLogger().handlers:
    if hasattr(handler, "stream"):
        handler.stream = sys.stderr

logger.info("Art Gallery MCP server module loaded")
logger.info(
    "Startup config: AWS_REGION=%s, S3_BUCKET_NAME=%s, CLOUDFRONT_DOMAIN=%s",
    os.environ.get("AWS_REGION", "(not set)"),
    os.environ.get("S3_BUCKET_NAME", "(not set)"),
    os.environ.get("CLOUDFRONT_DOMAIN", "(not set)"),
)

# ---------------------------------------------------------------------------
# AWS clients and configuration
# ---------------------------------------------------------------------------

_AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
_S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "")
_CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN", "")


def _get_bedrock_runtime_client() -> Any:
    """Return a boto3 Bedrock Runtime client."""
    return boto3.client("bedrock-runtime", region_name=_AWS_REGION)


def _get_s3_client() -> Any:
    """Return a boto3 S3 client."""
    return boto3.client("s3", region_name=_AWS_REGION)


# ---------------------------------------------------------------------------
# Content Validator
# ---------------------------------------------------------------------------

ALLOWED_TOPICS = [
    "kangaroo",
    "koala",
    "wombat",
    "platypus",
    "echidna",
    "emu",
    "kookaburra",
    "cockatoo",
    "quokka",
    "bilby",
    "numbat",
    "cassowary",
    "crocodile",
    "dugong",
    "possum",
    "glider",
    "wallaby",
    "quoll",
    "devil",
    "parrot",
    "eagle",
    "turtle",
    "tortoise",
    "honeyeater",
    "australian",
    "outback",
    "bush",
    "reef",
    "eucalyptus",
    "rainforest",
    "desert",
    "wetland",
    "mangrove",
    "national park",
    "wildlife",
    "nature",
    "landscape",
    "marine",
    "coral",
    "banksia",
    "wattle",
    "gum tree",
    "fern",
    "wildflower",
]

SYSTEM_PROMPT_PREFIX = "Generate a realistic image of Australian wildlife or nature: "


class ContentValidator:
    """Validates prompts against allowed Australian wildlife and nature topics."""

    def validate(self, prompt: str) -> bool:
        """Check if the prompt contains at least one allowed topic keyword.

        Args:
            prompt: The user-submitted prompt text.

        Returns:
            True if the lowercased prompt contains at least one allowed keyword.
        """
        lowered = prompt.lower()
        return any(topic in lowered for topic in ALLOWED_TOPICS)

    def build_full_prompt(self, prompt: str) -> str:
        """Prepend the system prompt prefix and enforce 512-char max.

        Args:
            prompt: The validated user prompt.

        Returns:
            The full prompt string (prefix + user prompt), truncated to 512 chars.
        """
        full = SYSTEM_PROMPT_PREFIX + prompt
        return full[:512]


# ---------------------------------------------------------------------------
# Job dataclass and in-memory store
# ---------------------------------------------------------------------------


@dataclass
class Job:
    """Represents a single image generation request."""

    job_id: str
    status: str  # "generating" | "completed" | "failed"
    prompt: str
    created_at: str  # ISO 8601
    s3_key: str | None = None
    cloudfront_url: str | None = None
    error: str | None = None


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()

_content_validator = ContentValidator()

# Load style guide images at module level (base64 for JSON payload)
_STYLE_DIR = Path(__file__).resolve().parent
_STYLE_IMAGES: dict[str, str] = {}
_DEFAULT_STYLE = "outback"

for _style_name in ("outback", "bush", "night", "beach", "river", "billabong", "city", "town"):
    _style_path = _STYLE_DIR / f"image_style_{_style_name}.jpg"
    try:
        with open(_style_path, "rb") as _f:
            _STYLE_IMAGES[_style_name] = base64.b64encode(_f.read()).decode("utf-8")
        logger.info("Loaded style image: %s (%d chars b64)", _style_path.name, len(_STYLE_IMAGES[_style_name]))
    except Exception as _exc:
        logger.error("Failed to load style image %s: %s", _style_path, _exc)


# ---------------------------------------------------------------------------
# Background image generation (placeholder — fully implemented in task 1.3)
# ---------------------------------------------------------------------------


def _update_job_status(job_id: str, status: str, **fields: str | None) -> None:
    """Safely update a job's status and optional fields. No-op if job was removed."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            logger.warning("Job %s no longer in store, skipping status update to %s", job_id, status)
            return
        job.status = status
        for key, value in fields.items():
            setattr(job, key, value)


def _generate_image_background(job_id: str, full_prompt: str, style: str) -> None:
    """Run in background thread: invoke Bedrock, create thumbnail, upload to S3.

    Args:
        job_id: The unique job identifier.
        full_prompt: The full prompt string (system prefix + user prompt).
        style: The style guide image key ("outback", "bush", or "night").
    """
    logger.info("[background] Started for job %s (style=%s)", job_id, style)
    logger.info("[background] Full prompt: %s", full_prompt[:200])

    try:
        # --- Invoke Stability AI Stable Image Style Guide ---
        logger.info("[background] Creating Bedrock client for region %s", _AWS_REGION)
        bedrock = _get_bedrock_runtime_client()

        seed = int(uuid.uuid4().int % 4294967295)
        # Build payload dict and serialize — use __import__ to avoid NameError in daemon threads
        logger.info("[background] Style image b64 length: %d", len(_STYLE_IMAGES.get(style, "")))
        style_b64 = _STYLE_IMAGES.get(style, "")
        if not style_b64:
            logger.error("[background] Style image '%s' NOT LOADED!", style)
            _update_job_status(job_id, "failed", error=f"Style guide image '{style}' not loaded")
            return
        params = {
            "image": style_b64,
            "prompt": full_prompt,
            "output_format": "png",
            "seed": seed,
        }
        request = json.dumps(params)

        # https://platform.stability.ai/docs/api-reference#tag/Control/paths/~1v2beta~1stable-image~1control~1style/post
        _model_id = "us.stability.stable-image-style-guide-v1:0"
        try:
            logger.info(
                "[background] Invoking model=%s for job %s, payload_size=%d, style=%s",
                _model_id,
                job_id,
                len(request),
                style,
            )
            response = bedrock.invoke_model(
                modelId=_model_id,
                body=request,
            )
        except Exception as exc:
            logger.error("[background] Bedrock InvokeModel FAILED model=%s job=%s: %s", _model_id, job_id, exc)
            _update_job_status(job_id, "failed", error=str(exc))
            return

        # --- Decode response ---
        logger.info("[background] Bedrock returned response for job %s, decoding", job_id)
        raw_body = response["body"].read()

        response_body = json.loads(raw_body)
        images = response_body.get("images", [])
        if not images:
            logger.error("[background] No images in Bedrock response for job %s", job_id)
            _update_job_status(job_id, "failed", error="Image generation produced no output.")
            return
        image_bytes = base64.b64decode(images[0])
        logger.info("[background] Decoded image for job %s, size=%d bytes", job_id, len(image_bytes))

        # --- Generate 200×200 thumbnail with Pillow ---
        logger.info("[background] Generating thumbnail for job %s", job_id)
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.thumbnail((200, 200))
            thumb_buffer = io.BytesIO()
            img.save(thumb_buffer, format="PNG")
            thumb_bytes = thumb_buffer.getvalue()
        except Exception as exc:
            logger.error("[background] Thumbnail generation FAILED for job %s: %s", job_id, exc)
            _update_job_status(job_id, "failed", error="Thumbnail generation failed")
            return

        # --- Upload to S3 ---
        s3_key = f"ArtGallery/{job_id}.png"
        thumb_key = f"ArtGallery/{job_id}_thumb.png"
        logger.info("[background] Uploading to S3 bucket=%s, key=%s", _S3_BUCKET_NAME or "(empty)", s3_key)

        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is None:
                logger.warning("Job %s removed before S3 upload, aborting", job_id)
                return
            original_prompt = job.prompt
            created_at = job.created_at

        metadata = {
            "x-amz-meta-prompt": original_prompt,
            "x-amz-meta-timestamp": created_at,
        }

        s3 = _get_s3_client()
        try:
            s3.put_object(
                Bucket=_S3_BUCKET_NAME,
                Key=s3_key,
                Body=image_bytes,
                ContentType="image/png",
                Metadata=metadata,
            )
            s3.put_object(
                Bucket=_S3_BUCKET_NAME,
                Key=thumb_key,
                Body=thumb_bytes,
                ContentType="image/png",
                Metadata=metadata,
            )
        except Exception as exc:
            logger.error("[background] S3 upload FAILED for job %s: %s", job_id, exc)
            _update_job_status(job_id, "failed", error="Failed to store image")
            return

        # --- Update job to completed ---
        cloudfront_url = f"https://{_CLOUDFRONT_DOMAIN}/{s3_key}"
        _update_job_status(job_id, "completed", s3_key=s3_key, cloudfront_url=cloudfront_url)

        logger.info("[background] Job %s COMPLETED: s3_key=%s, url=%s", job_id, s3_key, cloudfront_url)

    except Exception as exc:
        logger.error("[background] UNEXPECTED error for job %s: %s", job_id, exc, exc_info=True)
        _update_job_status(job_id, "failed", error=str(exc))


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def generate_image(prompt: str, style: str = "outback") -> dict[str, Any]:
    """Generate an AI image of Australian wildlife or nature.

    Validates the prompt against allowed topics, then spawns a background
    thread to invoke Stability AI Stable Image Style Guide and upload the result to S3.
    Returns immediately with a job ID that can be polled via get_job_status.

    Args:
        prompt: A text description of the desired image. Must relate to
            Australian wildlife or nature.
        style: The style guide image to use. One of: "outback" (desert/arid
            landscapes), "bush" (rainforest/dense vegetation), "night"
            (nocturnal scenes/starry skies), "beach" (coastal/ocean scenes),
            "river" (rivers/streams/waterways), "billabong" (still water/
            wetland pools), "city" (urban/city scenes), "town" (rural towns/
            small settlements). Defaults to "outback".

    Returns:
        A dict with ``job_id`` and ``status`` on success, or an ``error``
        dict if validation fails.
    """
    logger.info("[generate_image] CALLED with prompt: %s, style: %s", prompt[:100], style)

    # --- Content validation ---
    if not _content_validator.validate(prompt):
        logger.warning("[generate_image] Content validation REJECTED prompt: %s", prompt[:100])
        return {
            "error": "content_validation_failed",
            "message": (
                "Prompt must relate to Australian wildlife or nature. "
                "Allowed topics include: Australian animals, plants, "
                "landscapes, national parks, marine life."
            ),
        }

    # --- Build full prompt and check length ---
    full_prompt = SYSTEM_PROMPT_PREFIX + prompt
    if len(full_prompt) > 512:
        logger.warning("[generate_image] Prompt too long (%d chars): %s", len(full_prompt), prompt[:100])
        return {
            "error": "prompt_too_long",
            "message": ("Prompt exceeds maximum length of 512 characters (including system prefix)."),
        }

    # --- Validate style ---
    resolved_style = style if style in _STYLE_IMAGES else _DEFAULT_STYLE
    if style not in _STYLE_IMAGES:
        logger.warning("[generate_image] Unknown style '%s', falling back to '%s'", style, _DEFAULT_STYLE)

    # --- Create job ---
    job_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    job = Job(job_id=job_id, status="generating", prompt=prompt, created_at=now)

    with _jobs_lock:
        _jobs[job_id] = job

    logger.info("[generate_image] Job %s created (style=%s), spawning background thread", job_id, resolved_style)
    logger.info(
        "[generate_image] Config: S3_BUCKET_NAME=%s, CLOUDFRONT_DOMAIN=%s, AWS_REGION=%s",
        _S3_BUCKET_NAME or "(empty)",
        _CLOUDFRONT_DOMAIN or "(empty)",
        _AWS_REGION,
    )

    # --- Spawn background thread ---
    thread = threading.Thread(
        target=_generate_image_background,
        args=(job_id, full_prompt, resolved_style),
        daemon=True,
    )
    thread.start()

    logger.info("[generate_image] Background thread started for job %s, returning immediately", job_id)
    return {"job_id": job_id, "status": "generating"}


@mcp.tool()
def get_job_status(job_id: str) -> dict[str, Any]:
    """Check the status of an image generation job.

    Args:
        job_id: The unique identifier returned by ``generate_image``.

    Returns:
        A dict whose shape depends on the job's current status:
        - generating: ``{job_id, status}``
        - completed:  ``{job_id, status, s3_key, cloudfront_url}``
        - failed:     ``{job_id, status, error}``
        - not found:  ``{error, message}``
    """
    logger.info("[get_job_status] CALLED with job_id: %s", job_id)
    logger.info("[get_job_status] Current job store has %d jobs: %s", len(_jobs), list(_jobs.keys()))

    with _jobs_lock:
        job = _jobs.get(job_id)

    if job is None:
        logger.warning("[get_job_status] Job %s NOT FOUND in store", job_id)
        return {
            "error": "job_not_found",
            "message": f"No job found with ID: {job_id}",
        }

    with _jobs_lock:
        status = job.status
        logger.info("[get_job_status] Job %s has status: %s", job_id, status)
        if status == "completed":
            return {
                "job_id": job.job_id,
                "status": status,
                "s3_key": job.s3_key,
                "cloudfront_url": job.cloudfront_url,
            }
        if status == "failed":
            return {
                "job_id": job.job_id,
                "status": status,
                "error": job.error,
            }
        # "generating" or any other status
        return {
            "job_id": job.job_id,
            "status": status,
        }


@mcp.tool()
def list_gallery_images() -> dict[str, Any]:
    """List all previously generated images in the Art Gallery.

    Queries S3 for all images under the ``ArtGallery/`` prefix, filters out
    thumbnails, and returns metadata for each full-size image.

    Returns:
        A dict with ``images`` (list of gallery entries) and ``count``.
        Each entry contains ``s3_key``, ``prompt``, ``timestamp``,
        ``thumbnail_url``, and ``full_url``.
        Returns ``{error, message}`` if S3 is unavailable.
    """
    logger.info("[list_gallery_images] CALLED, bucket=%s", _S3_BUCKET_NAME or "(empty)")
    s3 = _get_s3_client()

    try:
        response = s3.list_objects_v2(Bucket=_S3_BUCKET_NAME, Prefix="ArtGallery/")
    except Exception as exc:
        logger.error("[list_gallery_images] S3 list_objects_v2 FAILED: %s", exc)
        return {
            "error": "gallery_unavailable",
            "message": "Unable to retrieve gallery images.",
        }

    contents = response.get("Contents", [])
    logger.info("[list_gallery_images] Found %d objects in S3", len(contents))

    # Filter to full-size images only (exclude thumbnails)
    full_size_keys = [obj["Key"] for obj in contents if not obj["Key"].endswith("_thumb.png")]

    if not full_size_keys:
        return {"images": [], "count": 0}

    images = []
    for s3_key in full_size_keys:
        try:
            head = s3.head_object(Bucket=_S3_BUCKET_NAME, Key=s3_key)
        except Exception as exc:
            logger.warning("Failed to read metadata for %s: %s", s3_key, exc)
            continue

        metadata = head.get("Metadata", {})
        prompt = metadata.get("x-amz-meta-prompt", "")
        timestamp = metadata.get("x-amz-meta-timestamp", "")

        # Build thumbnail key from full-size key (replace .png with _thumb.png)
        thumb_key = s3_key.replace(".png", "_thumb.png")

        images.append(
            {
                "s3_key": s3_key,
                "prompt": prompt,
                "timestamp": timestamp,
                "thumbnail_url": f"https://{_CLOUDFRONT_DOMAIN}/{thumb_key}",
                "full_url": f"https://{_CLOUDFRONT_DOMAIN}/{s3_key}",
            }
        )

    return {"images": images, "count": len(images)}


# ---------------------------------------------------------------------------
# Server entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http")

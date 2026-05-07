# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""API Gateway Lambda handler — lists gallery images directly from S3.

Bypasses the agent for fast gallery loading (sub-second vs 30s+ through the agent).
"""

import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
CLOUDFRONT_DOMAIN = os.environ["CLOUDFRONT_DOMAIN"]
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

s3 = boto3.client("s3")


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    """Handle GET /gallery — list all gallery images from S3."""
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Authorization,Content-Type",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
    }

    try:
        response = s3.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix="ArtGallery/")
        contents = response.get("Contents", [])

        # Filter to full-size images only (exclude thumbnails)
        full_keys = [obj["Key"] for obj in contents if not obj["Key"].endswith("_thumb.png")]

        if not full_keys:
            return {
                "statusCode": 200,
                "headers": headers,
                "body": json.dumps({"images": [], "count": 0}),
            }

        images = []
        for s3_key in full_keys:
            try:
                head = s3.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            except Exception:
                logger.warning("Failed to read metadata for %s", s3_key)
                continue

            metadata = head.get("Metadata", {})
            prompt = metadata.get("x-amz-meta-prompt", "")
            timestamp = metadata.get("x-amz-meta-timestamp", "")
            thumb_key = s3_key.replace(".png", "_thumb.png")

            images.append(
                {
                    "s3_key": s3_key,
                    "prompt": prompt,
                    "timestamp": timestamp,
                    "thumbnail_url": f"https://{CLOUDFRONT_DOMAIN}/{thumb_key}",
                    "full_url": f"https://{CLOUDFRONT_DOMAIN}/{s3_key}",
                }
            )

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"images": images, "count": len(images)}),
        }

    except Exception:
        logger.exception("Error listing gallery images")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Failed to load gallery"}),
        }

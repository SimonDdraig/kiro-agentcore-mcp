# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Shared logging configuration for AgentCore containers.

AgentCore captures stderr from containers into the -DEFAULT runtime-logs
CloudWatch log group. This module configures the root Python logger to
write to stderr so all logger.info/warning/error calls appear in those logs.
"""

from __future__ import annotations

import logging
import sys


def setup_logging() -> None:
    """Configure the root logger to write to stderr for AgentCore capture."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

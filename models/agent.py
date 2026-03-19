# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Shared models for agent invocation request and response."""

from dataclasses import dataclass


@dataclass
class InvokeRequest:
    """Agent invocation request from the frontend."""

    message: str


@dataclass
class InvokeResponse:
    """Agent invocation response returned to the frontend."""

    response: str
    request_id: str

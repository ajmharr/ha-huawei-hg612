"""Huawei HG612 modem statistics client."""

from .client import HuaweiHG612Client
from .exceptions import (
    AuthenticationError,
    ConnectionTimeoutError,
    HuaweiHG612Error,
    IncompleteResponseError,
    UnexpectedPromptError,
)
from .models import CommandResponse, DslStatistics, ResponseQuality
from .parser import detect_counter_resets, parse_xdsl_stats

__all__ = [
    "AuthenticationError",
    "CommandResponse",
    "ConnectionTimeoutError",
    "DslStatistics",
    "HuaweiHG612Client",
    "HuaweiHG612Error",
    "IncompleteResponseError",
    "ResponseQuality",
    "UnexpectedPromptError",
    "detect_counter_resets",
    "parse_xdsl_stats",
]


"""Exceptions raised by the Huawei HG612 client."""

from typing import Optional


class HuaweiHG612Error(Exception):
    """Base exception for HG612 communication failures."""


class ConnectionTimeoutError(HuaweiHG612Error):
    """A connection or prompt transition exceeded its timeout."""


class AuthenticationError(HuaweiHG612Error):
    """The modem rejected the supplied credentials."""


class UnexpectedPromptError(HuaweiHG612Error):
    """The modem presented a prompt that the client cannot safely answer."""


class IncompleteResponseError(HuaweiHG612Error):
    """The statistics command ended before the shell prompt returned."""

    def __init__(self, message: str, partial_output: Optional[str] = None) -> None:
        super().__init__(message)
        self.partial_output = partial_output or ""


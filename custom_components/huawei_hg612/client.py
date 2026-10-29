"""Asynchronous, prompt-aware Telnet client for the Huawei HG612."""

import asyncio
import inspect
import re
from typing import Any, Awaitable, Callable, Optional, Sequence, Tuple

from .exceptions import (
    AuthenticationError,
    ConnectionTimeoutError,
    IncompleteResponseError,
    UnexpectedPromptError,
)
from .models import CommandResponse, ResponseQuality

Connector = Callable[..., Awaitable[Tuple[Any, Any]]]

_USERNAME_PROMPT = re.compile(r"(?:^|[\r\n])\s*(?:login|user(?:name)?)\s*:\s*$", re.IGNORECASE)
_PASSWORD_PROMPT = re.compile(r"(?:^|[\r\n])\s*password\s*:\s*$", re.IGNORECASE)
_ATP_PROMPT = re.compile(r"(?:^|[\r\n])\s*ATP>\s*$", re.IGNORECASE)
_SHELL_PROMPT = re.compile(r"(?:^|[\r\n])[^\r\n]*#\s*$")
_AUTH_FAILURE = re.compile(
    r"(?:incorrect|invalid|authentication\s+fail|login\s+fail|access\s+denied)",
    re.IGNORECASE,
)
_GENERIC_PROMPT = re.compile(r"(?:^|[\r\n])\s*[^\r\n]{1,40}:\s*$")


class HuaweiHG612Client:
    """Retrieve DSL statistics through the modem's ATP and BusyBox prompts."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 23,
        connect_timeout: float = 10.0,
        prompt_timeout: float = 10.0,
        command_timeout: float = 20.0,
        connector: Optional[Connector] = None,
        logout_commands: Sequence[str] = ("exit", "quit"),
    ) -> None:
        self.host = host
        self.port = port
        self._username = username
        self._password = password
        self._connect_timeout = connect_timeout
        self._prompt_timeout = prompt_timeout
        self._command_timeout = command_timeout
        self._connector = connector
        self._logout_commands = tuple(logout_commands)

    async def get_statistics(self) -> CommandResponse:
        """Open one session, retrieve statistics, and close it cleanly."""
        reader = writer = None
        try:
            reader, writer = await self._connect()
            await self._authenticate(reader, writer)
            self._write_line(writer, "sh")
            await self._read_until(reader, (_SHELL_PROMPT,), self._prompt_timeout, "BusyBox shell")

            command = "xdslcmd info --stats"
            self._write_line(writer, command)
            command_exchange, _ = await self._read_until(
                reader,
                (_SHELL_PROMPT,),
                self._command_timeout,
                "statistics response",
                incomplete_on_eof=True,
            )
            output = self._strip_command_exchange(command_exchange, command)
            return CommandResponse(output=output, quality=ResponseQuality.COMPLETE)
        finally:
            if writer is not None:
                await self._close_session(writer)

    async def _connect(self) -> Tuple[Any, Any]:
        connector = self._connector
        if connector is None:
            try:
                import telnetlib3
            except ImportError as err:  # pragma: no cover - packaging failure
                raise RuntimeError("telnetlib3 is required for modem connections") from err
            connector = telnetlib3.open_connection

        try:
            return await asyncio.wait_for(
                connector(host=self.host, port=self.port, encoding="ascii"),
                timeout=self._connect_timeout,
            )
        except asyncio.TimeoutError as err:
            raise ConnectionTimeoutError(
                f"Timed out connecting to {self.host}:{self.port}"
            ) from err
        except OSError:
            raise

    async def _authenticate(self, reader: Any, writer: Any) -> None:
        initial, matched = await self._read_until(
            reader,
            (_USERNAME_PROMPT, _PASSWORD_PROMPT),
            self._prompt_timeout,
            "authentication prompt",
            reject_unknown_prompt=True,
        )
        if matched is _USERNAME_PROMPT:
            self._write_line(writer, self._username)
            _, matched = await self._read_until(
                reader,
                (_PASSWORD_PROMPT,),
                self._prompt_timeout,
                "password prompt",
                reject_unknown_prompt=True,
            )
        elif matched is not _PASSWORD_PROMPT:
            raise UnexpectedPromptError("Expected a username or password prompt")

        self._write_line(writer, self._password)
        try:
            exchange, matched = await self._read_until(
                reader,
                (_ATP_PROMPT, _USERNAME_PROMPT, _PASSWORD_PROMPT, _AUTH_FAILURE),
                self._prompt_timeout,
                "ATP prompt",
                reject_unknown_prompt=True,
            )
        except IncompleteResponseError as err:
            raise AuthenticationError("Connection closed during authentication") from err
        if matched is not _ATP_PROMPT:
            raise AuthenticationError("The modem rejected the supplied credentials")
        del initial, exchange

    async def _read_until(
        self,
        reader: Any,
        patterns: Sequence[re.Pattern[str]],
        timeout: float,
        description: str,
        *,
        reject_unknown_prompt: bool = False,
        incomplete_on_eof: bool = False,
    ) -> Tuple[str, re.Pattern[str]]:
        buffer = ""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            for pattern in patterns:
                if pattern.search(buffer):
                    return buffer, pattern

            if reject_unknown_prompt and _GENERIC_PROMPT.search(buffer):
                raise UnexpectedPromptError(
                    f"Unexpected prompt while waiting for {description}"
                )

            remaining = deadline - loop.time()
            if remaining <= 0:
                if incomplete_on_eof:
                    raise IncompleteResponseError(
                        f"Timed out before {description} completed", buffer
                    )
                raise ConnectionTimeoutError(f"Timed out waiting for {description}")
            try:
                chunk = await asyncio.wait_for(reader.read(1024), remaining)
            except asyncio.TimeoutError as err:
                if incomplete_on_eof:
                    raise IncompleteResponseError(
                        f"Timed out before {description} completed", buffer
                    ) from err
                raise ConnectionTimeoutError(f"Timed out waiting for {description}") from err
            if not chunk:
                if incomplete_on_eof:
                    raise IncompleteResponseError(
                        f"Connection closed before {description} completed", buffer
                    )
                raise IncompleteResponseError(
                    f"Connection closed while waiting for {description}", buffer
                )
            buffer += chunk

    @staticmethod
    def _write_line(writer: Any, value: str) -> None:
        writer.write(value + "\r\n")

    @staticmethod
    def _strip_command_exchange(exchange: str, command: str) -> str:
        normalized = exchange.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.splitlines()
        if lines and lines[0].strip() == command:
            lines.pop(0)
        if lines and re.fullmatch(r".*#\s*", lines[-1]):
            lines.pop()
        return "\n".join(lines).strip("\n")

    async def _close_session(self, writer: Any) -> None:
        try:
            for command in self._logout_commands:
                writer.write(command + "\r\n")
        except (OSError, RuntimeError):
            pass
        close = getattr(writer, "close", None)
        if close is not None:
            result = close()
            if inspect.isawaitable(result):
                await result


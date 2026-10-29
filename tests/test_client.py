"""Tests for the prompt-aware asynchronous Telnet client."""

import asyncio

import pytest

from huawei_hg612.client import HuaweiHG612Client
from huawei_hg612.exceptions import (
    AuthenticationError,
    ConnectionTimeoutError,
    IncompleteResponseError,
    UnexpectedPromptError,
)
from huawei_hg612.models import ResponseQuality


class ScriptedReader:
    """Queue-backed reader controlled by writes to a scripted peer."""

    def __init__(self, initial: str = "") -> None:
        self.queue = asyncio.Queue()
        if initial:
            self.queue.put_nowait(initial)

    async def read(self, size: int) -> str:
        del size
        value = await self.queue.get()
        return value

    def feed(self, value: str) -> None:
        self.queue.put_nowait(value)


class ScriptedWriter:
    def __init__(self, reader: ScriptedReader, script):
        self.reader = reader
        self.script = script
        self.writes = []
        self.closed = False

    def write(self, value: str) -> None:
        self.writes.append(value)
        response = self.script.get(value)
        if isinstance(response, tuple):
            for chunk in response:
                self.reader.feed(chunk)
        elif response is not None:
            self.reader.feed(response)

    def close(self) -> None:
        self.closed = True


def scripted_connector(initial, script):
    reader = ScriptedReader(initial)
    writer = ScriptedWriter(reader, script)

    async def connect(**kwargs):
        assert kwargs["host"] == "192.0.2.1"
        assert kwargs["port"] == 23
        assert kwargs["encoding"] == "ascii"
        return reader, writer

    return connect, writer


@pytest.mark.asyncio
async def test_successful_authentication_shell_transition_and_stats(fixture_text):
    output = fixture_text("stats_showtime_synthetic.txt")
    connector, writer = scripted_connector(
        "Welcome\r\nLogin: ",
        {
            "admin\r\n": "admin\r\nPassword: ",
            "secret\r\n": "\r\nATP>",
            "sh\r\n": "sh\r\nBusyBox v1.9.1\r\n# ",
            "xdslcmd info --stats\r\n": (
                "xdslcmd info --stats\r\n" + output.replace("\n", "\r\n") + "\r\n# "
            ),
        },
    )
    client = HuaweiHG612Client(
        "192.0.2.1", "admin", "secret", connector=connector, prompt_timeout=0.1
    )

    response = await client.get_statistics()

    assert response.quality is ResponseQuality.COMPLETE
    assert "Status: Showtime" in response.output
    assert "xdslcmd info --stats" not in response.output
    assert writer.closed is True
    assert "exit\r\n" in writer.writes
    assert "quit\r\n" in writer.writes


@pytest.mark.asyncio
async def test_password_only_authentication_prompt(fixture_text):
    connector, _ = scripted_connector(
        "Password: ",
        {
            "secret\r\n": "\r\nATP>",
            "sh\r\n": "\r\n# ",
            "xdslcmd info --stats\r\n": "Status: Idle\r\n# ",
        },
    )
    client = HuaweiHG612Client("192.0.2.1", "unused", "secret", connector=connector)

    response = await client.get_statistics()

    assert response.output == "Status: Idle"


@pytest.mark.asyncio
async def test_can_close_transport_without_sending_logout_commands():
    connector, writer = scripted_connector(
        "Login: ",
        {
            "admin\r\n": "Password: ",
            "secret\r\n": "ATP>",
            "sh\r\n": "# ",
            "xdslcmd info --stats\r\n": "Status: Idle\r\n# ",
        },
    )
    client = HuaweiHG612Client(
        "192.0.2.1",
        "admin",
        "secret",
        connector=connector,
        logout_commands=(),
    )

    await client.get_statistics()

    assert writer.writes == [
        "admin\r\n",
        "secret\r\n",
        "sh\r\n",
        "xdslcmd info --stats\r\n",
    ]


@pytest.mark.asyncio
async def test_incorrect_credentials():
    connector, _ = scripted_connector(
        "Login: ",
        {
            "admin\r\n": "Password: ",
            "wrong\r\n": "Login incorrect\r\nLogin: ",
        },
    )
    client = HuaweiHG612Client("192.0.2.1", "admin", "wrong", connector=connector)

    with pytest.raises(AuthenticationError):
        await client.get_statistics()


@pytest.mark.asyncio
async def test_unexpected_authentication_prompt():
    connector, _ = scripted_connector("Account number: ", {})
    client = HuaweiHG612Client("192.0.2.1", "admin", "secret", connector=connector)

    with pytest.raises(UnexpectedPromptError):
        await client.get_statistics()


@pytest.mark.asyncio
async def test_connection_timeout():
    async def never_connect(**kwargs):
        del kwargs
        await asyncio.sleep(1)

    client = HuaweiHG612Client(
        "192.0.2.1", "admin", "secret", connector=never_connect, connect_timeout=0.01
    )

    with pytest.raises(ConnectionTimeoutError):
        await client.get_statistics()


@pytest.mark.asyncio
async def test_timeout_waiting_for_shell_prompt():
    connector, _ = scripted_connector(
        "Login: ",
        {
            "admin\r\n": "Password: ",
            "secret\r\n": "ATP>",
            "sh\r\n": "BusyBox v1.9.1\r\n",
        },
    )
    client = HuaweiHG612Client(
        "192.0.2.1", "admin", "secret", connector=connector, prompt_timeout=0.01
    )

    with pytest.raises(ConnectionTimeoutError):
        await client.get_statistics()


@pytest.mark.asyncio
async def test_incomplete_statistics_response_retains_partial_output():
    connector, _ = scripted_connector(
        "Login: ",
        {
            "admin\r\n": "Password: ",
            "secret\r\n": "ATP>",
            "sh\r\n": "# ",
            "xdslcmd info --stats\r\n": (
                "Status: Showtime\r\nFEC: 12 0\r\n",
                "",
            ),
        },
    )
    client = HuaweiHG612Client(
        "192.0.2.1",
        "admin",
        "secret",
        connector=connector,
        command_timeout=0.01,
    )

    with pytest.raises(IncompleteResponseError) as error:
        await client.get_statistics()

    assert "Status: Showtime" in error.value.partial_output


@pytest.mark.asyncio
async def test_recovers_on_a_new_session_after_temporary_failure():
    calls = 0
    successful_connector, _ = scripted_connector(
        "Login: ",
        {
            "admin\r\n": "Password: ",
            "secret\r\n": "ATP>",
            "sh\r\n": "# ",
            "xdslcmd info --stats\r\n": "Status: Showtime\r\n# ",
        },
    )

    async def connector(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary connection failure")
        return await successful_connector(**kwargs)

    client = HuaweiHG612Client("192.0.2.1", "admin", "secret", connector=connector)

    with pytest.raises(OSError):
        await client.get_statistics()
    response = await client.get_statistics()

    assert response.output == "Status: Showtime"
    assert calls == 2


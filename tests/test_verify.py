"""Tests for the standalone read-only verification utility."""

import asyncio
import stat

import pytest

from huawei_hg612.verify import format_summary, save_raw_response, verify_modem


class SimulatedReader:
    def __init__(self) -> None:
        self.queue = asyncio.Queue()
        self.queue.put_nowait("Welcome\r\nLogin: ")

    async def read(self, size: int) -> str:
        del size
        return await self.queue.get()


class SimulatedWriter:
    def __init__(self, reader, output: str) -> None:
        self.reader = reader
        self.output = output
        self.writes = []
        self.closed = False

    def write(self, value: str) -> None:
        self.writes.append(value)
        responses = {
            "runtime-user\r\n": "Password: ",
            "runtime-password\r\n": "ATP>",
            "sh\r\n": "BusyBox v1.9.1\r\n# ",
            "xdslcmd info --stats\r\n": (
                "xdslcmd info --stats\r\n"
                + self.output.replace("\n", "\r\n")
                + "\r\n# "
            ),
        }
        if value in responses:
            self.reader.queue.put_nowait(responses[value])

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_verifier_uses_only_read_commands_and_parses_response(fixture_text, tmp_path):
    output = fixture_text("stats_showtime_synthetic.txt")
    reader = SimulatedReader()
    writer = SimulatedWriter(reader, output)

    async def connector(**kwargs):
        assert kwargs == {"host": "192.168.50.2", "port": 23, "encoding": "ascii"}
        return reader, writer

    raw_path = tmp_path / "hg612-stats.txt"
    stats = await verify_modem(
        "192.168.50.2",
        "runtime-user",
        "runtime-password",
        save_raw=raw_path,
        connector=connector,
    )

    assert stats.status == "Showtime"
    assert stats.sync_rate_kbps == (15713, 1177)
    assert writer.writes == [
        "runtime-user\r\n",
        "runtime-password\r\n",
        "sh\r\n",
        "xdslcmd info --stats\r\n",
    ]
    assert "runtime-user" not in raw_path.read_text(encoding="utf-8")
    assert "runtime-password" not in raw_path.read_text(encoding="utf-8")
    assert raw_path.read_text(encoding="utf-8").startswith("Status: Showtime")
    assert stat.S_IMODE(raw_path.stat().st_mode) == 0o600
    assert writer.closed is True


def test_summary_contains_requested_statistics(fixture_text):
    from huawei_hg612.models import CommandResponse
    from huawei_hg612.parser import parse_xdsl_stats

    stats = parse_xdsl_stats(CommandResponse(fixture_text("stats_showtime_synthetic.txt")))

    summary = format_summary(stats)

    assert "DSL status: Showtime" in summary
    assert "Sync speed: down 15713 Kbps, up 1177 Kbps" in summary
    assert "SNR margin: down 3.7 dB, up 6.4 dB" in summary
    assert "FEC: down 14634, up 0" in summary
    assert "CRC: down 4, up 1" in summary
    assert "Unrecognised lines/sections: none" in summary


def test_raw_capture_refuses_to_overwrite(tmp_path):
    path = tmp_path / "existing.txt"
    path.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        save_raw_response(path, "replacement")

    assert path.read_text(encoding="utf-8") == "keep"

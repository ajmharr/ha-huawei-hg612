"""Read-only command-line verification utility for a Huawei HG612 modem."""

import argparse
import asyncio
import getpass
import os
from pathlib import Path
import sys
from typing import Optional, Sequence

from .client import Connector, HuaweiHG612Client
from .exceptions import HuaweiHG612Error
from .models import CounterValues, DslStatistics
from .parser import parse_xdsl_stats

DEFAULT_HOST = "192.168.50.2"
_ERROR_COUNTERS = ("FEC", "CRC", "ES", "SES", "UAS", "LOS", "LOF")


def _format_pair(values, unit: str = "") -> str:
    if values is None:
        return "unavailable"
    downstream, upstream = values
    suffix = f" {unit}" if unit else ""
    down = "unavailable" if downstream is None else f"{downstream:g}{suffix}"
    up = "unavailable" if upstream is None else f"{upstream:g}{suffix}"
    return f"down {down}, up {up}"


def _counter_text(values: Optional[CounterValues]) -> str:
    if values is None:
        return "unavailable"
    down = "unavailable" if values.downstream is None else str(values.downstream)
    up = "unavailable" if values.upstream is None else str(values.upstream)
    return f"down {down}, up {up}"


def format_summary(stats: DslStatistics) -> str:
    """Create a concise human-readable summary."""
    sync_values = None
    if stats.sync_rate_kbps is not None:
        sync_values = stats.sync_rate_kbps
    snr_values = None
    if stats.snr_db is not None:
        snr_values = (stats.snr_db.downstream, stats.snr_db.upstream)

    lines = [
        "Huawei HG612 DSL summary",
        f"  DSL status: {stats.status or 'unavailable'}",
        f"  Line status: {stats.line_status or 'unavailable'}",
        f"  Sync speed: {_format_pair(sync_values, 'Kbps')}",
        f"  SNR margin: {_format_pair(snr_values, 'dB')}",
    ]

    total = stats.counter_sections.get("total")
    lines.append("  Total error counters:")
    for name in _ERROR_COUNTERS:
        values = total.counters.get(name) if total else None
        lines.append(f"    {name}: {_counter_text(values)}")

    if stats.unparsed_lines:
        lines.append(f"  Unrecognised lines/sections: {len(stats.unparsed_lines)}")
        lines.extend(f"    {line}" for line in stats.unparsed_lines)
    else:
        lines.append("  Unrecognised lines/sections: none")
    return "\n".join(lines)


def save_raw_response(path: Path, response: str) -> None:
    """Create an owner-readable raw capture without overwriting a file."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file_handle:
            file_handle.write(response)
            if response and not response.endswith("\n"):
                file_handle.write("\n")
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


async def verify_modem(
    host: str,
    username: str,
    password: str,
    *,
    port: int = 23,
    save_raw: Optional[Path] = None,
    connector: Optional[Connector] = None,
) -> DslStatistics:
    """Perform one read-only statistics request and parse it."""
    client = HuaweiHG612Client(
        host,
        username,
        password,
        port=port,
        connector=connector,
        # Closing the transport is sufficient for this one-shot verifier and
        # guarantees that only `sh` and `xdslcmd info --stats` are executed.
        logout_commands=(),
    )
    response = await client.get_statistics()
    if save_raw is not None:
        save_raw_response(save_raw, response.output)
    return parse_xdsl_stats(response)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read and parse Huawei HG612 DSL statistics over Telnet."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="modem host address")
    parser.add_argument("--port", type=int, default=23, help="Telnet port")
    parser.add_argument(
        "--save-raw",
        type=Path,
        metavar="PATH",
        help="create an owner-only file containing raw xdslcmd output",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    args = _parser().parse_args(argv)
    if args.save_raw is not None and args.save_raw.exists():
        print(f"Error: refusing to overwrite existing file: {args.save_raw}", file=sys.stderr)
        return 2

    username = getpass.getpass("Telnet username (input hidden): ")
    password = getpass.getpass("Telnet password: ")
    try:
        stats = asyncio.run(
            verify_modem(
                args.host,
                username,
                password,
                port=args.port,
                save_raw=args.save_raw,
            )
        )
    except (HuaweiHG612Error, OSError, ValueError) as err:
        print(f"Verification failed: {err}", file=sys.stderr)
        return 1

    print(format_summary(stats))
    if args.save_raw is not None:
        print(f"Raw xdslcmd response saved to: {args.save_raw}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

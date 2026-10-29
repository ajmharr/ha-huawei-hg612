"""Typed models shared by the Telnet client and statistics parser."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


class ResponseQuality(str, Enum):
    """Whether the command response was terminated normally."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class CommandResponse:
    """Raw output from one command, including transport completeness."""

    output: str
    quality: ResponseQuality = ResponseQuality.COMPLETE


@dataclass(frozen=True)
class DirectionalValues:
    """A downstream/upstream value pair."""

    downstream: Optional[float]
    upstream: Optional[float]


@dataclass(frozen=True)
class CounterValues:
    """A downstream/upstream integer counter pair."""

    downstream: Optional[int]
    upstream: Optional[int]


@dataclass(frozen=True)
class CounterSection:
    """Counters for one modem reporting period."""

    name: str
    duration_seconds: Optional[int] = None
    counters: Dict[str, CounterValues] = field(default_factory=dict)


@dataclass(frozen=True)
class DslStatistics:
    """Normalized DSL statistics with the unmodified command output."""

    raw_output: str
    response_quality: ResponseQuality
    status: Optional[str] = None
    line_status: Optional[str] = None
    mode: Optional[str] = None
    profile: Optional[str] = None
    sync_rate_kbps: Optional[Tuple[Optional[int], Optional[int]]] = None
    attainable_rate_kbps: Optional[Tuple[Optional[int], Optional[int]]] = None
    snr_db: Optional[DirectionalValues] = None
    attenuation_db: Optional[DirectionalValues] = None
    power_dbm: Optional[DirectionalValues] = None
    total_duration_seconds: Optional[int] = None
    link_duration_seconds: Optional[int] = None
    counter_sections: Dict[str, CounterSection] = field(default_factory=dict)
    ignored_detail_lines: Tuple[str, ...] = ()
    unparsed_lines: Tuple[str, ...] = ()

    @property
    def is_synchronized(self) -> Optional[bool]:
        """Return sync state without guessing when status is absent."""
        if self.status is None:
            return None
        return self.status.strip().casefold() == "showtime"


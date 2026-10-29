"""Pure parser for ``xdslcmd info --stats`` output."""

import re
from typing import Dict, Iterable, List, Optional, Tuple

from .models import (
    CommandResponse,
    CounterSection,
    CounterValues,
    DirectionalValues,
    DslStatistics,
    ResponseQuality,
)

_RATE_RE = re.compile(
    r"^(Max|Bearer):(?:\s*(\d+),)?\s*Upstream rate\s*=\s*(\d+)\s*Kbps,\s*"
    r"Downstream rate\s*=\s*(\d+)\s*Kbps\s*$",
    re.IGNORECASE,
)
_PAIR_RE = re.compile(
    r"^(SNR \(dB\)|Attn\(dB\)|Pwr\(dBm\)):\s*"
    r"(-?(?:\d+(?:\.\d+)?|nan|n/?a|-))\s+"
    r"(-?(?:\d+(?:\.\d+)?|nan|n/?a|-))\s*$",
    re.IGNORECASE,
)
_COUNTER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 _/-]*):\s*(-|\d+)\s+(-|\d+)\s*$")
_UNKNOWN_SECTION_RE = re.compile(r"\btime\s*=", re.IGNORECASE)
_DETAIL_HEADING_RE = re.compile(
    r"^(?:xdslcmd: ADSL driver and PHY status|VDSL2 framing|Bearer \d+|Counters|"
    r"Retransmit Counters|G\.INP Counters|Down\s+Up)$",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(
    r"(?:(\d+)\s*days?\s*)?(?:(\d+)\s*hours?\s*)?"
    r"(?:(\d+)\s*min(?:utes?)?\s*)?(?:(\d+)\s*sec(?:onds?)?\s*)?",
    re.IGNORECASE,
)

_SECTION_HEADINGS = (
    (re.compile(r"^Total time\s*=", re.IGNORECASE), "total"),
    (re.compile(r"^(?:Latest|Current) 15 minutes? time\s*=", re.IGNORECASE), "current_15_minutes"),
    (re.compile(r"^Previous 15 minutes? time\s*=", re.IGNORECASE), "previous_15_minutes"),
    (re.compile(r"^(?:Latest|Current) (?:1 )?day time\s*=", re.IGNORECASE), "current_day"),
    (re.compile(r"^Previous (?:1 )?day time\s*=", re.IGNORECASE), "previous_day"),
    (re.compile(r"^Since Link time\s*=", re.IGNORECASE), "since_link"),
)


def _optional_float(value: str) -> Optional[float]:
    if value.casefold() in {"-", "n/a", "na", "nan"}:
        return None
    return float(value)


def _optional_int(value: str) -> Optional[int]:
    return None if value == "-" else int(value)


def _duration_seconds(text: str) -> Optional[int]:
    match = _DURATION_RE.fullmatch(text.strip())
    if not match or not any(match.groups()):
        return None
    days, hours, minutes, seconds = (int(value or 0) for value in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _section_for_line(line: str) -> Optional[Tuple[str, Optional[int]]]:
    for pattern, name in _SECTION_HEADINGS:
        match = pattern.match(line)
        if match:
            duration_text = line.split("=", 1)[1] if "=" in line else ""
            return name, _duration_seconds(duration_text)
    return None


def parse_xdsl_stats(
    response: CommandResponse,
) -> DslStatistics:
    """Parse a command response without converting absent values to zero.

    ``response.quality`` is transport metadata. A complete modem response may
    legitimately contain few or no DSL values; an incomplete response may
    still be parsed for diagnostics but remains explicitly marked incomplete.
    """
    status = line_status = mode = profile = None
    sync_rate = attainable_rate = None
    snr = attenuation = power = None
    total_duration = link_duration = None
    sections: Dict[str, CounterSection] = {}
    section_counters: Dict[str, Dict[str, CounterValues]] = {}
    section_durations: Dict[str, Optional[int]] = {}
    current_section: Optional[str] = None
    reporting_started = False
    ignored_details: List[str] = []
    unparsed: List[str] = []

    for original_line in response.output.splitlines():
        line = original_line.strip()
        if not line or line.casefold() in {"down    up", "down up"}:
            continue

        section = _section_for_line(line)
        if section:
            reporting_started = True
            current_section, duration = section
            section_durations[current_section] = duration
            section_counters.setdefault(current_section, {})
            if current_section == "total":
                total_duration = duration
            elif current_section == "since_link":
                link_duration = duration
            continue

        # Do not attach counters beneath an unknown reporting-period heading
        # to the preceding known section. Preserve the whole unknown block as
        # unparsed instead.
        if _UNKNOWN_SECTION_RE.search(line):
            current_section = None
            unparsed.append(original_line)
            continue

        if line.startswith("Status:"):
            status = line.split(":", 1)[1].strip() or None
            continue
        if line.startswith("Line Status:"):
            line_status = line.split(":", 1)[1].strip() or None
            continue
        if line.startswith("Mode:"):
            mode = line.split(":", 1)[1].strip() or None
            continue
        if line.startswith("VDSL2 Profile:"):
            profile = line.split(":", 1)[1].strip() or None
            continue

        rate_match = _RATE_RE.match(line)
        if rate_match:
            pair = (int(rate_match.group(4)), int(rate_match.group(3)))
            if rate_match.group(1).casefold() == "max":
                attainable_rate = pair
            elif rate_match.group(2) in {None, "0"}:
                sync_rate = pair
            continue

        pair_match = _PAIR_RE.match(line)
        if pair_match:
            pair = DirectionalValues(
                downstream=_optional_float(pair_match.group(2)),
                upstream=_optional_float(pair_match.group(3)),
            )
            label = pair_match.group(1).casefold()
            if label.startswith("snr"):
                snr = pair
            elif label.startswith("attn"):
                attenuation = pair
            else:
                power = pair
            continue

        counter_match = _COUNTER_RE.match(line)
        if counter_match and current_section:
            counter_name = counter_match.group(1).strip().upper().replace(" ", "_")
            section_counters[current_section][counter_name] = CounterValues(
                downstream=_optional_int(counter_match.group(2)),
                upstream=_optional_int(counter_match.group(3)),
            )
            continue

        # The full HG612 response includes framing, bearer, retransmission and
        # G.INP diagnostics before the reporting-period counters. They are
        # valid modem detail but outside Phase 1's normalized data model.
        if not reporting_started and (":" in line or _DETAIL_HEADING_RE.match(line)):
            ignored_details.append(original_line)
            continue

        unparsed.append(original_line)

    for name, counters in section_counters.items():
        sections[name] = CounterSection(
            name=name,
            duration_seconds=section_durations.get(name),
            counters=counters,
        )

    return DslStatistics(
        raw_output=response.output,
        response_quality=response.quality,
        status=status,
        line_status=line_status,
        mode=mode,
        profile=profile,
        sync_rate_kbps=sync_rate,
        attainable_rate_kbps=attainable_rate,
        snr_db=snr,
        attenuation_db=attenuation,
        power_dbm=power,
        total_duration_seconds=total_duration,
        link_duration_seconds=link_duration,
        counter_sections=sections,
        ignored_detail_lines=tuple(ignored_details),
        unparsed_lines=tuple(unparsed),
    )


def detect_counter_resets(
    previous: DslStatistics,
    current: DslStatistics,
    section_names: Iterable[str] = ("total", "since_link"),
) -> Tuple[str, ...]:
    """Return paths of cumulative counters that decreased.

    Missing counters are ignored: absence is not evidence of a reset.
    """
    resets: List[str] = []
    for section_name in section_names:
        previous_section = previous.counter_sections.get(section_name)
        current_section = current.counter_sections.get(section_name)
        if not previous_section or not current_section:
            continue
        for counter_name, old_pair in previous_section.counters.items():
            new_pair = current_section.counters.get(counter_name)
            if not new_pair:
                continue
            for direction in ("downstream", "upstream"):
                old_value = getattr(old_pair, direction)
                new_value = getattr(new_pair, direction)
                if old_value is not None and new_value is not None and new_value < old_value:
                    resets.append(f"{section_name}.{counter_name}.{direction}")
    return tuple(resets)

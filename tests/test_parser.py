"""Tests for the pure DSL statistics parser."""

from dataclasses import replace

from custom_components.huawei_hg612.models import CommandResponse, ResponseQuality
from custom_components.huawei_hg612.parser import detect_counter_resets, parse_xdsl_stats


def test_parses_showtime_statistics_and_keeps_sections_separate(fixture_text):
    stats = parse_xdsl_stats(CommandResponse(fixture_text("stats_showtime_synthetic.txt")))

    assert stats.response_quality is ResponseQuality.COMPLETE
    assert stats.is_synchronized is True
    assert stats.status == "Showtime"
    assert stats.line_status == "No Defect"
    assert stats.mode == "VDSL2 Annex B"
    assert stats.profile == "Profile 17a"
    assert stats.sync_rate_kbps == (15713, 1177)
    assert stats.attainable_rate_kbps == (16148, 1177)
    assert stats.snr_db.downstream == 3.7
    assert stats.snr_db.upstream == 6.4
    assert stats.total_duration_seconds == 4841
    assert stats.link_duration_seconds == 4757

    assert stats.counter_sections["total"].counters["FEC"].downstream == 14634
    assert stats.counter_sections["current_15_minutes"].counters["FEC"].downstream == 34
    assert stats.counter_sections["previous_15_minutes"].counters["FEC"].downstream == 120
    assert stats.counter_sections["since_link"].counters["FEC"].downstream == 14500
    assert len(stats.ignored_detail_lines) == 6
    assert stats.unparsed_lines == ()


def test_disconnected_response_is_complete_with_missing_values(fixture_text):
    stats = parse_xdsl_stats(CommandResponse(fixture_text("stats_disconnected_synthetic.txt")))

    assert stats.response_quality is ResponseQuality.COMPLETE
    assert stats.is_synchronized is False
    assert stats.sync_rate_kbps is None
    assert stats.snr_db is None
    assert stats.counter_sections["total"].counters["UAS"].downstream == 123


def test_unavailable_values_remain_none_not_zero(fixture_text):
    stats = parse_xdsl_stats(CommandResponse(fixture_text("stats_missing_values_synthetic.txt")))

    assert stats.response_quality is ResponseQuality.COMPLETE
    assert stats.snr_db.downstream == 4.2
    assert stats.snr_db.upstream is None
    assert stats.attenuation_db.upstream is None
    assert stats.counter_sections["total"].counters["CRC"].downstream == 0
    assert stats.counter_sections["total"].counters["CRC"].upstream is None


def test_transport_incomplete_is_distinct_from_missing_statistics(fixture_text):
    stats = parse_xdsl_stats(
        CommandResponse(
            fixture_text("stats_incomplete_synthetic.txt"),
            quality=ResponseQuality.INCOMPLETE,
        )
    )

    assert stats.response_quality is ResponseQuality.INCOMPLETE
    assert stats.status == "Showtime"
    assert stats.counter_sections["total"].counters["FEC"].downstream == 14634
    assert "CRC:" in stats.unparsed_lines


def test_empty_complete_response_does_not_invent_values():
    stats = parse_xdsl_stats(CommandResponse("No DSL statistics available"))

    assert stats.response_quality is ResponseQuality.COMPLETE
    assert stats.status is None
    assert stats.is_synchronized is None
    assert stats.counter_sections == {}
    assert stats.unparsed_lines == ("No DSL statistics available",)


def test_detects_counter_decrease_as_reset(fixture_text):
    previous = parse_xdsl_stats(CommandResponse(fixture_text("stats_showtime_synthetic.txt")))
    total = previous.counter_sections["total"]
    reduced_counters = dict(total.counters)
    reduced_counters["FEC"] = replace(reduced_counters["FEC"], downstream=3)
    current = replace(
        previous,
        counter_sections={
            **previous.counter_sections,
            "total": replace(total, counters=reduced_counters),
        },
    )

    assert detect_counter_resets(previous, current) == ("total.FEC.downstream",)


def test_missing_counter_is_not_a_reset(fixture_text):
    previous = parse_xdsl_stats(CommandResponse(fixture_text("stats_showtime_synthetic.txt")))
    current = replace(previous, counter_sections={})

    assert detect_counter_resets(previous, current) == ()


def test_unknown_section_does_not_overwrite_known_counters():
    response = CommandResponse(
        "Total time = 1 min 0 sec\n"
        "CRC: 10 1\n"
        "Experimental period time = 30 sec\n"
        "CRC: 99 99\n"
    )

    stats = parse_xdsl_stats(response)

    assert stats.counter_sections["total"].counters["CRC"].downstream == 10
    assert stats.unparsed_lines == (
        "Experimental period time = 30 sec",
        "CRC: 99 99",
    )


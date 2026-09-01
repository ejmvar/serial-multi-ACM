from serial_terminal.filters import LineFilter, is_visible
import pytest

from serial_terminal.formatting import (
    DisplayPolicy,
    format_mac,
    log_file_name,
    parse_device_line,
    render_record,
    sanitize_port,
)


def test_port_names_are_sanitized_for_log_files() -> None:
    assert sanitize_port("/dev/ttyACM0") == "dev_ttyACM0"
    assert log_file_name("/dev/tty ACM0", "20260825_120000") == "log_dev_tty_ACM0_20260825_120000.log"


def test_plain_and_regex_filters_are_combined() -> None:
    global_filter = LineFilter.parse("error")
    port_filter = LineFilter.parse("/RX\\s+42/")
    assert is_visible("ERROR RX 42", global_filter, port_filter)
    assert not is_visible("ERROR TX 42", global_filter, port_filter)
    assert not is_visible("INFO RX 42", global_filter, port_filter)


@pytest.mark.parametrize(
    ("marker", "prefix"),
    [("", ""), ("-", "- "), ("+", "+ "), ("+-", "+- ")],
)
def test_render_record_formats_display_only_marker_and_tags(marker: str, prefix: str) -> None:
    rendered = render_record(
        "2026-08-25T00:00:00+00:00", "/dev/ttyACM0", "INFO ready", frozenset({"2", "a"}), marker=marker
    )

    assert rendered.plain == (
        f"{prefix}2026-08-25T00:00:00+00:00 /dev/ttyACM0 | INFO ready [#2 #a]\n"
        "↳ Uninterpreted"
    )


def test_render_record_preserves_highlighting_after_marker_prefix() -> None:
    rendered = render_record("2026-08-25T00:00:00+00:00", "port", "ERROR RX 42", marker="+-")

    assert rendered.plain.startswith("+- 2026-08-25T00:00:00+00:00 port | ")
    assert any(
        span.style == "bold red" and rendered.plain[span.start : span.end] == "ERROR"
        for span in rendered.spans
    )
    assert any(
        span.style == "bold magenta" and rendered.plain[span.start : span.end] == "RX"
        for span in rendered.spans
    )


@pytest.mark.parametrize(
    ("line", "derived"),
    [
        ("I (12) boot: ready", "↳ INFO boot | device elapsed: 12 ms"),
        ("W (80) handshake: retry", "↳ WARN handshake | device elapsed: 80 ms"),
        ("E (91) wifi: failed", "↳ ERROR wifi | device elapsed: 91 ms"),
        ("I (12) handshake: peer found", "↳ INFO handshake | device elapsed: 12 ms: peer discovered"),
        (
            "I (13) link: ACK",
            "↳ INFO link | device elapsed: 13 ms: acknowledgement received",
        ),
    ],
)
def test_render_record_appends_conservative_interpretation(line: str, derived: str) -> None:
    rendered = render_record("2026-08-25T00:00:00+00:00", "port", line)

    assert rendered.plain == (
        f"2026-08-25T00:00:00+00:00 port | {line}\n{derived}"
    )


def test_render_record_keeps_host_utc_separate_from_device_elapsed() -> None:
    rendered = render_record("2026-08-25T00:00:00+00:00", "port", "W (80) link: retry")

    assert "2026-08-25T00:00:00+00:00 port | W (80) link: retry" in rendered.plain
    assert "device elapsed: 80 ms" in rendered.plain
    assert "UTC" not in rendered.plain
    assert "@80 ms" not in rendered.plain


@pytest.mark.parametrize("line", ["bootloader: ESP-IDF", "I (12) boot: first I (13) link: ACK"])
def test_render_record_marks_rejected_lines_uninterpreted(line: str) -> None:
    rendered = render_record("2026-08-25T00:00:00+00:00", "port", line)

    assert rendered.plain.endswith(f"| {line}\n↳ Uninterpreted")


def test_render_record_preserves_ansi_as_plain_raw_text_without_rich_styling() -> None:
    line = "I (12) link: \x1b[31mACK\x1b[0m"
    rendered = render_record("2026-08-25T00:00:00+00:00", "port", line)

    assert line in rendered.plain
    assert rendered.plain.endswith("↳ Uninterpreted")
    assert all("\x1b" not in rendered.plain[span.start : span.end] for span in rendered.spans)


@pytest.mark.parametrize("marker", ["+", "-", "+-"])
def test_render_record_hides_parsed_raw_line_and_relocates_marker(marker: str) -> None:
    rendered = render_record(
        "2026-08-25T00:00:00+00:00",
        "port",
        "I (12) boot: ready",
        marker=marker,
        policy=DisplayPolicy(raw_lines=False),
    )

    assert rendered.plain == f"{marker} ↳ INFO boot | device elapsed: 12 ms"
    assert rendered.plain.count("\n") == 0


def test_render_record_keeps_uninterpreted_raw_line_when_hidden() -> None:
    line = "unknown [raw] record"

    rendered = render_record(
        "2026-08-25T00:00:00+00:00", "port", line, marker="+", policy=DisplayPolicy(raw_lines=False)
    )

    assert rendered.plain == f"+ 2026-08-25T00:00:00+00:00 port | {line}\n↳ Uninterpreted"


@pytest.mark.parametrize(
    "line",
    [
        "I (12) boot: \x1b[31mfailed\x1b[0m",
        "I (12) boot: first\nsecond",
        "I (12) boot ready",
        "unknown [raw] record",
    ],
)
def test_render_record_preserves_exact_unsafe_or_unknown_raw_when_hidden(line: str) -> None:
    rendered = render_record("timestamp", "port", line, policy=DisplayPolicy(raw_lines=False))

    assert line in rendered.plain
    assert rendered.plain.endswith("↳ Uninterpreted")


def test_render_record_has_two_lines_when_raw_is_shown_and_one_when_parsed_raw_is_hidden() -> None:
    line = "W (80) handshake: retry"

    shown = render_record("timestamp", "port", line)
    hidden = render_record("timestamp", "port", line, policy=DisplayPolicy(raw_lines=False))

    assert shown.plain.count("\n") == 1
    assert hidden.plain.count("\n") == 0
    assert hidden.plain == "↳ WARN handshake | device elapsed: 80 ms"


def test_render_record_keeps_rich_spans_safe_after_hiding_raw_line() -> None:
    rendered = render_record(
        "timestamp",
        "port",
        "E (12) boot: [bold]ERROR[/bold]",
        policy=DisplayPolicy(raw_lines=False),
    )

    assert rendered.plain == "↳ ERROR boot | device elapsed: 12 ms"
    assert any(
        span.style == "bold red" and rendered.plain[span.start : span.end] == "ERROR"
        for span in rendered.spans
    )
    assert "[bold]" not in rendered.plain


@pytest.mark.parametrize(
    ("line", "severity", "device_ms", "component", "message", "explanation"),
    [
        ("I (12) boot: ready", "INFO", 12, "boot", "ready", None),
        ("W (80) handshake: retry", "WARN", 80, "handshake", "retry", None),
        ("E (91) wifi: failed", "ERROR", 91, "wifi", "failed", None),
        ("I (12) boot: unusual vendor text", "INFO", 12, "boot", "unusual vendor text", None),
        ("I (12) handshake: peer found", "INFO", 12, "handshake", "peer found", "peer discovered"),
        ("I (13) link: ACK", "INFO", 13, "link", "ACK", "acknowledgement received"),
        ("W (14) link: acknowledged", "WARN", 14, "link", "acknowledged", "acknowledgement received"),
    ],
)
def test_parse_device_line_returns_exact_fields_and_explanations(
    line: str,
    severity: str,
    device_ms: int,
    component: str,
    message: str,
    explanation: str | None,
) -> None:
    parsed = parse_device_line(line)

    assert parsed is not None
    assert (parsed.severity, parsed.device_ms, parsed.component, parsed.message, parsed.explanation) == (
        severity,
        device_ms,
        component,
        message,
        explanation,
    )


@pytest.mark.parametrize(
    "line",
    [
        "bootloader: ESP-IDF",
        "I (12) boot ready",
        "I (12) boot: ",
        "I (12) boot: continuation\ntext",
        "I (12) boot: \x1b[31mfailed\x1b[0m",
        "I (12) boot: first I (13) link: ACK",
        "I (12) boot: first E (13) link: failed",
        "D (12) boot: debug",
        "I (12) boot: first\rsecond",
    ],
)
def test_parse_device_line_rejects_unsafe_or_incomplete_records(line: str) -> None:
    assert parse_device_line(line) is None


def test_display_policy_is_immutable_and_defaults_to_full_visible_output() -> None:
    policy = DisplayPolicy()

    assert policy.raw_lines is True
    assert policy.mac_mode == "full"
    assert policy.toggle_raw() == DisplayPolicy(raw_lines=False)
    assert policy.select_mac("m") == DisplayPolicy(mac_mode="4")
    with pytest.raises(AttributeError):
        policy.raw_lines = False  # type: ignore[misc]


@pytest.mark.parametrize(
    ("key", "expected"),
    [("m", "4"), ("M", "6")],
)
def test_display_policy_selects_case_sensitive_mac_modes(key: str, expected: str) -> None:
    assert DisplayPolicy().select_mac(key).mac_mode == expected
    assert DisplayPolicy(mac_mode=expected).select_mac(key) == DisplayPolicy()


def test_display_policy_switches_mac_mode_without_normalizing_case() -> None:
    policy = DisplayPolicy(mac_mode="4")

    assert policy.select_mac("M") == DisplayPolicy(mac_mode="6")
    assert policy.select_mac("m") == DisplayPolicy()
    assert policy.select_mac("x") == policy


@pytest.mark.parametrize(
    ("value", "policy", "expected"),
    [
        ("14:c1:9f:3b:1e:b4", DisplayPolicy(), "14:c1:9f:3b:1e:b4"),
        ("14:c1:9f:3b:1e:b4", DisplayPolicy(mac_mode="4"), "1e:b4"),
        ("14:c1:9f:3b:1e:b4", DisplayPolicy(mac_mode="6"), "3b:1e:b4"),
        ("14-C1-9F-3B-1E-B4", DisplayPolicy(), "14:c1:9f:3b:1e:b4"),
        ("14-C1-9F-3B-1E-B4", DisplayPolicy(mac_mode="4"), "1e:b4"),
        ("14-C1-9F-3B-1E-B4", DisplayPolicy(mac_mode="6"), "3b:1e:b4"),
    ],
)
def test_format_mac_supports_full_and_suffix_modes_for_colon_and_dash_values(
    value: str, policy: DisplayPolicy, expected: str
) -> None:
    assert format_mac(value, policy) == expected


@pytest.mark.parametrize("value", [None, "", "14:c1:9f:3b:1e", "raw text", "UNINTERPRETED"])
def test_format_mac_preserves_absent_invalid_and_non_interpreted_values(value: str | None) -> None:
    assert format_mac(value, DisplayPolicy(mac_mode="4")) == value


def test_parse_type_one_uses_authoritative_gateway_direction() -> None:
    parsed = parse_device_line("W (80) handshake: ESP-NOW RX raw from 14:c1:9f:3b:1e:b4 type=1")
    assert parsed is not None
    assert (parsed.message_type, parsed.message_type_name, parsed.direction, parsed.peer_mac) == (
        1, "HANDSHAKE_MESSAGE_GATEWAY_BEACON", "gateway_to_edge", "14:c1:9f:3b:1e:b4"
    )


def test_parse_type_ten_and_unknown_type() -> None:
    ack = parse_device_line("I (1) link: type=10 DATA_ACK")
    unknown = parse_device_line("I (1) link: type=99 future")
    assert ack is not None and ack.message_type_name == "HANDSHAKE_MESSAGE_DATA_ACK"
    assert unknown is not None and unknown.message_type == 99 and unknown.message_type_name is None


def test_parse_canonical_identity_and_reject_malformed_mac() -> None:
    parsed = parse_device_line("I (1) handshake: identity: device=14:c1:9f:3b:1e:b4 role=gateway role_source=gpio4_latched degraded_request=released")
    malformed = parse_device_line("I (1) handshake: identity: device=not-a-mac role=edge")
    assert parsed is not None
    assert (parsed.device_mac, parsed.role, parsed.role_source, parsed.evidence) == (
        "14:c1:9f:3b:1e:b4", "gateway", "gpio4_latched", "DECLARED"
    )
    assert malformed is not None and malformed.device_mac is None and malformed.evidence == "UNKNOWN"


def test_render_record_preserves_raw_text_and_adds_explicit_type_projection() -> None:
    line = "W (80) handshake: ESP-NOW RX raw from 14:c1:9f:3b:1e:b4 type=1"
    rendered = render_record("timestamp", "port", line)
    assert line in rendered.plain
    assert "type=1 HANDSHAKE_MESSAGE_GATEWAY_BEACON" in rendered.plain

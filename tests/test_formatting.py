from serial_terminal.filters import LineFilter, is_visible
import pytest

from serial_terminal.formatting import log_file_name, parse_device_line, render_record, sanitize_port


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

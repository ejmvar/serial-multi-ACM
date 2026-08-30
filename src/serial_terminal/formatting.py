"""Formatting helpers shared by the reader and TUI."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
import re
from typing import Literal

from rich.text import Text


HIGHLIGHTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bNACK\b", re.IGNORECASE), "bold white on red"),
    (re.compile(r"\bACK\b", re.IGNORECASE), "bold black on green"),
    (re.compile(r"\bTX\b", re.IGNORECASE), "bold cyan"),
    (re.compile(r"\bRX\b", re.IGNORECASE), "bold magenta"),
    (re.compile(r"\b(?:FATAL|CRITICAL|ERROR|ERR)\b", re.IGNORECASE), "bold red"),
    (re.compile(r"\b(?:WARN|WARNING)\b", re.IGNORECASE), "bold yellow"),
    (re.compile(r"\b(?:INFO|DEBUG|TRACE)\b", re.IGNORECASE), "blue"),
)

_DEVICE_LINE_RE = re.compile(r"^(I|W|E) \((\d+)\) ([^:]+): (.+)$")
_DEVICE_HEADER_RE = re.compile(r"(?:I|W|E) \(\d+\) [^:]+: ")


@dataclass(frozen=True)
class DeviceLine:
    """Immutable interpretation of one complete ESP-IDF device record."""

    severity: Literal["INFO", "WARN", "ERROR"]
    device_ms: int
    component: str
    message: str
    explanation: str | None


def parse_device_line(line: str) -> DeviceLine | None:
    """Parse one conservative, complete ESP-IDF-style device line."""
    if any(control in line for control in ("\x1b", "\r", "\n")):
        return None

    match = _DEVICE_LINE_RE.fullmatch(line)
    if match is None:
        return None

    level, device_ms, component, message = match.groups()
    if _DEVICE_HEADER_RE.search(message) is not None:
        return None

    severity: Literal["INFO", "WARN", "ERROR"] = {"I": "INFO", "W": "WARN", "E": "ERROR"}[level]
    explanation = None
    if component == "handshake" and message == "peer found":
        explanation = "peer discovered"
    elif message in {"ACK", "acknowledged"}:
        explanation = "acknowledgement received"

    return DeviceLine(severity, int(device_ms), component, message, explanation)


def iso_timestamp() -> str:
    """Return an ISO-8601 timestamp in UTC with millisecond precision."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def file_timestamp() -> str:
    """Return the timestamp component used in log file names."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_port(port: str) -> str:
    """Make a serial device name safe and readable in a file name."""
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", port).strip("._")
    return sanitized or "port"


def log_file_name(port: str, timestamp: str | None = None) -> str:
    """Create the required independent log file name for *port*."""
    return f"log_{sanitize_port(port)}_{timestamp or file_timestamp()}.log"


def format_tags(tags: frozenset[str]) -> str:
    """Return stable, explicit tag labels for display and study exports."""
    return " ".join(f"#{tag}" for tag in sorted(tags))


def render_record(
    timestamp: str,
    port: str,
    line: str,
    tags: frozenset[str] = frozenset(),
    *,
    marker: str = "",
) -> Text:
    """Render raw evidence followed by its conservative derived projection."""
    suffix = f" [{format_tags(tags)}]" if tags else ""
    prefix = f"{marker} " if marker else ""
    parsed = parse_device_line(line)
    if parsed is None:
        derived = "↳ Uninterpreted"
    else:
        explanation = f": {parsed.explanation}" if parsed.explanation else ""
        derived = (
            f"↳ {parsed.severity} {parsed.component} | "
            f"device elapsed: {parsed.device_ms} ms{explanation}"
        )

    # Text construction does not parse markup; callers must retain markup=False
    # when printing this renderable through Rich.
    text = Text(f"{prefix}{timestamp} {port} | {line}{suffix}\n{derived}")
    if not any(control in line for control in ("\x1b", "\r", "\n")):
        for pattern, style in HIGHLIGHTS:
            for match in pattern.finditer(text.plain):
                text.stylize(style, match.start(), match.end())
    return text

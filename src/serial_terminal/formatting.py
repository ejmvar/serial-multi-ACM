"""Formatting helpers shared by the reader and TUI."""

from __future__ import annotations

from datetime import datetime, timezone
import re

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


def render_record(timestamp: str, port: str, line: str) -> Text:
    """Render one received line with safe Rich highlighting."""
    text = Text(f"{timestamp} {port} | {line.rstrip()}")
    for pattern, style in HIGHLIGHTS:
        for match in pattern.finditer(text.plain):
            text.stylize(style, match.start(), match.end())
    return text

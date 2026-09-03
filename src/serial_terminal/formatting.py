"""Formatting helpers shared by the reader and TUI."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, replace
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
_MAC_RE = re.compile(
    r"^[0-9A-Fa-f]{2}(?P<separator>[:-])[0-9A-Fa-f]{2}"
    r"(?P=separator)[0-9A-Fa-f]{2}(?P=separator)[0-9A-Fa-f]{2}"
    r"(?P=separator)[0-9A-Fa-f]{2}(?P=separator)[0-9A-Fa-f]{2}$"
)
_TYPE_RE = re.compile(r"(?<!\w)type\s*=\s*(\d+)(?!\w)", re.IGNORECASE)
_ROLE_RE = re.compile(r"(?<!\w)role\s*=\s*(gateway|edge|gw|\b(?:GW|EDGE)\b)(?!\w)", re.IGNORECASE)
_ROLE_SOURCE_RE = re.compile(r"(?<!\w)role_source\s*=\s*([A-Za-z0-9_-]+)", re.IGNORECASE)
_FROM_RE = re.compile(r"\bfrom\s+((?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})\b", re.IGNORECASE)
_TO_RE = re.compile(r"\bto\s+((?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})\b", re.IGNORECASE)

MESSAGE_TYPES: dict[int, str] = {
    1: "HANDSHAKE_MESSAGE_GATEWAY_BEACON",
    2: "HANDSHAKE_MESSAGE_EDGE_AVAILABLE",
    3: "HANDSHAKE_MESSAGE_BIND_REQUEST",
    4: "HANDSHAKE_MESSAGE_BIND_ACCEPT",
    5: "HANDSHAKE_MESSAGE_BIND_CONFIRM",
    6: "HANDSHAKE_MESSAGE_EDGE_PACKET",
    7: "HANDSHAKE_MESSAGE_HEARTBEAT",
    8: "HANDSHAKE_MESSAGE_HEARTBEAT_ACK",
    9: "HANDSHAKE_MESSAGE_DATA_MESSAGE",
    10: "HANDSHAKE_MESSAGE_DATA_ACK",
    11: "HANDSHAKE_MESSAGE_ERROR_FOUND",
    12: "HANDSHAKE_MESSAGE_FIELD_LOG",
    13: "HANDSHAKE_MESSAGE_FIELD_LOG_ACK",
}
_GATEWAY_TO_EDGE = frozenset({1, 4, 8, 10})


@dataclass(frozen=True)
class DeviceLine:
    """Immutable interpretation of one complete ESP-IDF device record."""

    severity: Literal["INFO", "WARN", "ERROR"]
    device_ms: int
    component: str
    message: str
    explanation: str | None
    device_mac: str | None = None
    role: str | None = None
    role_source: str | None = None
    peer_mac: str | None = None
    message_type: int | None = None
    message_type_name: str | None = None
    direction: str | None = None
    evidence: Literal["OBSERVED", "DECLARED", "UNKNOWN"] = "UNKNOWN"


@dataclass(frozen=True)
class DisplayPolicy:
    """Immutable, session-local presentation choices."""

    raw_lines: bool = True
    mac_mode: Literal["full", "4", "6"] = "full"

    def toggle_raw(self) -> DisplayPolicy:
        """Return a policy with raw-line visibility toggled."""
        return replace(self, raw_lines=not self.raw_lines)

    def select_mac(self, key: str) -> DisplayPolicy:
        """Select or restore a MAC mode using the case-sensitive binding key."""
        if key == "m":
            mode: Literal["full", "4", "6"] = "full" if self.mac_mode == "4" else "4"
        elif key == "M":
            mode = "full" if self.mac_mode == "6" else "6"
        else:
            return self
        return replace(self, mac_mode=mode)


DEFAULT_DISPLAY_POLICY = DisplayPolicy()


def format_mac(value: str | None, policy: DisplayPolicy) -> str | None:
    """Format only complete six-octet MAC values for human-facing display."""
    if value is None:
        return None

    match = _MAC_RE.fullmatch(value)
    if match is None:
        return value

    octets = re.split(r"[:-]", value.lower())
    if policy.mac_mode == "4":
        octets = octets[-2:]
    elif policy.mac_mode == "6":
        octets = octets[-3:]
    return ":".join(octets)


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

    identity = re.search(r"\bidentity:\s+device=([^\s]+)\s+role=([^\s]+)(?:\s+role_source=([^\s]+))?", message, re.IGNORECASE)
    device_mac = identity.group(1) if identity and _MAC_RE.fullmatch(identity.group(1)) else None
    role = identity.group(2).lower() if identity else None
    if role == "gw":
        role = "gateway"
    role_source_match = _ROLE_SOURCE_RE.search(message)
    role_source = role_source_match.group(1).lower() if role_source_match else None
    role_match = _ROLE_RE.search(message)
    if role is None and role_match:
        role = role_match.group(1).lower()
        if role == "gw":
            role = "gateway"
    type_match = _TYPE_RE.search(message)
    message_type = int(type_match.group(1)) if type_match else None
    message_type_name = MESSAGE_TYPES.get(message_type) if message_type is not None else None
    if message_type is None:
        for value, name in MESSAGE_TYPES.items():
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", message, re.IGNORECASE):
                message_type, message_type_name = value, name
                break
    if message_type is None and re.search(r"(?<!\w)DATA_MESSAGE(?!\w)", message, re.IGNORECASE):
        message_type, message_type_name = 9, MESSAGE_TYPES[9]
    peer_match = _FROM_RE.search(message) or _TO_RE.search(message)
    peer_mac = peer_match.group(1) if peer_match else None
    direction = None
    if message_type in MESSAGE_TYPES:
        direction = "gateway_to_edge" if message_type in _GATEWAY_TO_EDGE else "edge_to_gateway"
    elif re.search(r"\b(?:DATA_MESSAGE|FAKE_DATA|ACK|send .* completed)\b", message, re.IGNORECASE):
        direction = None
    if message_type_name is not None and explanation is None:
        explanation = message_type_name
    elif explanation is None and re.search(r"\b(?:DATA_MESSAGE|FAKE_DATA|ACK|send .* completed)\b", message, re.IGNORECASE):
        explanation = "explicit diagnostic event"
    evidence: Literal["OBSERVED", "DECLARED", "UNKNOWN"] = "UNKNOWN"
    if identity and device_mac and role:
        evidence = "DECLARED"
    elif message_type is not None or peer_mac:
        evidence = "OBSERVED"
    return DeviceLine(
        severity, int(device_ms), component, message, explanation,
        device_mac, role, role_source, peer_mac, message_type, message_type_name,
        direction, evidence,
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
    policy: DisplayPolicy = DEFAULT_DISPLAY_POLICY,
    original_only: bool = False,
) -> Text:
    """Render raw evidence, optionally omitting the derived projection."""
    suffix = f" [{format_tags(tags)}]" if tags else ""
    prefix = f"{marker} " if marker else ""
    parsed = parse_device_line(line)
    if parsed is None:
        derived = "↳ Uninterpreted"
    else:
        if parsed.device_mac and parsed.role:
            role = "GW" if parsed.role == "gateway" else "EDGE"
            derived = (
                f"↳ {parsed.severity} | device={format_mac(parsed.device_mac, policy)} "
                f"| role={role} | role_source={(parsed.role_source or '?').upper()} "
                f"| evidence={parsed.evidence} | identity established"
            )
        elif parsed.role or parsed.role_source:
            role = "GW" if parsed.role == "gateway" else "EDGE" if parsed.role == "edge" else "?"
            derived = f"↳ {parsed.severity} | role={role} | role_source={(parsed.role_source or '?').upper()} | evidence={parsed.evidence}"
        elif parsed.message_type is not None or parsed.message_type_name or parsed.peer_mac:
            direction = parsed.direction or "unknown"
            src_role, dst_role = ("GW", "EDGE") if direction == "gateway_to_edge" else ("EDGE", "GW") if direction == "edge_to_gateway" else ("?", "?")
            src = f"{src_role}:{format_mac(parsed.peer_mac, policy) if parsed.peer_mac else '?'}"
            dst = f"{dst_role}:?"
            event = "HS" if parsed.message_type and parsed.message_type <= 5 else "DATA" if parsed.message_type in {6, 9, 11} else "ACK" if parsed.message_type in {8, 10, 13} else "EVT"
            type_text = f"type={parsed.message_type} {parsed.message_type_name or 'UNKNOWN'}"
            derived = f"↳ {parsed.severity} | src={src} | dst={dst} | {('RCV' if 'RX' in parsed.message.upper() else 'EVT')} | evt={event} | {type_text} | evidence={parsed.evidence}"
        else:
            explanation = f": {parsed.explanation}" if parsed.explanation else ""
            derived = f"↳ {parsed.severity} {parsed.component} | device elapsed: {parsed.device_ms} ms{explanation}"

    if original_only:
        rendered = f"{prefix}{timestamp} {port} | {line}{suffix}"
    elif parsed is not None and not policy.raw_lines:
        rendered = f"{prefix}{derived}{suffix}"
    else:
        rendered = f"{prefix}{timestamp} {port} | {line}{suffix}\n{derived}"

    # Text construction does not parse markup; callers must retain markup=False
    # when printing this renderable through Rich.
    text = Text(rendered)
    if not any(control in line for control in ("\x1b", "\r", "\n")):
        for pattern, style in HIGHLIGHTS:
            for match in pattern.finditer(text.plain):
                text.stylize(style, match.start(), match.end())
    return text

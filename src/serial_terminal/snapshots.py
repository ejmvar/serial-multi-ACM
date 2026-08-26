"""Tagged retained-history study snapshot helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .formatting import format_tags, sanitize_port
from .reader import PortEvent


@dataclass(frozen=True)
class SnapshotResult:
    """The paths and event counts written by one tagged-history export."""

    written: tuple[tuple[Path, int], ...]
    errors: tuple[str, ...]


def tagged_log_file_name(port: str) -> str:
    """Create a safe tagged snapshot name, such as ``ttyACM0-tagged.log``."""
    leaf = Path(port).name or port
    return f"{sanitize_port(leaf)}-tagged.log"


def snapshot_line(event: PortEvent) -> str:
    """Serialize an event with an explicit, stable tag field."""
    labels = format_tags(event.tags) or "-"
    return f"{event.timestamp} {event.text.rstrip()} [tags: {labels}]\n"


def save_tagged_snapshots(log_dir: Path, histories: Mapping[str, Sequence[PortEvent]]) -> SnapshotResult:
    """Write one non-overwriting tagged snapshot per retained port history."""
    written: list[tuple[Path, int]] = []
    errors: list[str] = []
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return SnapshotResult((), (f"Cannot create snapshot directory {log_dir}: {error}",))

    for port, events in histories.items():
        path = log_dir / tagged_log_file_name(port)
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.writelines(snapshot_line(event) for event in events)
        except FileExistsError:
            errors.append(f"Not saved (already exists): {path}")
        except OSError as error:
            errors.append(f"Could not save {path}: {error}")
        else:
            written.append((path, len(events)))
    return SnapshotResult(tuple(written), tuple(errors))

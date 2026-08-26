from pathlib import Path

from serial_terminal.reader import PortEvent
from serial_terminal.snapshots import save_tagged_snapshots, tagged_log_file_name


def event(port: str, text: str, tags: frozenset[str] = frozenset()) -> PortEvent:
    return PortEvent(port, "data", "2026-08-26T12:00:00.000+00:00", text, tags)


def test_tagged_snapshot_uses_safe_port_names_preserves_tags_and_never_overwrites(tmp_path: Path) -> None:
    histories = {
        "/dev/ttyACM0": [event("/dev/ttyACM0", "gateway forwarded", frozenset({"2", "a"}))],
        "/dev/ttyACM1": [event("/dev/ttyACM1", "edge received")],
    }

    result = save_tagged_snapshots(tmp_path, histories)

    assert tagged_log_file_name("/dev/ttyACM0") == "ttyACM0-tagged.log"
    assert [(path.name, count) for path, count in result.written] == [
        ("ttyACM0-tagged.log", 1),
        ("ttyACM1-tagged.log", 1),
    ]
    assert not result.errors
    assert (tmp_path / "ttyACM0-tagged.log").read_text() == "2026-08-26T12:00:00.000+00:00 gateway forwarded [tags: #2 #a]\n"
    assert (tmp_path / "ttyACM1-tagged.log").read_text() == "2026-08-26T12:00:00.000+00:00 edge received [tags: -]\n"

    repeated = save_tagged_snapshots(tmp_path, histories)

    assert not repeated.written
    assert len(repeated.errors) == 2
    assert "already exists" in repeated.errors[0]

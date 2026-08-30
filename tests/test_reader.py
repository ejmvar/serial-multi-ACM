from io import StringIO
from pathlib import Path

from serial_terminal import reader
from serial_terminal.reader import PortEvent, PortSettings, SerialReader


def test_emit_keeps_raw_port_event_text_and_disk_record(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(reader, "iso_timestamp", lambda: "2026-08-26T12:00:00.000+00:00")
    received: list[PortEvent] = []
    serial_reader = SerialReader("/dev/ttyACM0", PortSettings(), Path("log"), received.append)
    handle = StringIO()

    serial_reader._emit("data", "W (80) handshake: peer found", handle)

    assert received == [
        PortEvent(
            "/dev/ttyACM0",
            "data",
            "2026-08-26T12:00:00.000+00:00",
            "W (80) handshake: peer found",
        )
    ]
    assert handle.getvalue() == (
        "2026-08-26T12:00:00.000+00:00 /dev/ttyACM0 | W (80) handshake: peer found\n"
    )

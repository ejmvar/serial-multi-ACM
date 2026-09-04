from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import serial
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


def _port(device: str, *, vid: int = 0x1234, pid: int = 0x5678, serial_number: str = "serial", location: str = "1-2"):
    return SimpleNamespace(device=device, vid=vid, pid=pid, serial_number=serial_number, location=location)


def test_initial_open_failure_then_success(monkeypatch, tmp_path: Path) -> None:
    events: list[PortEvent] = []
    attempts = 0

    class Handle:
        is_open = True

        def readline(self) -> bytes:
            serial_reader.stop()
            return b"recovered\n"

        def close(self) -> None:
            self.is_open = False

    def open_serial(**kwargs):  # type: ignore[no-untyped-def]
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise serial.SerialException("not present")
        return Handle()

    monkeypatch.setattr(reader.serial, "Serial", open_serial)
    monkeypatch.setattr(reader.list_ports, "comports", lambda: [_port("/dev/ttyACM0")])
    serial_reader = SerialReader("/dev/ttyACM0", PortSettings(reconnect_delay=0.001), tmp_path, events.append)
    serial_reader.start()
    serial_reader.join(1)

    assert not serial_reader.is_alive()
    assert attempts == 2
    assert any(event.kind == "status" and event.text.startswith("Waiting for") for event in events)
    assert any(event.kind == "data" and event.text == "recovered" for event in events)


def test_read_disconnect_then_reconnect_keeps_log_and_logical_port(monkeypatch, tmp_path: Path) -> None:
    events: list[PortEvent] = []
    handles = []

    class Handle:
        is_open = True

        def __init__(self, line: bytes | None) -> None:
            self.line = line

        def readline(self) -> bytes:
            if self.line is None:
                raise serial.SerialException("device disconnected")
            line, self.line = self.line, None
            if line == b"after\n":
                serial_reader.stop()
            return line

        def close(self) -> None:
            self.is_open = False

    def open_serial(**kwargs):  # type: ignore[no-untyped-def]
        handle = Handle(b"before\n" if not handles else b"after\n")
        handles.append(handle)
        return handle

    monkeypatch.setattr(reader.serial, "Serial", open_serial)
    monkeypatch.setattr(reader.list_ports, "comports", lambda: [_port("/dev/ttyACM0")])
    serial_reader = SerialReader("/dev/ttyACM0", PortSettings(reconnect_delay=0.001), tmp_path, events.append)
    serial_reader.start()
    serial_reader.join(1)

    assert not serial_reader.is_alive()
    assert [event.text for event in events if event.kind == "data"] == ["before", "after"]
    assert any(event.text.startswith("Disconnected /dev/ttyACM0") for event in events)
    assert any(event.text == "Reconnected /dev/ttyACM0 via /dev/ttyACM0" for event in events)
    assert {event.port for event in events} == {"/dev/ttyACM0"}
    assert len(list(tmp_path.glob("*.log"))) == 1
    assert "before" in next(tmp_path.glob("*.log")).read_text()
    assert "after" in next(tmp_path.glob("*.log")).read_text()


def test_stop_during_wait_does_not_emit_error(monkeypatch, tmp_path: Path) -> None:
    events: list[PortEvent] = []

    def open_serial(**kwargs):  # type: ignore[no-untyped-def]
        raise serial.SerialException("missing")

    monkeypatch.setattr(reader.serial, "Serial", open_serial)
    monkeypatch.setattr(reader.list_ports, "comports", lambda: [])
    serial_reader = SerialReader("/dev/ttyACM0", PortSettings(reconnect_delay=10), tmp_path, events.append)
    serial_reader.start()
    while not events:
        pass
    serial_reader.stop()
    serial_reader.join(1)

    assert not serial_reader.is_alive()
    assert not any(event.kind == "error" for event in events)


def test_changed_tty_path_uses_unique_descriptor(monkeypatch, tmp_path: Path) -> None:
    events: list[PortEvent] = []
    calls: list[str] = []
    info = _port("/dev/ttyACM0")

    class Handle:
        is_open = True

        def readline(self) -> bytes:
            if len(calls) == 1:
                raise serial.SerialException("gone")
            serial_reader.stop()
            return b"continued\n"

        def close(self) -> None:
            self.is_open = False

    def open_serial(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs["port"])
        return Handle()

    discovery_calls = 0

    def comports():  # type: ignore[no-untyped-def]
        nonlocal discovery_calls
        discovery_calls += 1
        return [info] if discovery_calls == 1 else [_port("/dev/ttyACM7")]

    monkeypatch.setattr(reader.serial, "Serial", open_serial)
    monkeypatch.setattr(reader.list_ports, "comports", comports)
    serial_reader = SerialReader("/dev/ttyACM0", PortSettings(reconnect_delay=0.001), tmp_path, events.append)
    serial_reader.start()
    serial_reader.join(1)

    assert calls == ["/dev/ttyACM0", "/dev/ttyACM7"]
    assert any(event.text == "Reconnected /dev/ttyACM0 via /dev/ttyACM7" for event in events)
    assert all(event.port == "/dev/ttyACM0" for event in events)


def test_reconnect_ignores_reused_original_path(monkeypatch, tmp_path: Path) -> None:
    events: list[PortEvent] = []
    calls: list[str] = []

    class Handle:
        is_open = True

        def readline(self) -> bytes:
            if len(calls) == 1:
                raise serial.SerialException("gone")
            serial_reader.stop()
            return b"continued\n"

        def close(self) -> None:
            self.is_open = False

    def open_serial(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs["port"])
        return Handle()

    discovery_calls = 0

    def comports():  # type: ignore[no-untyped-def]
        nonlocal discovery_calls
        discovery_calls += 1
        if discovery_calls == 1:
            return [_port("/dev/ttyACM0")]
        return [
            _port("/dev/ttyACM0", serial_number="other-board"),
            _port("/dev/ttyACM7"),
        ]

    monkeypatch.setattr(reader.serial, "Serial", open_serial)
    monkeypatch.setattr(reader.list_ports, "comports", comports)
    serial_reader = SerialReader("/dev/ttyACM0", PortSettings(reconnect_delay=0.001), tmp_path, events.append)
    serial_reader.start()
    serial_reader.join(1)

    assert calls == ["/dev/ttyACM0", "/dev/ttyACM7"]
    assert "/dev/ttyACM0" not in calls[1:]
    assert any(event.text == "Reconnected /dev/ttyACM0 via /dev/ttyACM7" for event in events)
    assert all(event.port == "/dev/ttyACM0" for event in events)
    assert len(list(tmp_path.glob("*.log"))) == 1


def test_ambiguous_descriptor_match_does_not_guess(monkeypatch, tmp_path: Path) -> None:
    events: list[PortEvent] = []
    calls = 0

    class Handle:
        is_open = True

        def readline(self) -> bytes:
            raise serial.SerialException("gone")

        def close(self) -> None:
            self.is_open = False

    def open_serial(**kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return Handle()

    discovery_calls = 0

    def comports():  # type: ignore[no-untyped-def]
        nonlocal discovery_calls
        discovery_calls += 1
        if discovery_calls == 1:
            return [_port("/dev/ttyACM0")]
        return [_port("/dev/ttyACM1"), _port("/dev/ttyACM2")]

    monkeypatch.setattr(reader.serial, "Serial", open_serial)
    monkeypatch.setattr(reader.list_ports, "comports", comports)
    def receive(event: PortEvent) -> None:
        events.append(event)
        if "no unique matching device" in event.text:
            serial_reader.stop()

    serial_reader = SerialReader("/dev/ttyACM0", PortSettings(reconnect_delay=0.001), tmp_path, receive)
    serial_reader.start()
    serial_reader.join(1)

    assert calls == 1
    assert any("no unique matching device" in event.text for event in events)
    assert any("/dev/ttyACM1" in event.text and "/dev/ttyACM2" in event.text for event in events)

"""Threaded serial readers that keep disk logging independent from the UI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import threading

import serial

from .formatting import iso_timestamp, log_file_name


@dataclass(frozen=True)
class PortSettings:
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 0.25


@dataclass(frozen=True)
class PortEvent:
    port: str
    kind: str
    timestamp: str
    text: str


EventCallback = Callable[[PortEvent], None]


class SerialReader(threading.Thread):
    """Read one serial port in a daemon thread and append every event to disk."""

    def __init__(self, port: str, settings: PortSettings, log_dir: Path, callback: EventCallback) -> None:
        super().__init__(name=f"serial-reader-{port}", daemon=True)
        self.port = port
        self.settings = settings
        self.log_dir = log_dir
        self.callback = callback
        self.stop_requested = threading.Event()
        self._serial: serial.Serial | None = None

    def stop(self) -> None:
        self.stop_requested.set()
        if self._serial and self._serial.is_open:
            self._serial.close()

    def _emit(self, kind: str, text: str, log_handle) -> None:  # type: ignore[no-untyped-def]
        event = PortEvent(self.port, kind, iso_timestamp(), text)
        log_handle.write(f"{event.timestamp} {event.port} | {event.text.rstrip()}\n")
        log_handle.flush()
        self.callback(event)

    def run(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / log_file_name(self.port)
        with log_path.open("a", encoding="utf-8") as log_handle:
            try:
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.settings.baudrate,
                    bytesize=self.settings.bytesize,
                    parity=self.settings.parity,
                    stopbits=self.settings.stopbits,
                    timeout=self.settings.timeout,
                )
                self._emit("status", f"Opened {self.port}; logging to {log_path}", log_handle)
                while not self.stop_requested.is_set():
                    raw = self._serial.readline()
                    if raw:
                        self._emit("data", raw.decode("utf-8", errors="replace").rstrip("\r\n"), log_handle)
            except (serial.SerialException, OSError) as error:
                self._emit("error", f"Port error: {error}", log_handle)
            finally:
                if self._serial and self._serial.is_open:
                    self._serial.close()

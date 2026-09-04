"""Threaded serial readers that keep disk logging independent from the UI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import threading

import serial
from serial.tools import list_ports

from .formatting import iso_timestamp, log_file_name


@dataclass(frozen=True)
class PortSettings:
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 0.25
    reconnect_delay: float = 1.0


@dataclass(frozen=True)
class PortEvent:
    port: str
    kind: str
    timestamp: str
    text: str
    tags: frozenset[str] = field(default_factory=frozenset)


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
        self._usb_descriptor: tuple[object, ...] | None = None

    def stop(self) -> None:
        self.stop_requested.set()
        if self._serial and self._serial.is_open:
            self._serial.close()

    def _emit(self, kind: str, text: str, log_handle) -> None:  # type: ignore[no-untyped-def]
        event = PortEvent(self.port, kind, iso_timestamp(), text)
        log_handle.write(f"{event.timestamp} {event.port} | {event.text.rstrip()}\n")
        log_handle.flush()
        self.callback(event)

    @staticmethod
    def _descriptor(info) -> tuple[object, ...]:  # type: ignore[no-untyped-def]
        return (info.vid, info.pid, info.serial_number, info.location)

    @staticmethod
    def _available_ports(infos) -> list[str]:  # type: ignore[no-untyped-def]
        return sorted(
            info.device
            for info in infos
            if info.device.startswith(("/dev/ttyACM", "/dev/ttyUSB"))
        )

    def _port_infos(self):  # type: ignore[no-untyped-def]
        try:
            return list_ports.comports()
        except (serial.SerialException, OSError):
            return []

    def _reconnect_path(self) -> tuple[str | None, list[str]]:
        infos = self._port_infos()
        available = self._available_ports(infos)
        if self._usb_descriptor is None:
            return self.port, available
        original = next((info for info in infos if info.device == self.port), None)
        if original is not None and self._descriptor(original) == self._usb_descriptor:
            return self.port, available
        matches = [info.device for info in infos if self._descriptor(info) == self._usb_descriptor]
        return (matches[0] if len(matches) == 1 else None), available

    def _close_serial(self) -> None:
        handle = self._serial
        self._serial = None
        if handle is not None and getattr(handle, "is_open", False):
            handle.close()

    def run(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / log_file_name(self.port)
        with log_path.open("a", encoding="utf-8") as log_handle:
            first_attempt = True
            while not self.stop_requested.is_set():
                available: list[str] = []
                active_path = self.port
                if not first_attempt:
                    active_path, available = self._reconnect_path()
                    if active_path is None:
                        self._emit(
                            "status",
                            f"Waiting for {self.port}; available={available or '<none>'}; "
                            "no unique matching device",
                            log_handle,
                        )
                        self.stop_requested.wait(self.settings.reconnect_delay)
                        continue
                try:
                    self._serial = serial.Serial(
                        port=active_path,
                        baudrate=self.settings.baudrate,
                        bytesize=self.settings.bytesize,
                        parity=self.settings.parity,
                        stopbits=self.settings.stopbits,
                        timeout=self.settings.timeout,
                    )
                    if first_attempt:
                        info = next((item for item in self._port_infos() if item.device == active_path), None)
                        if info is not None:
                            self._usb_descriptor = self._descriptor(info)
                        self._emit("status", f"Opened {self.port}; logging to {log_path}", log_handle)
                    else:
                        self._emit("status", f"Reconnected {self.port} via {active_path}", log_handle)
                    first_attempt = False
                    while not self.stop_requested.is_set():
                        raw = self._serial.readline()
                        if raw:
                            self._emit("data", raw.decode("utf-8", errors="replace").rstrip("\r\n"), log_handle)
                except (serial.SerialException, OSError) as error:
                    if not self.stop_requested.is_set():
                        if not available:
                            available = self._available_ports(self._port_infos())
                        if first_attempt:
                            kind = "status"
                            message = (
                                f"Waiting for {self.port}; available={available or '<none>'}; "
                                f"open via {active_path} failed: {error}"
                            )
                        else:
                            kind = "error"
                            message = (
                                f"Disconnected {self.port} via {active_path}: {error}; "
                                f"available={available or '<none>'}"
                            )
                        self._emit(
                            kind,
                            message,
                            log_handle,
                        )
                finally:
                    self._close_serial()
                if not self.stop_requested.is_set():
                    self.stop_requested.wait(self.settings.reconnect_delay)

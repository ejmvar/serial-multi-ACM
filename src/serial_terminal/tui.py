"""Textual application for observing several serial readers safely."""

from __future__ import annotations

from pathlib import Path
import re

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Footer, Header, Input, Label, RichLog, Static

from .filters import LineFilter, is_visible
from .formatting import render_record
from .reader import PortEvent, PortSettings, SerialReader


class PortView(Static):
    """The independently pausable visual panel for one serial port."""

    can_focus = True

    def __init__(self, port: str) -> None:
        super().__init__(classes="port-panel")
        self.port = port
        self.paused = False
        self.zoomed = False

    def compose(self) -> ComposeResult:
        yield Label(self.port, classes="port-title")
        yield RichLog(wrap=True, markup=False, highlight=False)

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        self._update_title()

    def set_zoomed(self, zoomed: bool) -> None:
        self.zoomed = zoomed
        self.set_class(zoomed, "zoomed")
        self._update_title()

    def on_focus(self) -> None:
        if isinstance(self.app, TerminalApp):
            self.app.select_port(self.port)

    def _update_title(self) -> None:
        suffixes = ["[ZOOMED]" if self.zoomed else "", "[PAUSED]" if self.paused else ""]
        self.query_one(Label).update(" ".join(part for part in [self.port, *suffixes] if part))

    def write_event(self, event: PortEvent) -> None:
        self.query_one(RichLog).write(render_record(event.timestamp, event.port, event.text))


class TerminalApp(App[None]):
    """Thread-safe multi-port serial terminal."""

    CSS = """
    #panels { height: 1fr; layout: horizontal; }
    .port-panel { width: 1fr; height: 1fr; border: round $accent; }
    .port-panel:focus { border: heavy $success; }
    #panels.zoomed .port-panel { display: none; }
    #panels.zoomed .port-panel.zoomed { display: block; width: 1fr; border: heavy $warning; }
    .port-title { text-style: bold; padding: 0 1; }
    RichLog { height: 1fr; }
    #filter { dock: bottom; display: none; }
    #filter.visible { display: block; }
    #status { dock: bottom; height: 1; padding-left: 1; }
    """
    BINDINGS = [
        Binding("space", "toggle_global_pause", "Pause all"),
        Binding("p", "toggle_port_pause", "Pause port"),
        Binding("f", "edit_global_filter", "Global filter"),
        Binding("F", "edit_port_filter", "Port filter"),
        Binding("z", "toggle_zoom", "Zoom port"),
        Binding("escape", "cancel_filter", "Cancel filter"),
        Binding("q", "quit", "Quit"),
    ]

    class ReaderUpdate(Message):
        def __init__(self, event: PortEvent) -> None:
            super().__init__()
            self.event = event

    def __init__(self, ports: list[str], settings: PortSettings, log_dir: Path) -> None:
        super().__init__()
        self.ports = ports
        self.settings = settings
        self.log_dir = log_dir
        self.global_paused = False
        self.selected_port = ports[0]
        self.global_filter: LineFilter | None = None
        self.port_filters: dict[str, LineFilter | None] = {port: None for port in ports}
        self.filter_target: str | None = None
        self.zoomed_port: str | None = None
        self.readers: list[SerialReader] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="panels"):
            for port in self.ports:
                yield PortView(port)
        yield Input(placeholder="Filter text, or /regex/", id="filter")
        yield Label("Ready. Focus a port with Tab or 1-9.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._port_view(self.selected_port).focus()
        self.readers = [SerialReader(port, self.settings, self.log_dir, self._receive_from_reader) for port in self.ports]
        for reader in self.readers:
            reader.start()

    def _receive_from_reader(self, event: PortEvent) -> None:
        """post_message is Textual's thread-safe bridge to the UI thread."""
        self.post_message(self.ReaderUpdate(event))

    def on_terminal_app_reader_update(self, message: ReaderUpdate) -> None:
        event = message.event
        if event.kind == "error":
            self._status(f"{event.port}: {event.text}")
        if self.global_paused:
            return
        view = self._port_view(event.port)
        if not view.paused and is_visible(event.text, self.global_filter, self.port_filters[event.port]):
            view.write_event(event)

    def _port_view(self, port: str) -> PortView:
        return next(view for view in self.query(PortView) if view.port == port)

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key.isdigit() and event.key != "0":
            index = int(event.key) - 1
            if index < len(self.ports):
                self._port_view(self.ports[index]).focus()
                event.stop()

    def select_port(self, port: str) -> None:
        self.selected_port = port
        self._status(f"Selected {port}")

    def action_toggle_global_pause(self) -> None:
        self.global_paused = not self.global_paused
        self._status("All visual panels paused; disk logging continues." if self.global_paused else "All visual panels resumed.")

    def action_toggle_port_pause(self) -> None:
        view = self._port_view(self.selected_port)
        view.set_paused(not view.paused)
        self._status(f"{self.selected_port} visual display {'paused' if view.paused else 'resumed'}; disk logging continues.")

    def action_toggle_zoom(self) -> None:
        panels = self.query_one("#panels", Horizontal)
        if self.zoomed_port:
            self._port_view(self.zoomed_port).set_zoomed(False)
            panels.remove_class("zoomed")
            self._status(f"Restored side-by-side layout from {self.zoomed_port}.")
            self.zoomed_port = None
            return
        self.zoomed_port = self.selected_port
        self._port_view(self.zoomed_port).set_zoomed(True)
        panels.add_class("zoomed")
        self._status(f"Zoomed {self.zoomed_port}. Press z or Escape to restore the layout.")

    def action_edit_global_filter(self) -> None:
        self._show_filter("global", self.global_filter.source if self.global_filter else "")

    def action_edit_port_filter(self) -> None:
        current = self.port_filters[self.selected_port]
        self._show_filter(self.selected_port, current.source if current else "")

    def _show_filter(self, target: str, value: str) -> None:
        self.filter_target = target
        input_ = self.query_one(Input)
        input_.value = value
        input_.add_class("visible")
        input_.focus()
        self._status(f"Editing {'global' if target == 'global' else target} filter. Empty clears; /.../ is regex.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.filter_target is None:
            return
        try:
            parsed = LineFilter.parse(event.value)
        except re.error as error:
            self._status(f"Invalid regular expression: {error}")
            return
        if self.filter_target == "global":
            self.global_filter = parsed
        else:
            self.port_filters[self.filter_target] = parsed
        self._status("Filter updated. It applies to new visual lines; disk logging is unchanged.")
        self.action_cancel_filter()

    def action_cancel_filter(self) -> None:
        if self.filter_target is None:
            if self.zoomed_port:
                self.action_toggle_zoom()
            return
        self.filter_target = None
        input_ = self.query_one(Input)
        input_.remove_class("visible")
        self.set_focus(None)

    def _status(self, text: str) -> None:
        self.query_one("#status", Label).update(text)

    def on_unmount(self) -> None:
        for reader in self.readers:
            reader.stop()

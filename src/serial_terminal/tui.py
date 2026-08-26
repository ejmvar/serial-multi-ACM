"""Textual application for observing several serial readers safely."""

from __future__ import annotations

from dataclasses import replace
from functools import partial
from pathlib import Path
import re

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Footer, Header, Input, Label, RichLog, Static
from textual.worker import Worker, WorkerState

from .filters import LineFilter, is_visible
from .formatting import render_record
from .reader import PortEvent, PortSettings, SerialReader
from .search import ContextBounds, SearchMatch, context_window, find_matches
from .snapshots import SnapshotResult, save_tagged_snapshots


class PortView(Static):
    """The independently pausable visual panel for one serial port."""

    can_focus = True

    def __init__(self, port: str) -> None:
        super().__init__(classes="port-panel")
        self.port = port
        self.paused = False
        self.zoomed = False
        self.history: list[PortEvent] = []

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
        self.history.append(event)
        if len(self.history) > 5_000:
            del self.history[:-5_000]
        self.query_one(RichLog).write(render_record(event.timestamp, event.port, event.text, event.tags))

    def replace_event(self, index: int, event: PortEvent) -> None:
        """Replace one retained record after its user-assigned tags change."""
        self.history[index] = event

    def show_context(self, timestamp: str, bounds: ContextBounds) -> None:
        """Replace the panel with retained lines surrounding *timestamp*."""
        log = self.query_one(RichLog)
        events, offset = context_window(self.history, timestamp, bounds)
        log.clear()
        for event in events:
            log.write(render_record(event.timestamp, event.port, event.text, event.tags))
        log.scroll_to(y=offset, animate=False, force=True)

    def show_history(self) -> None:
        """Restore the normal retained visual history after leaving search."""
        log = self.query_one(RichLog)
        log.clear()
        for event in self.history:
            log.write(render_record(event.timestamp, event.port, event.text, event.tags))


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
        Binding("P", "toggle_port_pause", "Pause port"),
        Binding("f", "edit_search", "Find history"),
        Binding("g", "edit_global_filter", "Global filter"),
        Binding("p", "edit_port_filter", "Port filter"),
        Binding("a", "edit_after_context", "After context"),
        Binding("b", "edit_before_context", "Before context"),
        Binding("t", "start_numeric_tag", "Tag 1-9"),
        Binding("T", "start_letter_tag", "Tag a-z"),
        Binding("u", "start_numeric_untag", "Untag 1-9"),
        Binding("U", "start_letter_untag", "Untag a-z"),
        Binding("S", "save_tagged_snapshot", "Save tagged study"),
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
        self.search_filter: LineFilter | None = None
        self.search_matches: list[SearchMatch] = []
        self.search_index = 0
        self.global_context = ContextBounds()
        self.port_contexts: dict[str, ContextBounds] = {port: ContextBounds() for port in ports}
        self.context_target: str | None = None
        self.tag_mode: tuple[str, bool] | None = None
        self.readers: list[SerialReader] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="panels"):
            for port in self.ports:
                yield PortView(port)
        yield Input(placeholder="Find text, or /regex/", id="filter")
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
        if self.filter_target is not None:
            return
        if self.tag_mode is not None:
            kind, removing = self.tag_mode
            valid = event.key in "123456789" if kind == "numeric" else len(event.key) == 1 and event.key.isascii() and event.key.islower()
            if valid:
                self._change_active_tag(event.key, removing)
                event.stop()
            else:
                self._status(f"Waiting for a {'1-9' if kind == 'numeric' else 'lowercase a-z'} tag; Escape cancels.")
                event.stop()
            return
        if event.key.isdigit() and event.key != "0":
            index = int(event.key) - 1
            if index < len(self.ports):
                port = self.ports[index]
                if self.zoomed_port == port:
                    self.action_toggle_zoom()
                else:
                    self._port_view(port).focus()
                    if self.zoomed_port:
                        self.action_toggle_zoom()
                event.stop()
            return
        if self.context_target:
            adjustments = {"j": 1, "k": -1, "h": -5, "l": 5}
            if event.key in adjustments:
                self._adjust_context(adjustments[event.key])
                event.stop()
            return
        if self.search_matches and event.key in {"j", "k"}:
            self.search_index = (self.search_index + (1 if event.key == "j" else -1)) % len(self.search_matches)
            self._show_search_result()
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

    def action_edit_search(self) -> None:
        self._show_filter("search", self.search_filter.source if self.search_filter else "")

    def action_edit_after_context(self) -> None:
        self._activate_context("after")

    def action_edit_before_context(self) -> None:
        self._activate_context("before")

    def action_start_numeric_tag(self) -> None:
        self._start_tag_mode("numeric", removing=False)

    def action_start_letter_tag(self) -> None:
        self._start_tag_mode("letter", removing=False)

    def action_start_numeric_untag(self) -> None:
        self._start_tag_mode("numeric", removing=True)

    def action_start_letter_untag(self) -> None:
        self._start_tag_mode("letter", removing=True)

    def action_save_tagged_snapshot(self) -> None:
        histories = {view.port: tuple(view.history) for view in self.query(PortView)}
        self._status("Saving tagged retained-history snapshots in the background.")
        self.run_worker(partial(save_tagged_snapshots, self.log_dir, histories), thread=True, name="tagged-snapshot")

    def _active_event(self) -> tuple[PortView, int, PortEvent] | None:
        if self.search_filter is not None:
            if not self.search_matches:
                return None
            match = self.search_matches[self.search_index]
            view = self._port_view(match.port)
            return view, match.index, view.history[match.index]
        view = self._port_view(self.selected_port)
        if not view.history:
            return None
        index = len(view.history) - 1
        return view, index, view.history[index]

    def _start_tag_mode(self, kind: str, removing: bool) -> None:
        if self._active_event() is None:
            self._status("No active retained event: find a match or select a port with displayed history.")
            return
        self.tag_mode = (kind, removing)
        verb = "remove" if removing else "assign"
        choices = "1-9" if kind == "numeric" else "lowercase a-z"
        self._status(f"Tag mode: press {choices} to {verb} that tag on the active event; Escape cancels.")

    def _change_active_tag(self, tag: str, removing: bool) -> None:
        active = self._active_event()
        self.tag_mode = None
        if active is None:
            self._status("No active retained event; tag mode cancelled.")
            return
        view, index, record = active
        tags = record.tags - {tag} if removing else record.tags | {tag}
        if tags == record.tags:
            self._status(f"#{tag} was already {'absent from' if removing else 'on'} the active event.")
            return
        view.replace_event(index, replace(record, tags=frozenset(tags)))
        self._refresh_after_tag_change(view.port, index)
        self._status(f"{'Removed' if removing else 'Assigned'} #{tag} on {view.port} at {record.timestamp}.")

    def _refresh_after_tag_change(self, port: str, index: int) -> None:
        if self.search_filter is None:
            self._port_view(port).show_history()
            return
        self.search_matches = find_matches({view.port: view.history for view in self.query(PortView)}, self.search_filter)
        for match_index, match in enumerate(self.search_matches):
            if (match.port, match.index) == (port, index):
                self.search_index = match_index
                self._show_search_result()
                return
        if self.search_matches:
            self.search_index = min(self.search_index, len(self.search_matches) - 1)
            self._show_search_result()
        else:
            for view in self.query(PortView):
                view.show_history()

    def _show_filter(self, target: str, value: str) -> None:
        self.filter_target = target
        input_ = self.query_one(Input)
        input_.value = value
        input_.add_class("visible")
        input_.focus()
        if target == "search":
            self._status("Searching retained display history. Empty clears; /.../ is regex. j/k navigate results.")
        else:
            self._status(f"Editing {'global' if target == 'global' else target} live filter. Empty clears; /.../ is regex.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.filter_target is None:
            return
        try:
            parsed = LineFilter.parse(event.value)
        except re.error as error:
            self._status(f"Invalid regular expression: {error}")
            return
        if self.filter_target == "search":
            self.search_filter = parsed
            self.search_matches = find_matches({view.port: view.history for view in self.query(PortView)}, parsed) if parsed else []
            self.search_index = 0
            if self.search_matches:
                self._show_search_result()
            else:
                self._status("No retained displayed-history matches. Live filters and logging are unchanged.")
        elif self.filter_target == "global":
            self.global_filter = parsed
        else:
            self.port_filters[self.filter_target] = parsed
        if self.filter_target != "search":
            self._status("Live filter updated. It applies to new visual lines; disk logging is unchanged.")
        self.action_cancel_filter()

    def action_cancel_filter(self) -> None:
        if self.tag_mode is not None:
            self.tag_mode = None
            self._status("Tag mode cancelled.")
            return
        if self.context_target:
            self.context_target = None
            self._status("Context adjustment off. j/k navigate search results.")
            return
        if self.filter_target is None:
            if self.search_filter:
                self.search_filter = None
                self.search_matches = []
                for view in self.query(PortView):
                    view.show_history()
                self._status("Search cleared; retained visual history restored.")
                return
            if self.zoomed_port:
                self.action_toggle_zoom()
            return
        self.filter_target = None
        input_ = self.query_one(Input)
        input_.remove_class("visible")
        self.set_focus(None)

    def _active_context(self) -> ContextBounds:
        return self.port_contexts[self.selected_port] if self.zoomed_port else self.global_context

    def _activate_context(self, target: str) -> None:
        if not self.search_matches:
            self._status("Find retained history with f before adjusting context.")
            return
        self.context_target = target
        bounds = self._active_context()
        self._status(f"Adjusting {target.upper()} context: before={bounds.before}, after={bounds.after}; j/k +/-1, h/l -/+5, Escape exits.")

    def _adjust_context(self, amount: int) -> None:
        assert self.context_target is not None
        if self.zoomed_port:
            self.port_contexts[self.selected_port] = self._active_context().adjusted(self.context_target, amount)
        else:
            self.global_context = self._active_context().adjusted(self.context_target, amount)
        self._show_search_result()

    def _show_search_result(self) -> None:
        match = self.search_matches[self.search_index]
        for view in self.query(PortView):
            if view.display:
                bounds = self.port_contexts[view.port] if self.zoomed_port else self.global_context
                view.show_context(match.timestamp, bounds)
        bounds = self._active_context()
        mode = f" Adjusting {self.context_target.upper()}: j/k +/-1, h/l -/+5." if self.context_target else " j/k navigate; a/b adjust context."
        self._status(f"Find {self.search_index + 1}/{len(self.search_matches)} at {match.timestamp} ({match.port}); before={bounds.before}, after={bounds.after}.{mode}")

    def _status(self, text: str) -> None:
        self.query_one("#status", Label).update(text)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "tagged-snapshot":
            return
        if event.state == WorkerState.SUCCESS:
            result = event.worker.result
            assert isinstance(result, SnapshotResult)
            saved = ", ".join(f"{path} ({count} events)" for path, count in result.written) or "none"
            errors = "; ".join(result.errors)
            self._status(f"Tagged snapshots saved: {saved}." + (f" Errors: {errors}" if errors else ""))
        elif event.state == WorkerState.ERROR:
            self._status(f"Tagged snapshot failed: {event.worker.error}")

    def on_unmount(self) -> None:
        for reader in self.readers:
            reader.stop()

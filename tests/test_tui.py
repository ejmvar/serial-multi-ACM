import asyncio
from io import StringIO
from pathlib import Path

from textual.containers import Horizontal
from textual.widgets import Label, RichLog

from serial_terminal.filters import LineFilter
from serial_terminal.reader import PortEvent, PortSettings, SerialReader
from serial_terminal.snapshots import save_tagged_snapshots
from serial_terminal.tui import PortView, TerminalApp, resolve_marker


def test_resolve_marker_combines_latest_and_selected_identity() -> None:
    latest = ("port", 2)
    assert resolve_marker(latest, latest, latest) == "+-"
    assert resolve_marker(("port", 1), latest, latest) == ""
    assert resolve_marker(latest, latest, ("other", 0)) == "-"
    assert resolve_marker(("port", 1), latest, ("port", 1)) == "+"


def test_live_event_projection_does_not_rebuild_retained_history(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["port"], PortSettings(), tmp_path)
    projection_sizes: list[int] = []

    async def exercise() -> None:
        async with app.run_test():
            view = app.query_one(PortView)
            view.write_event(PortEvent("port", "data", "0", "event-0"))
            view.write_event(PortEvent("port", "data", "1", "event-1"))
            assert view.marker_texts() == ["- 1 port | event-1"]
            monkeypatch.setattr(
                view,
                "_projection",
                lambda events, selected=None: projection_sizes.append(len(events)),
            )
            for index in range(2, 5_001):
                view.write_event(PortEvent("port", "data", str(index), f"event-{index}"))

            assert len(view.history) == 5_000
            assert sum(projection_sizes) <= 10_001
            assert max(projection_sizes, default=0) <= 5_000

    asyncio.run(exercise())


def test_port_projection_keeps_wrapped_event_marker_on_retained_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["port"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test() as pilot:
            view = app.query_one(PortView)
            view.write_event(PortEvent("port", "data", "2026-08-25T00:00:00+00:00", "I (1) boot: first"))
            view.write_event(
                PortEvent(
                    "port",
                    "data",
                    "2026-08-25T00:00:01+00:00",
                    "W (80) handshake: " + "needle " * 30,
                    frozenset({"a"}),
                )
            )
            view.show_context(view.history[1].timestamp, app.global_context, selected=("port", 1))
            rendered = [line.text for line in view.query_one(RichLog).lines]
            assert any(line.startswith(("+ ", "+- ")) and "W (80)" in line for line in rendered)
            assert any("[#a]" in line for line in rendered)
            assert any(line.startswith("↳ WARN handshake | device elapsed: 80 ms") for line in rendered)
            assert len(view.marker_texts()) == 1
            assert not any(line.startswith(("+ ", "+- ")) and "first" in line for line in rendered)
            await pilot.pause()

    asyncio.run(exercise())


def test_live_reconciliation_moves_latest_marker_only_for_admitted_events(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["port"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test() as pilot:
            view = app.query_one(PortView)
            app.post_message(app.ReaderUpdate(PortEvent("port", "data", "2026-08-25T00:00:00+00:00", "accepted")))
            await pilot.pause()
            assert view.marker_texts()[0].endswith("| accepted")
            app.global_filter = app.global_filter or __import__("serial_terminal.filters", fromlist=["LineFilter"]).LineFilter.parse("keep")
            app.post_message(app.ReaderUpdate(PortEvent("port", "data", "2026-08-25T00:00:01+00:00", "discarded")))
            await pilot.pause()
            assert view.marker_texts()[0].endswith("| accepted")
            view.set_paused(True)
            app.post_message(app.ReaderUpdate(PortEvent("port", "data", "2026-08-25T00:00:02+00:00", "paused")))
            await pilot.pause()
            assert view.marker_texts()[0].endswith("| accepted")

    asyncio.run(exercise())


def test_find_marker_is_exact_across_ties_and_zoom_visibility(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["a", "b"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test() as pilot:
            first, second = app.query(PortView)
            for view in (first, second):
                app.post_message(app.ReaderUpdate(PortEvent(view.port, "data", "2026-08-25T00:00:00+00:00", "needle")))
            await pilot.pause()
            await pilot.press("f", *"needle", "enter")
            assert app.search_matches[app.search_index].port == "a"
            assert any(line.startswith(("+ ", "+- ")) for line in first.marker_texts())
            assert not any(line.startswith(("+ ", "+- ")) for line in second.marker_texts())
            await pilot.press("j")
            assert any(line.startswith(("+ ", "+- ")) for line in second.marker_texts())
            assert not any(line.startswith(("+ ", "+- ")) for line in first.marker_texts())
            second.focus()
            await pilot.press("z")
            assert not first.display
            assert not any(line.startswith(("+ ", "+- ")) for line in first.marker_texts())
            await pilot.press("escape", "escape")
            assert first.display and second.display

    asyncio.run(exercise())


def test_focus_zoom_restores_layout_and_keeps_port_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["/dev/ttyACM0", "/dev/ttyACM1"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test() as pilot:
            first, second = app.query(PortView)
            assert app.focused is first

            second.focus()
            await pilot.pause()
            assert app.selected_port == "/dev/ttyACM1"

            await pilot.press("z")
            panels = app.query_one("#panels", Horizontal)
            assert app.zoomed_port == "/dev/ttyACM1"
            assert panels.has_class("zoomed")
            assert second.has_class("zoomed")
            assert not first.display
            assert second.display

            app.post_message(app.ReaderUpdate(PortEvent(second.port, "data", "2026-08-25T00:00:00+00:00", "selected")))
            app.post_message(app.ReaderUpdate(PortEvent(first.port, "data", "2026-08-25T00:00:00+00:00", "hidden")))
            await pilot.pause()
            assert len(second.query_one(RichLog).lines) == 2
            assert len(first.query_one(RichLog).lines) == 2

            await pilot.press("escape")
            assert app.zoomed_port is None
            assert not panels.has_class("zoomed")
            assert not second.has_class("zoomed")
            assert first.display

            await pilot.press("z")
            assert app.zoomed_port == "/dev/ttyACM1"
            await pilot.press("z")
            assert app.zoomed_port is None
            assert not panels.has_class("zoomed")

    asyncio.run(exercise())


def test_find_context_scope_navigation_and_numeric_zoom_toggle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["/dev/ttyACM0", "/dev/ttyACM1"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test() as pilot:
            first, second = app.query(PortView)
            for view in (first, second):
                for number in range(3):
                    app.post_message(app.ReaderUpdate(PortEvent(view.port, "data", f"2026-08-25T00:00:0{number}+00:00", f"needle {number}")))
            await pilot.pause()

            await pilot.press("f")
            await pilot.press(*"needle", "enter")
            assert len(app.search_matches) == 6
            assert app.search_index == 0
            await pilot.press("j")
            assert app.search_index == 1

            await pilot.press("a", "l")
            assert app.global_context.after == 15
            assert app.port_contexts[second.port].after == 10
            await pilot.press("escape")

            await pilot.press("2")
            assert app.selected_port == second.port
            assert app.zoomed_port is None
            await pilot.press("z")
            assert app.zoomed_port == second.port
            await pilot.press("b", "h")
            assert app.port_contexts[second.port].before == 5
            assert app.global_context.before == 10
            await pilot.press("escape", "2")
            assert app.zoomed_port is None

    asyncio.run(exercise())


def test_tag_modes_update_active_search_record_and_cancel(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["/dev/ttyACM0", "/dev/ttyACM1"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test() as pilot:
            first, second = app.query(PortView)
            app.post_message(app.ReaderUpdate(PortEvent(first.port, "data", "2026-08-26T00:00:00+00:00", "gateway forwarded")))
            app.post_message(app.ReaderUpdate(PortEvent(second.port, "data", "2026-08-26T00:00:01+00:00", "edge received")))
            await pilot.pause()

            await pilot.press("t", "1")
            assert first.history[-1].tags == frozenset({"1"})
            await pilot.press("T", "a")
            assert first.history[-1].tags == frozenset({"1", "a"})
            await pilot.press("u", "1")
            assert first.history[-1].tags == frozenset({"a"})
            await pilot.press("U", "a")
            assert first.history[-1].tags == frozenset()

            await pilot.press("t", "escape")
            assert app.tag_mode is None
            assert "cancelled" in app.query_one("#status", Label).render().plain.lower()

            await pilot.press("T", "a")
            await pilot.press("2", "T", "a")
            await pilot.press("f", *"#a", "enter")
            assert [(match.port, match.index) for match in app.search_matches] == [(first.port, 0), (second.port, 0)]
            await pilot.press("j")
            assert app.search_matches[app.search_index].port == second.port
            await pilot.press("U", "a")
            assert second.history[-1].tags == frozenset()
            assert [(match.port, match.index) for match in app.search_matches] == [(first.port, 0)]

            await pilot.press("S")
            await pilot.pause(0.1)
            assert (tmp_path / "ttyACM0-tagged.log").exists()
            assert (tmp_path / "ttyACM1-tagged.log").exists()

    asyncio.run(exercise())


def test_empty_history_projection_contains_no_marker(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["port"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test():
            view = app.query_one(PortView)
            view.show_history()
            assert view.query_one(RichLog).lines == []
            assert view.marker_texts() == []

    asyncio.run(exercise())


def test_retention_eviction_recovers_selected_marker_end_to_end(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["port"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test():
            view = app.query_one(PortView)
            view.history = [
                PortEvent("port", "data", f"2026-08-25T00:00:{index:04d}+00:00", f"needle-{index}")
                for index in range(5_000)
            ]
            app.search_filter = LineFilter.parse("needle")
            app._reconcile_selection()
            assert (app.search_matches[app.search_index].port, app.search_matches[app.search_index].index) == ("port", 0)

            app.on_terminal_app_reader_update(
                app.ReaderUpdate(PortEvent("port", "data", "2026-08-25T01:23:45+00:00", "needle-new"))
            )

            assert len(view.history) == 5_000
            selected = app.search_matches[app.search_index]
            assert (selected.port, selected.index) == ("port", 0)
            assert any(line.startswith("+ ") and "needle-1" in line for line in view.marker_texts())
            assert not any("needle-0" in line for line in view.marker_texts())

            view.show_history()
            assert len(view.query_one(RichLog).lines) == 10_000

    asyncio.run(exercise())


def test_tag_change_and_redraw_preserve_marker_owners(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["port"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test():
            view = app.query_one(PortView)
            for index, text in enumerate(("needle", "latest")):
                app.on_terminal_app_reader_update(
                    app.ReaderUpdate(PortEvent("port", "data", f"2026-08-25T00:00:0{index}+00:00", text))
                )
            app.search_filter = LineFilter.parse("needle")
            app._reconcile_selection()
            assert any(line.startswith("+ ") and "needle" in line for line in view.marker_texts())
            assert any(line.startswith("- ") and "latest" in line for line in view.marker_texts())

            app._change_active_tag("a", removing=False)
            app._redraw_visible()
            assert any(line.startswith("+ ") and "needle" in line for line in view.marker_texts())
            assert any(line.startswith("- ") and "latest" in line for line in view.marker_texts())

    asyncio.run(exercise())


def test_hidden_projection_renders_explicitly_without_markers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["hidden", "visible"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test() as pilot:
            hidden, visible = app.query(PortView)
            visible.focus()
            await pilot.pause()
            app.action_toggle_zoom()
            await pilot.pause()
            hidden.write_event(PortEvent("hidden", "data", "2026-08-25T00:00:00+00:00", "hidden event"))
            await pilot.pause()
            assert hidden.query_one(RichLog).lines[0].text.startswith("2026-")
            assert hidden.query_one(RichLog).lines[1].text == "↳ Uninterpreted"
            assert hidden.marker_texts() == []
            visible.show_history()
            assert visible.marker_texts() == []

    asyncio.run(exercise())


def test_out_of_range_and_non_owner_contexts_never_render_plus(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["owner", "other"], PortSettings(), tmp_path)

    async def exercise() -> None:
        async with app.run_test() as pilot:
            owner, other = app.query(PortView)
            timestamp = "2026-08-25T00:00:00+00:00"
            owner.write_event(PortEvent("owner", "data", timestamp, "selected"))
            other.write_event(PortEvent("other", "data", timestamp, "same timestamp"))
            owner.show_context(timestamp, app.global_context, selected=("owner", 9))
            other._projection([(0, other.history[0])], selected=("owner", 0))
            await pilot.pause()
            assert owner.marker_texts() == []
            assert any("same timestamp" in line.text for line in other.query_one(RichLog).lines)
            assert not any(line.text.startswith(("+ ", "+- ")) for line in other.query_one(RichLog).lines)

    asyncio.run(exercise())


def test_marker_data_separation_covers_logs_snapshots_search_filters_and_pause(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(SerialReader, "start", lambda self: None)
    app = TerminalApp(["port"], PortSettings(), tmp_path)
    raw_log = StringIO()
    emitted: list[PortEvent] = []
    reader = SerialReader("port", PortSettings(), tmp_path, emitted.append)

    async def exercise() -> None:
        async with app.run_test():
            reader._emit("data", "needle", raw_log)
            app.on_terminal_app_reader_update(app.ReaderUpdate(emitted[0]))
            app.search_filter = LineFilter.parse("needle")
            app.global_filter = LineFilter.parse("needle")
            app._reconcile_selection()
            view = app.query_one(PortView)
            assert any(line.startswith(("+ ", "+- ")) for line in view.marker_texts())
            assert view.history[0].text == "needle"
            assert "- " not in raw_log.getvalue() and "+ " not in raw_log.getvalue()
            snapshot = save_tagged_snapshots(tmp_path, {"port": view.history})
            assert snapshot.written
            assert "+ " not in (tmp_path / "port-tagged.log").read_text()
            view.set_paused(True)
            app.on_terminal_app_reader_update(
                app.ReaderUpdate(PortEvent("port", "data", "2026-08-25T00:00:01+00:00", "needle-paused"))
            )
            assert [event.text for event in view.history] == ["needle"]
            assert app.search_filter.source == "needle"

    asyncio.run(exercise())

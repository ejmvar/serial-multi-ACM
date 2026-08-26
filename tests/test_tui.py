import asyncio
from pathlib import Path

from textual.containers import Horizontal
from textual.widgets import Label, RichLog

from serial_terminal.reader import PortEvent, PortSettings, SerialReader
from serial_terminal.tui import PortView, TerminalApp


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
            assert len(second.query_one(RichLog).lines) == 1
            assert len(first.query_one(RichLog).lines) == 1

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

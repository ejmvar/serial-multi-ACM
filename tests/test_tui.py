import asyncio
from pathlib import Path

from textual.containers import Horizontal
from textual.widgets import RichLog

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

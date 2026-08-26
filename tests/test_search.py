from serial_terminal.filters import LineFilter
from serial_terminal.reader import PortEvent
from serial_terminal.search import ContextBounds, context_window, find_matches


def event(port: str, second: int, text: str) -> PortEvent:
    return PortEvent(port, "data", f"2026-08-25T00:00:0{second}+00:00", text)


def test_find_matches_supports_case_insensitive_text_and_regex() -> None:
    histories = {
        "first": [event("first", 2, "INFO boot"), event("first", 4, "Error RX 42")],
        "second": [event("second", 1, "error tx 41")],
    }

    assert [(match.port, match.index) for match in find_matches(histories, LineFilter.parse("ERROR"))] == [
        ("second", 0),
        ("first", 1),
    ]
    assert [(match.port, match.index) for match in find_matches(histories, LineFilter.parse(r"/rx\s+42/"))] == [("first", 1)]


def test_context_window_aligns_to_timestamp_and_clamps_bounds() -> None:
    events = [event("first", second, f"line {second}") for second in range(5)]
    window, offset = context_window(events, events[2].timestamp, ContextBounds(before=10, after=1))

    assert [item.text for item in window] == ["line 0", "line 1", "line 2", "line 3"]
    assert offset == 2
    assert ContextBounds().adjusted("before", -99).before == 0
    assert ContextBounds().adjusted("after", -99).after == 0

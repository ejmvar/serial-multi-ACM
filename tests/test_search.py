from serial_terminal.filters import LineFilter
from serial_terminal.reader import PortEvent
from serial_terminal.search import (
    ContextBounds,
    SearchMatch,
    context_window,
    event_search_text,
    find_matches,
    recover_selected_match,
)


def event(port: str, second: int, text: str, tags: frozenset[str] = frozenset()) -> PortEvent:
    return PortEvent(port, "data", f"2026-08-25T00:00:0{second}+00:00", text, tags)


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


def test_find_matches_tag_labels_as_well_as_message_text() -> None:
    histories = {
        "gateway": [event("gateway", 1, "forwarded", frozenset({"a", "2"}))],
        "edge": [event("edge", 2, "received", frozenset({"a"}))],
    }

    assert [(match.port, match.index) for match in find_matches(histories, LineFilter.parse("#a"))] == [
        ("gateway", 0),
        ("edge", 0),
    ]
    assert [(match.port, match.index) for match in find_matches(histories, LineFilter.parse(r"/#2/"))] == [("gateway", 0)]


def test_search_uses_raw_text_and_tags_not_derived_projection_words() -> None:
    retained = event("port", 1, "W (80) handshake: peer found", frozenset({"a"}))

    assert event_search_text(retained) == "W (80) handshake: peer found #a"
    for derived_term in ("WARN", "peer discovered", "device elapsed"):
        assert find_matches({"port": [retained]}, LineFilter.parse(derived_term)) == []
    assert [(match.port, match.index) for match in find_matches({"port": [retained]}, LineFilter.parse("#a"))] == [("port", 0)]


def test_context_window_aligns_to_timestamp_and_clamps_bounds() -> None:
    events = [event("first", second, f"line {second}") for second in range(5)]
    window, offset = context_window(events, events[2].timestamp, ContextBounds(before=10, after=1))

    assert [item.text for item in window] == ["line 0", "line 1", "line 2", "line 3"]
    assert offset == 2
    assert ContextBounds().adjusted("before", -99).before == 0
    assert ContextBounds().adjusted("after", -99).after == 0


def test_find_matches_orders_equal_timestamps_by_port_then_history_index() -> None:
    histories = {
        "z-port": [event("z-port", 1, "needle")],
        "a-port": [event("a-port", 1, "needle"), event("a-port", 1, "needle")],
    }

    assert [(match.timestamp, match.port, match.index) for match in find_matches(histories, LineFilter.parse("needle"))] == [
        ("2026-08-25T00:00:01+00:00", "a-port", 0),
        ("2026-08-25T00:00:01+00:00", "a-port", 1),
        ("2026-08-25T00:00:01+00:00", "z-port", 0),
    ]


def test_context_window_can_focus_exact_index_when_timestamps_tie() -> None:
    events = [event("first", 2, "before"), event("first", 2, "selected"), event("first", 2, "after")]

    window, offset = context_window(events, events[2].timestamp, ContextBounds(before=1, after=0), index=1)

    assert [item.text for item in window] == ["before", "selected"]
    assert offset == 1


def test_context_window_rejects_an_out_of_range_exact_index() -> None:
    events = [event("first", 1, "only")]

    window, offset = context_window(events, events[0].timestamp, ContextBounds(), index=4)

    assert window == []
    assert offset == 0


def test_recover_selected_match_translates_eviction_and_keeps_same_event() -> None:
    matches = [
        SearchMatch("first", 0, "2026-08-25T00:00:02+00:00"),
        SearchMatch("first", 1, "2026-08-25T00:00:02+00:00"),
    ]

    assert recover_selected_match(matches, matches[1], {"first": 1}) == matches[0]


def test_recover_selected_match_chooses_sorted_successor_after_eviction() -> None:
    previous = SearchMatch("first", 2, "2026-08-25T00:00:02+00:00")
    matches = [
        SearchMatch("first", 1, "2026-08-25T00:00:01+00:00"),
        SearchMatch("second", 0, "2026-08-25T00:00:03+00:00"),
    ]

    assert recover_selected_match(matches, previous, {"first": 1}) == matches[1]


def test_recover_selected_match_clears_when_no_successor_exists() -> None:
    previous = SearchMatch("first", 0, "2026-08-25T00:00:01+00:00")
    matches = [SearchMatch("first", 0, "2026-08-25T00:00:00+00:00")]

    assert recover_selected_match(matches, previous, {"first": 1}) is None

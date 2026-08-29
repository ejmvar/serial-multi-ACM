"""Pure helpers for searching retained serial display history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .filters import LineFilter
from .formatting import format_tags
from .reader import PortEvent


@dataclass(frozen=True)
class SearchMatch:
    """A matched event and its stable location in one port's history."""

    port: str
    index: int
    timestamp: str


@dataclass(frozen=True)
class ContextBounds:
    """The non-negative number of retained lines shown around an occurrence."""

    before: int = 10
    after: int = 10

    def adjusted(self, field: str, amount: int) -> "ContextBounds":
        if field == "before":
            return ContextBounds(before=max(0, self.before + amount), after=self.after)
        if field == "after":
            return ContextBounds(before=self.before, after=max(0, self.after + amount))
        raise ValueError(f"Unknown context field: {field}")


def find_matches(histories: Mapping[str, Sequence[PortEvent]], query: LineFilter) -> list[SearchMatch]:
    """Return text or explicit tag-label matches in timestamp order."""
    matches = [
        SearchMatch(port, index, event.timestamp)
        for port, events in histories.items()
        for index, event in enumerate(events)
        if query.matches(event_search_text(event))
    ]
    return sorted(matches, key=lambda match: (match.timestamp, match.port, match.index))


def event_search_text(event: PortEvent) -> str:
    """Provide the message and its explicit labels to the find matcher."""
    return f"{event.text} {format_tags(event.tags)}".rstrip()


def context_window(
    events: Sequence[PortEvent],
    timestamp: str,
    bounds: ContextBounds,
    *,
    index: int | None = None,
) -> tuple[list[PortEvent], int]:
    """Return a timestamp-aligned context window and the focused offset within it."""
    if not events:
        return [], 0
    if index is not None:
        if not 0 <= index < len(events) or events[index].timestamp != timestamp:
            return [], 0
        focused = index
    else:
        focused = None
    # ISO-8601 timestamps sort lexically. Pick the first event at or after the
    # target, or the final event when all retained events precede it.
    if focused is None:
        for candidate, event in enumerate(events):
            if event.timestamp >= timestamp:
                focused = candidate
                break
        else:
            focused = len(events) - 1
    start = max(0, focused - bounds.before)
    end = min(len(events), focused + bounds.after + 1)
    return list(events[start:end]), focused - start


def recover_selected_match(
    matches: Sequence[SearchMatch],
    previous: SearchMatch | None,
    evicted: Mapping[str, int] | None = None,
) -> SearchMatch | None:
    """Retain or deterministically recover a selection after retained changes.

    Eviction counts translate a previous history index into the new retained
    history. If that exact event no longer matches, the first sorted match at
    or after its translated identity is selected.
    """
    if not matches:
        return None
    if previous is None:
        return matches[0]

    removed = (evicted or {}).get(previous.port, 0)
    translated_index = previous.index - removed
    exact = next(
        (
            match
            for match in matches
            if match.port == previous.port
            and match.index == translated_index
            and match.timestamp == previous.timestamp
        ),
        None,
    )
    if exact is not None:
        return exact

    target = (previous.timestamp, previous.port, translated_index)
    return next(
        (match for match in matches if (match.timestamp, match.port, match.index) >= target),
        None,
    )

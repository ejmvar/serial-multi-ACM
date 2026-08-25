"""Runtime text and regular-expression filtering."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class LineFilter:
    """A compiled filter; slash-delimited values are regular expressions."""

    source: str
    is_regex: bool
    _pattern: re.Pattern[str] | None = None

    @classmethod
    def parse(cls, value: str) -> "LineFilter | None":
        value = value.strip()
        if not value:
            return None
        if len(value) >= 2 and value.startswith("/") and value.endswith("/"):
            return cls(value, True, re.compile(value[1:-1], re.IGNORECASE))
        return cls(value, False)

    def matches(self, line: str) -> bool:
        if self.is_regex:
            assert self._pattern is not None
            return bool(self._pattern.search(line))
        return self.source.casefold() in line.casefold()


def is_visible(line: str, global_filter: LineFilter | None, port_filter: LineFilter | None) -> bool:
    """Return whether a line satisfies all configured filters."""
    return all(filter_.matches(line) for filter_ in (global_filter, port_filter) if filter_)

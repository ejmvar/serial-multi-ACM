# Tasks: Visual Panel Markers

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 320–380 authored lines; each slice ≤200 |
| Review budget | 200 changed lines |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes (exceeds 200-line budget) |
| Suggested split | PR 1 formatting → PR 2 search → PR 3 TUI → PR 4 docs |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Marker formatting contract (~35 lines) | PR 1 | `uv run pytest tests/test_formatting.py` | N/A; pure Rich `Text` helper | `formatting.py` and its tests |
| 2 | Exact find identity/recovery (~80 lines) | PR 2 | `uv run pytest tests/test_search.py` | N/A; pure search helpers | `search.py` and its tests |
| 3 | Visible-panel projection/lifecycle (~170 lines) | PR 3 | `uv run pytest tests/test_tui.py` | Textual `run_test` with synthetic `ReaderUpdate` events | `tui.py` and TUI tests |
| 4 | User documentation (~35 lines) | PR 4 | `uv run pytest` | N/A; docs-only, no runtime boundary | `README.md` and `USAGE.md` |

## Phase 1: RED Contracts (strict TDD)

- [x] 1.1 Add failing `tests/test_formatting.py` coverage for `render_record(marker=...)`: `""`, `"-"`, `"+"`, and `"+-"` prefixes, unchanged tag suffixes, and preserved `HIGHLIGHTS` styles.
- [x] 1.2 Add failing `tests/test_search.py` cases for `find_matches` tie ordering, index-exact `context_window`, and `recover_selected_match` retention, translated successor, and clear-on-no-successor behavior.

## Phase 2: GREEN Pure Helpers

- [x] 2.1 Modify `src/serial_terminal/formatting.py:render_record` to accept the optional display-only marker and apply existing highlighting to the complete rendered `Text`.
- [x] 2.2 Modify `src/serial_terminal/search.py:SearchMatch, find_matches, context_window`; add `recover_selected_match` and index validation using `(timestamp, port, index)` without changing `event_search_text`.

## Phase 3: RED TUI Integration

- [x] 3.1 Add failing `tests/test_tui.py` scenarios for `resolve_marker`, wrapped-event ownership, combined/empty markers, and accepted versus filtered/paused `-` movement.
- [x] 3.2 Add failing `tests/test_tui.py` scenarios for `TerminalApp._show_search_result`, `_refresh_after_tag_change`, eviction recovery, `j/k`, equal timestamps, and out-of-range context; assert markers by event identity, not `RichLog.lines` positions.
- [x] 3.3 Add failing `tests/test_tui.py` scenarios for `action_toggle_zoom`, focus changes, redraw/tag preservation, hidden-panel suppression, and unchanged search/filter/snapshot data semantics.

## Phase 4: GREEN TUI Projection and Reconciliation

- [x] 4.1 Modify `src/serial_terminal/tui.py:PortView.write_event, replace_event, show_context, show_history`; add `EventRef`, `resolve_marker`, retained-event projection, and marker-aware redraws for visible panels.
- [x] 4.2 Modify `src/serial_terminal/tui.py:TerminalApp.on_terminal_app_reader_update, action_toggle_zoom, on_input_submitted, action_cancel_filter, _show_search_result, _refresh_after_tag_change`; centralize selection reconciliation and eviction translation while preserving pause/filter admission.

## Phase 5: Acceptance and Documentation

- [x] 5.1 Update `README.md` and `USAGE.md` to document visual-only `-`, `+`, and `+-` behavior, visibility, wrapping, and data-separation guarantees.
- [x] 5.2 Run `uv run pytest` and record evidence for all specification scenarios; confirm no markers enter raw logs, snapshots, search terms, or retained event text. Threat matrix is N/A, so no security-boundary RED tests are required.

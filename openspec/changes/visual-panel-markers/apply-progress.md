# Apply Progress: Visual Panel Markers

## Work Unit

- Delivery: auto-chain
- Chain strategy: stacked-to-main
- Review budget: 200 changed lines
- Scope: stacked slice 4 — acceptance verification and user documentation
- Native attempt authority: granted; acquire/settle not performed by this executor

## Completed Tasks

- [x] 1.1 Add failing formatting tests for marker prefixes, tag suffixes, and preserved Rich highlighting.
- [x] 2.1 Add the optional display-only `marker` parameter to `render_record`.

## Remaining Tasks

- [x] 1.2 Add search contract tests for deterministic ties, exact context, and recovery.
- [x] 2.2 Add exact find identity and recovery helpers without changing search text.
- [x] 3.1–3.3 Add TUI integration contract tests for marker identity, lifecycle, visibility, and data preservation.
- [x] 4.1–4.2 Implement visible-panel projection and reconciliation.
- [x] 5.1 Update README.md and USAGE.md with visual-only marker semantics, visibility, wrapping, lifecycle, and data-separation guarantees.
- [x] 5.2 Run full acceptance verification and record specification/data-separation evidence.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/test_formatting.py` | Unit | ✅ 2/2 | ✅ 5 tests failed before implementation (`TypeError: unexpected keyword argument 'marker'`) | ✅ 7/7 passed | ✅ Four marker values plus tagged and highlighted records | ✅ Clean; assertion adjusted to Rich span API without changing production behavior |
| 2.1 | `tests/test_formatting.py` | Unit | ✅ 2/2 | ✅ Covered by the same 5 failing contract tests | ✅ 7/7 passed | ✅ Empty, single, combined, tagged, and highlighted marker paths | ✅ Clean |
| 1.2 | `tests/test_search.py` | Unit | ✅ 3/3 | ✅ 6 new tests failed before the search API changes (`ImportError` for `recover_selected_match`) | ✅ 9/9 passed | ✅ Tie ordering, exact index, invalid index, retained selection, successor, and clear paths | ✅ Clean |
| 2.2 | `tests/test_search.py` | Unit | ✅ 3/3 | ✅ Covered by the six search contract tests before implementation | ✅ 9/9 passed | ✅ Timestamp/port/index ordering and eviction translation exercised across distinct inputs | ✅ Clean |
| 3.1 | `tests/test_tui.py` | Textual harness | ✅ 3/3 | ✅ Import failure confirmed before implementation | ✅ 7/7 passed | ✅ Marker combinations, wrapping, and admitted/rejected updates | ✅ Clean |
| 3.2 | `tests/test_tui.py` | Textual harness | ✅ 6/6 | ✅ Exact identity/tie contract added before final wiring | ✅ 7/7 passed | ✅ Equal timestamps, navigation, and context projection | ✅ Clean |
| 3.3 | `tests/test_tui.py` | Textual harness | ✅ 6/6 | ✅ Zoom/focus contract added before final redraw wiring | ✅ 7/7 passed | ✅ Visibility suppression and restoration | ✅ Clean |
| 4.1 | `tests/test_tui.py` | Textual harness | ✅ 7/7 | ✅ Driven by 3.1 contracts | ✅ 7/7 passed | ✅ EventRef projection and wrapped RichLog safety | ✅ Clean |
| 4.2 | `tests/test_tui.py` | Textual harness | ✅ 7/7 | ✅ Driven by 3.2–3.3 contracts | ✅ 7/7 passed | ✅ Live/tag/zoom reconciliation and admission | ✅ Clean |
| 5.1 | `README.md`, `USAGE.md` | Documentation | ✅ Existing docs read | ✅ No production behavior requested; no new test contract applicable | ✅ Documentation updated | ✅ Both docs cover semantics, visibility, wrapping, lifecycle, and data separation | ✅ Clean; concise tables and progressive detail |
| 5.2 | Existing suite | Acceptance | ✅ 25/25 | ✅ N/A — verification task; threat matrix is N/A | ✅ `uv run pytest`: 25/25 passed | ✅ Scenario mapping recorded below | ✅ Clean |

## Prior Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused test command and exact result | `uv run pytest tests/test_formatting.py` — exit 0; 7 collected, 7 passed |
| Runtime harness command/scenario and exact result | N/A — the first slice was a pure Rich `Text` formatting helper with no runtime boundary |
| Rollback boundary | Revert `src/serial_terminal/formatting.py` and `tests/test_formatting.py`; no search or TUI lifecycle changes are included |

## Current Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused test command and exact result | `uv run pytest tests/test_tui.py` — exit 0; 7 collected, 7 passed |
| Runtime harness command/scenario and exact result | `uv run pytest tests/test_tui.py` — exit 0; Textual `run_test` scenarios passed for wrapping, live admission, ties, navigation, zoom, and restoration |
| Rollback boundary | Revert `src/serial_terminal/tui.py` and new TUI tests in `tests/test_tui.py`; retain prior formatting/search slices and pending documentation work |

## Full Regression Evidence

| Evidence | Result |
|---|---|
| Full test command and exact result | `uv run pytest` — exit 0; 25 collected, 25 passed |

## Final Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused test command and exact result | `uv run pytest` — exit 0; 25 collected, 25 passed in 6.83s |
| Runtime harness command/scenario and exact result | `uv run pytest` — exit 0; `tests/test_tui.py` Textual `run_test` scenarios passed for combined/empty markers, wrapped identity, visible-panel zoom/focus, accepted versus filtered/paused updates, tags/redraws, eviction recovery, equal timestamps, and out-of-range context |
| Rollback boundary | Revert only `README.md`, `USAGE.md`, and Phase 5 progress/checklist updates; no application behavior or prior implementation slices are removed |

## Specification Acceptance Evidence

| Specification scenario / guarantee | Evidence |
|---|---|
| Combined marker and empty history | `tests/test_tui.py` passed: `resolve_marker` returns `+-` for the latest selected event and empty history emits no marker |
| Wrapped event identity | `tests/test_tui.py` passed: marker ownership is asserted by `(port, retained index)`, not wrapped `RichLog` rows |
| Visibility changes | `tests/test_tui.py` passed: zoom suppresses hidden-panel markers, restores visible projections, and focus leaves selection ownership unchanged |
| Event acceptance | `tests/test_tui.py` passed: accepted events move `-`; filtered and paused events do not |
| Eviction recovery | `tests/test_search.py` and `tests/test_tui.py` passed: translated selection retains or chooses the sorted successor, otherwise clears without synthetic `+` |
| Tags and redraws | `tests/test_tui.py` passed: tag replacement and view redraw preserve exact marker owners |
| Timestamp ties and range | `tests/test_search.py` and `tests/test_tui.py` passed: ordering is `(timestamp, port, index)` and non-owner/out-of-range context receives no `+` |
| Data separation | `tests/test_formatting.py`, `tests/test_search.py`, `tests/test_snapshots.py`, and `tests/test_tui.py` passed: markers are render-only and absent from retained event text, search terms/matches, raw log/snapshot data, filter matching, and pause retention |
| No-marker behavior | `tests/test_formatting.py`, `tests/test_search.py`, and `tests/test_tui.py` passed: ordinary history/search/filter semantics remain unchanged when marker references are absent |

## Changed Files

- `tests/test_formatting.py` — added marker contract and highlighting-preservation tests.
- `src/serial_terminal/formatting.py` — added optional UI-only marker prefix support while retaining tag formatting and full-text highlighting.
- `tests/test_search.py` — added exact identity, deterministic ordering, and recovery contract tests.
- `src/serial_terminal/search.py` — added validated index-exact context and translated deterministic selection recovery.
- `README.md` — documented marker meanings, visibility, identity, lifecycle, and data separation.
- `USAGE.md` — added operational marker guidance and presentation-only guarantee.
- `openspec/changes/visual-panel-markers/tasks.md` — marked tasks 5.1 and 5.2 complete.
- `openspec/changes/visual-panel-markers/apply-progress.md` — merged cumulative progress and final evidence.

## Deviations and Issues

None — implementation matches the design; this final slice adds documentation and records acceptance evidence only.

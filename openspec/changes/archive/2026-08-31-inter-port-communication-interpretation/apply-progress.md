# Apply Progress: Inter-Port Communication Interpretation

**Status**: Phase 4 acceptance and preservation verification complete
**Mode**: Strict TDD
**Delivery**: auto-chain, stacked-to-main
**Review budget**: 400 changed lines
**Runtime authority**: `sha256:bfec572fab268eb06b45f85d2296b15d6d77701b0f6aa4388598b8845ef79d71`

## Completed Tasks

- [x] 1.1 RED — Added contract and validation tests for immutable evidence records, source references, input validation, deduplication, and distinct references.
- [x] 1.2 GREEN — Added the isolated immutable history-entry/evidence domain records and caller-supplied history adapter.
- [x] 2.1 RED — Added fixture-driven unit tests for strict grammar/whitelist extraction, malformed and incomplete evidence, MAC normalization, role states, local device time, explicit direction, and conservative no-link cases.
- [x] 2.2 GREEN — Added versioned literal extraction, typed station/peer MAC fields, uncertainty handling, and deterministic explicit peer-MAC-to-unique-station-MAC candidate generation.
- [x] 3.1 RED — Added review and projection tests for immutable human decisions, candidate/reference validation, non-mutation, deterministic IDs/order, and bounded output without verdict or causal claims.
- [x] 3.2 GREEN — Added immutable `ReviewRecord`, human decision validation, and one deterministic aligned-list projection for evidence, candidates, and separate reviews.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/test_inter_port_evidence.py` | Unit | N/A (new) | ✅ Importing missing module failed during collection | ✅ 4 passed | ✅ Happy path, duplicate/distinct references, and invalid input paths | ✅ Clean immutable records and explicit validation |
| 1.2 | `tests/test_inter_port_evidence.py` | Unit | N/A (new) | ✅ Tests referenced missing contracts/adapter | ✅ 4 passed | ✅ Ordering, duplicate identity, and type/key validation | ✅ Clean pure adapter with no existing-contract changes |
| 2.1 | `tests/test_inter_port_evidence.py` | Unit | ✅ 4 passed foundation baseline | ✅ Collection failed on missing `CandidateLink`/link APIs; 8 focused tests then exercised the new contract | ✅ 8 passed | ✅ Exact/negative extraction, role conflict, direction, unique/ambiguous MAC owners, coincidence/no-link cases | ✅ Consolidated fixture helpers and deterministic assertions |
| 2.2 | `tests/test_inter_port_evidence.py` | Unit | ✅ 8 passed | ✅ New tests failed before extraction/link implementation | ✅ 8 passed | ✅ Station/peer joins, normalized MACs, unknown direction, duplicate/ambiguous owners | ✅ Pure functions, frozen records, no existing-contract changes |
| 3.1 | `tests/test_inter_port_evidence.py` | Unit | ✅ 8 passed Phase 2 baseline | ✅ Importing missing `ReviewRecord`/review/projection APIs failed during collection | ✅ 11 passed after implementation | ✅ Accepted/rejected, invalid candidate/source, permutation-stable projection and uncertainty cases | ✅ Separate review records and compact deterministic renderer |
| 3.2 | `tests/test_inter_port_evidence.py` | Unit | ✅ 11 passed | ✅ Review/projection contract tests failed before implementation | ✅ 11 passed | ✅ Human lifecycle and independently ordered evidence/candidates/reviews | ✅ Pure validation/projection; no existing-contract changes |

## Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused test command and exact result | `uv run pytest tests/test_inter_port_evidence.py -k "review or render or stable"` — exit 0; 3 passed, 8 deselected; complete focused file: 11 passed |
| Runtime harness command/scenario and exact result | N/A — pure uncalled domain module; no UI, file I/O, live state, or offline-ingestion boundary exists in this slice |
| Rollback boundary | Delete `src/serial_terminal/inter_port_evidence.py` and `tests/test_inter_port_evidence.py`; existing capture and readability behavior are untouched |

## Regression Evidence

`uv run pytest tests/test_reader.py tests/test_search.py tests/test_snapshots.py tests/test_formatting.py tests/test_tui.py` — exit 0; 59 passed. Full suite: `uv run pytest -q` — exit 0; 71 passed.

## Phase 4 Acceptance Evidence

- [x] 4.1 Focused module suite: `uv run pytest tests/test_inter_port_evidence.py` — exit 0; 11 passed. Review/projection focus: `uv run pytest tests/test_inter_port_evidence.py -k "review or render or stable"` — exit 0; 3 passed, 8 deselected.
- [x] 4.1 Existing contract regression: reader, TUI, formatting, search, and snapshots — exit 0; 59 passed. No `tests/test_filters.py` exists; filter coverage is included in `tests/test_formatting.py` and the TUI suite.
- [x] 4.1 Full suite: `uv run pytest -q` — exit 0; 71 passed. `git diff --check` — exit 0.
- [x] 4.2 Scoped implementation files remain limited to `src/serial_terminal/inter_port_evidence.py` and `tests/test_inter_port_evidence.py`; the restored `visual-panel-markers` files are present, and source inspection confirms no graph visualization, live state, offline ingestion, automatic verdict, causal/report behavior, or raw/event mutation. `git diff --name-only` produced no tracked paths.

## Remaining Tasks

- [x] 2.1–2.2 Evidence extraction, uncertainty, and explicit links
- [x] 3.1–3.2 Review records and projection
- [x] 4.1 Full verification and acceptance evidence
- [x] 4.2 Preservation gate (passed after unrelated visual-panel marker files were restored)

## Scope Boundary

This stacked-to-main acceptance slice verifies only the isolated immutable review/evidence module and its tests. It does not implement UI, file I/O, live state, offline ingestion, automatic verdicts, causality, reports, graphs, or changes to existing reader/TUI/formatting/filter/search/snapshot contracts. Rollback is limited to `src/serial_terminal/inter_port_evidence.py` and `tests/test_inter_port_evidence.py`.

# Tasks: Inter-Port Communication Interpretation

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 500–650 authored lines (module and fixture-driven tests) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 foundation; PR 2 extraction/links; PR 3 review/projection/verification |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

Required delivery decision: choose the chain strategy before the first slice; do not invent one.

### Suggested Work Units

| Unit | Goal / dependency | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Frozen contracts, supplied-history adapter, validation, deduplication; first | PR 1 | `uv run pytest tests/test_inter_port_evidence.py -k "contract or source or duplicate"` | N/A: pure module | Remove new module and test file; capture remains untouched |
| 2 | Strict extraction, uncertainty, and explicit MAC links; depends on 1 | PR 2 | `uv run pytest tests/test_inter_port_evidence.py -k "extract or role or link or incomplete"` | N/A: no UI, I/O, live state | Revert extraction/link code and tests only |
| 3 | Immutable review records, projection, preservation/full verification; depends on 2 | PR 3 | `uv run pytest tests/test_inter_port_evidence.py -k "review or render or stable"` then `uv run pytest -q` | N/A: no runtime boundary | Remove only `inter_port_evidence.py` and its tests |

## Phase 1: Foundation (RED → GREEN)

- [x] 1.1 **RED** — In `tests/test_inter_port_evidence.py`, specify frozen records, source `(port, retained index, host timestamp)` preservation, key/event-port validation, empty timestamps, negative/non-unique indexes, exact-source deduplication, and distinct references.
- [x] 1.2 **GREEN** — Create `src/serial_terminal/inter_port_evidence.py` with immutable records plus the caller-supplied partial-history adapter and strict validation; prove 1.1 passes.

## Phase 2: Evidence and Links (RED → GREEN)

- [x] 2.1 **RED** — Add fixtures in `tests/test_inter_port_evidence.py` for exact ESP-IDF grammar/whitelist, malformed or ANSI/partial/multiline/unlisted text, MAC normalization, `DECLARED`/`UNKNOWN`/`CONFLICTING` roles, local device time, missing ACK, explicit direction, and all coincidence/roles/IDs/results/timing/ambiguous-owner no-link cases.
- [x] 2.2 **GREEN** — Implement the versioned literal extractor, typed MAC observations, uncertainty status, and canonical explicit peer-MAC-to-unique-station-MAC candidate generation in `src/serial_terminal/inter_port_evidence.py`; prove 2.1 passes.

## Phase 3: Review and Projection (RED → GREEN)

- [x] 3.1 **RED** — Add review/projection tests for candidate-only status, immutable human `accepted`/`rejected` records, unknown-candidate/invalid-reference rejection, raw/event non-mutation, deterministic IDs, sorted evidence, and byte-identical table/aligned-list output without PASS/FAIL, causal, completeness, fault, graph, report, or live-state claims.
- [x] 3.2 **GREEN** — Implement review validation/application and the single deterministic `render_preview` table/aligned-list projection in `src/serial_terminal/inter_port_evidence.py`; prove 3.1 passes.

## Phase 4: Preservation / Verification

- [x] 4.1 Run focused RED/GREEN tests, then `uv run pytest -q`; acceptance evidence is passing tests plus existing reader, TUI, formatting, filters, search, and snapshot coverage. Focused module: 11 passed; existing contracts: 59 passed; full suite: 71 passed; `git diff --check`: passed.
- [x] 4.2 Preservation gate: `git diff --name-only` produced no tracked paths; restored `visual-panel-markers` files are present, and source inspection confirms no graph visualization, live state, offline ingestion, automatic verdict, causal claim, raw mutation, or existing-contract task was added.

Threat matrix: N/A in the design; no threat-specific RED tasks apply.

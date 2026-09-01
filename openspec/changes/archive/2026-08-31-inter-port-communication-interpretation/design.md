# Design: Inter-Port Communication Interpretation

## Technical Approach

Add one isolated, pure `inter_port_evidence` domain module. A caller adapts explicitly supplied `Mapping[str, Sequence[PortEvent]]` histories into immutable source references, inventories only strict supported records, joins only explicit peer-MAC-to-direct-station-MAC observations, and projects one byte-stable table/aligned list. It neither subscribes to readers nor changes capture, UI, filtering, search, tags, markers, snapshots, or formatting.

## Architecture Decisions

| Decision | Choice | Rejected / rationale |
|---|---|---|
| Identity | `port` is a supplied key, not a device. Only a directly observed normalized station MAC is local identity; peer/softAP MACs remain typed references. | Panel position, filename, roles, and IDs are weak inference and can create false aliases. |
| Extraction | Full ESP-IDF line first, then a literal, versioned whitelist extractor. Unsupported, malformed, ANSI, partial, or multiline text yields `UNINTERPRETED`. | Reusing broad renderer explanations or fuzzy matching would expand single-line readability into protocol inference. |
| Links | Generate one `candidate` only where a peer MAC equals exactly one other port's direct station MAC; retain both source sets and explicit direction (`peer_to_local`, `local_to_peer`, or `unknown`). | Roles, IDs, tokens, results, timing, missing data, and ambiguous/multiple owners never link ports. |
| Time/order | Sort `(host_timestamp, port, retained_index)`; device milliseconds are displayed as `device_local` only. Domain functions read no clock; review time is caller-supplied. | Device-clock correlation and wall-clock generation would manufacture causality or nondeterminism. |
| Review/persistence | `ReviewRecord` is separate and immutable; a repository/export adapter is the only persistence boundary. It accepts a human-supplied `accepted`/`rejected` decision for an existing candidate identity. | Mutating `PortEvent`, tags, raw logs, or tagged snapshots would violate authoritative capture contracts. |

The remaining proposal gaps are deliberately closed conservatively: literal `pin4_gateway`/`GPIO8` claims are `DECLARED`; absent claims are `UNKNOWN`; contradictory claims are `CONFLICTING`; none establish a link. RX/TX only annotate direction when an approved exact extractor says so. Rejected-frame warnings and missing ACKs remain observed evidence or incomplete input, never PASS/FAIL. Exact message-pattern literals still require product-approved representative fixtures; until approved, that message is uninterpreted rather than guessed.

## Data Flow

```text
supplied retained histories
  -> adapt/enumerate + validate source identity
  -> strict inventory (evidence, roles, input=PARTIAL_RETAINED)
  -> explicit-MAC candidate generation
  -> apply separate review records
  -> shared table/aligned-list projection -> future UI or export adapter
```

The adapter enumerates each supplied sequence; it rejects a key/event-port mismatch, empty port/timestamp, negative/non-unique retained index, and invalid decision/candidate references. It de-duplicates exact source identities before parsing; different references with identical text remain distinct. It never reads files, records a live subscription, reconstructs lines, or compensates for filters, pause, or eviction. Thus the whole inventory is labeled partial and absence is unknown.

## Module / File Plan

| File | Action | Description |
|---|---|---|
| `src/serial_terminal/inter_port_evidence.py` | Create | Frozen records, strict extraction registry, adapter, inventory, candidate generation, review validation, and projection. |
| `tests/test_inter_port_evidence.py` | Create | Pure fixture-driven RED/GREEN coverage. |
| Existing source files | No change | `reader.py`, `tui.py`, `formatting.py`, `search.py`, `filters.py`, and `snapshots.py` remain contract boundaries. |

## Interfaces / Contracts

```python
SourceRef = tuple[str, int, str]  # port, retained index, host timestamp
EvidenceStatus = Literal["OBSERVED", "UNINTERPRETED"]
RoleState = Literal["DECLARED", "UNKNOWN", "CONFLICTING"]
CandidateStatus = Literal["candidate"]
ReviewDecision = Literal["accepted", "rejected"]

@dataclass(frozen=True)
class Evidence: source: SourceRef; status: EvidenceStatus; fields: EvidenceFields
@dataclass(frozen=True)
class CandidateLink: identity: str; status: CandidateStatus; sources: tuple[SourceRef, ...]
@dataclass(frozen=True)
class ReviewRecord: candidate_id: str; decision: ReviewDecision; sources: tuple[SourceRef, ...]; reviewer: str; decided_at: str
```

`candidate_id` is a canonical serialization of normalized endpoints, direction, and sorted supporting references; it does not include process time. `render_preview(inventory, candidates, reviews) -> str` is the sole projection, so future UI/export consume identical rows. A future filesystem exporter may write a distinct non-overwriting review artifact; it must not reuse `save_tagged_snapshots`.

## Testing Strategy

| Layer | What to test | Approach |
|---|---|---|
| Unit | Grammar, MAC normalization, exact-only joins, role conflict, validation, duplicates, ordering, stable bytes | `uv run pytest tests/test_inter_port_evidence.py` with permutation and negative fixtures. |
| Contract regression | No altered capture/search/filter/tag/marker/snapshot/readability behavior | Existing `tests/test_reader.py`, `test_search.py`, `test_snapshots.py`, `test_formatting.py`, and `test_tui.py`. |
| Integration/E2E | N/A in this slice | No UI, file I/O, live state, or offline ingestion is introduced. |

Required RED cases include equal device times, adjacent ports, IDs/results/roles alone, malformed MACs, duplicate source references, ambiguous station owners, missing ACK, conflicting roles, and review records for unknown candidates.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. Deliver as an uncalled pure module; later UI/export integration is a separate change. Rollback deletes this isolated module/tests and any distinct review artifact; raw capture remains intact.

## Open Questions

- [ ] Approve exact per-token extractor patterns and representative fixtures before implementation.
- [ ] Define reviewer identity and retention/location policy for the future review repository/export adapter.

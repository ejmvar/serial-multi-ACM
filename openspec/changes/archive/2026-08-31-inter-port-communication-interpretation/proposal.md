# Proposal: Inter-Port Communication Interpretation

## Intent

Give operators a reviewable, evidence-first preview of possible inter-port links without turning incomplete serial logs into protocol verdicts.

## Scope

### In Scope
- A pure read-only inventory over explicitly supplied per-port retained histories; offline adapters are deferred.
- Exact evidence grammar: complete ESP-IDF lines matching `^(I|W|E) \((\d+)\) ([^:]+): (.+)$`; message recognition is a strict whitelist of observed tokens: Wi-Fi station-MAC, `pin4_gateway`, `GPIO8`, `ESP-NOW RX raw`, `send ... completed`, `bind`, `BOUND`, `EDGE_PACKET`, `FAKE_DATA`, `ACK`, and heartbeat. MACs require six hex octets; unlisted/partial text remains uninterpreted.
- Deterministic evidence table/aligned list and candidate links with `(port, retained index, host timestamp)` references.
- Separate, exportable human review decisions: `candidate`, `accepted`, or `rejected`.

### Out of Scope
- Automatic PASS/FAIL, topology completeness, causality, graph visualization, reports, live state machines, and offline raw-log ingestion.
- Changes to `PortEvent`, reader, filters, tags, markers, snapshots, raw logs, search, retention, or `logs-human-readability`.

## Capabilities

### New Capabilities
- `inter-port-evidence-review`: Evidence extraction, candidate-link preview, and human review records.

### Modified Capabilities
None.

## Approach

Define `PORT` as the supplied port key only; it is not a device identity. Treat a normalized local station MAC as identity only when directly observed; softAP and peer MACs are typed references, never aliases. Accept role claims only as the literal declared `pin4_gateway` or `GPIO8` token—no inferred gateway/edge mapping; missing or conflicting claims remain unknown/conflicting.

Create links only when an explicit peer MAC references another port's directly observed local station MAC. RX evidence means peer-to-local; explicit TX evidence means local-to-peer; otherwise direction is unknown. IDs and result tokens annotate evidence but never establish a link alone. Host timestamps provide deterministic order/window display; device elapsed time is local-only and never correlates ports. Retained-history input is explicitly partial: absence proves nothing.

Candidates begin `candidate`; only an operator may transition them to `accepted` or `rejected`. Review records retain candidate identity, decision, and source references separately from events and raw/tagged snapshots. Present the same deterministic table/aligned list in the UI/export boundary; any export is a new, explicitly labeled review artifact.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/serial_terminal/` | New | Derived evidence/review module and preview surface only. |
| `tests/` | New | Grammar, identity, ordering, and review-decision tests. |
| `README.md`, `USAGE.md` | Modified | Evidence limits and review workflow. |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| False MAC/role match | Medium | Exact grammar, typed identities, human review. |
| Missing retained evidence | High | Label input partial; forbid absence-based verdicts. |
| Clock-derived causality | Medium | Host ordering only; local clocks labeled. |

## Rollback Plan

Remove the isolated derived inventory/preview and review export; raw capture and existing workflows remain untouched.

## Dependencies

- Representative fixtures with exact vocabulary; product approval of the listed grammar.

## Success Criteria

- [ ] Same supplied histories produce byte-stable ordered evidence and candidates.
- [ ] Every candidate exposes source references and no automatic PASS/FAIL.
- [ ] Accepted/rejected review records persist separately from raw/tagged data.
- [ ] Existing capture, readability, filtering, search, markers, and snapshots remain unchanged.

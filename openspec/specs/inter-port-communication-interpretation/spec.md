# Inter-Port Evidence Review Specification

## Purpose

Provide a deterministic, read-only preview of possible inter-port links from
supplied retained histories. It exposes evidence and uncertainty, not outcomes.

## Requirements

### Requirement: Bounded evidence inventory

The system MUST accept only caller-supplied per-port histories whose entries
include port key, retained index, host timestamp, and raw text. An
adapter MUST NOT read offline files, ingest logs, reconstruct multiline records,
or alter reader or retention contracts.

#### Scenario: Supplied history
- GIVEN a caller supplies two per-port histories
- WHEN inventory is built
- THEN only those entries are considered with source references preserved

### Requirement: Exact evidence vocabulary

The system MUST recognize only complete ESP-IDF lines matching
`^(I|W|E) \((\d+)\) ([^:]+): (.+)$` and the proposal’s strict whitelist:
Wi-Fi station-MAC, `pin4_gateway`, `GPIO8`, `ESP-NOW RX raw`, `send ...
completed`, `bind`, `BOUND`, `EDGE_PACKET`, `FAKE_DATA`, `ACK`, and heartbeat.
Records MAY contain only host timestamp, port key, device elapsed, literal role
claim, directly observed station/peer MAC, direction, protocol/frame token, bind
state, sample/edge ID, and explicit result token. Raw text MUST remain
authoritative; unsupported text remains uninterpreted.

#### Scenario: Unsupported line
- GIVEN partial text, malformed MAC, or an unlisted token
- WHEN it is inventoried
- THEN no substitute or unsupported interpretation is emitted

### Requirement: Stable source identity and ordering

Every evidence item MUST preserve `(port, retained index, timestamp)`; output
MUST sort by host timestamp, port key, then retained index. Device elapsed is a
device-local value and MUST NOT correlate ports. Same-source duplicate entries
MUST yield one derived item; distinct source references remain distinct.

#### Scenario: Repeatable preview
- GIVEN identical histories in different input order
- WHEN output is produced
- THEN evidence and table/aligned-list bytes are identical

#### Scenario: Duplicate source
- GIVEN repeated entries with one source reference
- WHEN inventory is built
- THEN no duplicate derived row is emitted

### Requirement: Explicit-only candidate links

The system MUST create a candidate only from an explicit shared
identifier/reference, such as a peer MAC referencing another port’s directly
observed local station MAC. Roles, IDs, results, bind state, direction, timing,
or tokens alone MUST NOT link ports. Panel order, filenames, equal device times,
and missing events MUST NOT be inference inputs.

#### Scenario: Explicit MAC reference
- GIVEN port B observes peer MAC X and port A directly observes station MAC X
- WHEN candidates are generated
- THEN one candidate links the source sets with supporting references

#### Scenario: Coincidence only
- GIVEN equal device times or adjacent panel positions without a shared reference
- WHEN candidates are generated
- THEN no candidate link is created

### Requirement: Human-only review lifecycle

Every candidate MUST start as `candidate`. Only a human MAY transition it to
`accepted` or `rejected`; generation MUST NOT do so. A decision MUST be stored
as a separate review record containing candidate identity, decision, and source
references, without changing events, raw text, tags, or tagged snapshots.

#### Scenario: Operator decision
- GIVEN a candidate
- WHEN an operator accepts or rejects it
- THEN a separate review record stores that status and its references

### Requirement: Uncertainty and bounded presentation

The system MUST distinguish observed evidence, missing/incomplete history, and
unknown or conflicting role claims. Absence MUST NOT mean failure. The preview
MUST NOT emit PASS/FAIL, causal, completeness, fault-ownership, graph, report,
or persistent live-state-machine claims. UI and export MUST use the same
deterministic table or aligned-list representation.

#### Scenario: Missing observation
- GIVEN a sender, ACK, or role claim is absent from retained history
- WHEN preview is rendered
- THEN it is unknown/incomplete, never failed

### Requirement: Existing contracts remain unchanged

The slice MUST NOT change `PortEvent`, reader behavior, filtering, search,
markers, tags, snapshots, raw logs, retention, or readability interpretation.

#### Scenario: Review unused
- GIVEN normal capture, filtering, search, markers, and snapshots
- WHEN evidence review is unused
- THEN existing behavior is unchanged

## Exploration: inter-port-communication-interpretation

### Current State

The application is a live, per-port serial capture tool, not a protocol
analyzer. `SerialReader.run` reads newline-delimited bytes in one daemon thread
per configured port. `_emit` creates an immutable `PortEvent` with the port,
kind, host UTC timestamp, raw decoded text, and tags; it flushes every event to
an independent raw log before notifying the TUI. There is no run manifest,
device identity model, protocol state, event correlation ID, or cross-port
clock alignment.

`TerminalApp.on_terminal_app_reader_update` applies the global and per-port
`LineFilter` before admitting an event to the relevant `PortView`. Each
`PortView.history` retains at most 5,000 admitted displayed events. Pause and
zoom affect presentation only; disk logging continues. `find_matches` searches
retained raw message text plus explicit tag labels, ordering matches by host
timestamp, port, and retained index. `ContextBounds` and `show_context` align
visible panels by timestamp but do not claim that similarly timed events are
causally related.

Tags are user-assigned metadata on retained `PortEvent` values and are exported
by `save_tagged_snapshots`; markers (`-`, `+`, `+-`) are presentation-only and
must not enter raw logs, snapshots, search, filtering, or interpretation input.
`render_record` currently provides a conservative single-line ESP-IDF parser
and raw-plus-derived display. The completed `logs-human-readability` change
explicitly keeps that interpretation per event and explicitly excludes
inter-port topology, graph/MAC/ROLE inference, PASS/FAIL correlation, report
generation, raw rewriting, and heuristic multiline reconstruction. That scope
is complete and must remain unchanged.

The supplied reference run demonstrates why a separate change is useful. Its
`ports.json` maps `/dev/ttyACM0`..`2` to `ACM0.log`..`2`, but does not identify
devices or roles. `summary.json` and `RESULTS.md` derive one gateway and two
edges from log evidence. In the logs, role evidence appears in
`pin4_gateway`/`GPIO8` lines; station MACs appear in Wi-Fi lines; gateway and
edge communication names peer MACs in `ESP-NOW RX raw`, bind, BOUND,
`EDGE_PACKET`, `FAKE_DATA`, ACK, and heartbeat lines. The same run contains
repeated rejected frames and a recovery/reset event, so a warning is not
automatically a failed communication. Device elapsed milliseconds are not host
capture timestamps, and the fixture does not provide a synchronized host-time
axis.

### Affected Areas

- `src/serial_terminal/reader.py` — authoritative event boundary, raw
  persistence, host timestamp, and line/multiline behavior; likely unchanged in
  a safe first slice unless correlation metadata is intentionally introduced.
- `src/serial_terminal/formatting.py` — existing conservative parser and
  derived projection; should remain the single-port interpretation boundary,
  not become a topology verdict engine.
- `src/serial_terminal/tui.py` — independent panel rendering, retained
  histories, filtering admission, pause/zoom, search context, tag mutation,
  marker ownership, and any future cross-port review panel.
- `src/serial_terminal/filters.py` and `src/serial_terminal/search.py` — raw
  compatibility contract; interpreted or correlated text must not silently
  change live admission or existing find semantics.
- `src/serial_terminal/snapshots.py` — current per-port, non-overwriting tagged
  export; any correlation export needs a distinct, explicitly labeled artifact.
- `tests/test_reader.py`, `tests/test_formatting.py`, `tests/test_search.py`,
  `tests/test_snapshots.py`, `tests/test_tui.py` — preservation and identity
  regressions; add pure correlation tests before adding UI state.
- `README.md` and `USAGE.md` — document evidence/confidence language and any
  review controls without weakening the completed readability contract.
- `ft/20260829-185106-logs-human-readable-interpreter.md` — source intent for
  `PORT`, `MAC`, `ROLE`, the dynamic `|Gw|event|Edge|event|` concept, scrolling
  page-length presentation, and a future mobile consumer; it is deliberately
  underspecified and is not itself a protocol schema.
- Reference fixtures under
  `/W/NVT/espnow-master-slave/TEST-e2e/20260829-allboards-b11def7/` —
  representative evidence only: `ACM0.log`, `ACM1.log`, `ACM2.log`,
  `ports.json`, `summary.json`, and `RESULTS.md`.

### Decision Gaps

- **Identity model:** Is `PORT` the host serial path, a stable panel/index, or a
  user-supplied device alias? Is `MAC` the station MAC, softAP MAC, peer MAC,
  or all of them? A single device can expose both station and AP MACs.
- **Role authority:** Is `ROLE` authoritative only when an exact role line is
  observed, or may GPIO, configuration, and protocol behavior vote? What is
  shown for conflicting, missing, or changing role evidence?
- **Direction and semantics:** Are `RX raw from` and `send ... completed`
  sufficient direction evidence? How are gateway/edge, sender/receiver, frame
  type, bind phase, sample, and ACK related? Which protocol vocabulary is
  stable enough to contract, and which remains uninterpreted?
- **Correlation:** Should matching use MAC references, sample/edge IDs, frame
  types, tags, host capture windows, device elapsed values, or a combination?
  What tolerance applies when lines are delayed, duplicated, missing, or
  filtered from retained history?
- **Truth states:** What are the permitted outputs (for example observed,
  corroborated, inconsistent, unverified) and which, if any, may be called
  PASS/FAIL? The system must distinguish “not observed” from “failed”.
- **Human authority:** Is the tool proposing links for operator confirmation,
  or asserting them? How are accepted/rejected links recorded and preserved?
  Can a user correct a false match without rewriting raw evidence?
- **Presentation/export:** Is the first view a dynamic table, timeline, graph,
  side panel, or separate report? Does page-length scrolling operate on events,
  relationships, or rows? Are correlated exports separate from raw and tagged
  snapshots?
- **Input lifecycle:** Does analysis include only live retained events, raw
  logs loaded after a run, or both? How do 5,000-event per-panel retention,
  filters, pause, and eviction affect completeness claims?

### Safe First-Slice Candidate

Build a read-only, pure **evidence inventory and candidate-link preview** over
explicitly supplied per-port retained histories (or a separately loaded set of
raw logs), without changing `PortEvent`, reader behavior, filters, markers,
tags, snapshots, or the completed renderer. Extract only exact, documented
fields already visible in the reference vocabulary: host capture timestamp and
port, device elapsed value, local station MAC, role declaration, peer MAC,
direction, protocol/frame token, bind state, sample/edge ID, and explicit result
token. Preserve every source event reference `(port, retained index, timestamp)`.

Return candidates such as “edge MAC X on port B references gateway MAC Y on
port A” with evidence references and an **unverified/candidate** status. Require
the operator to accept or reject each candidate; record that decision in a
separate review structure or export, never in `PortEvent.text` or raw logs.
Use host timestamps only for ordering/window display, and label device elapsed
time as a device-local clock. Do not infer causality from equal device times.
Start with a deterministic table or aligned event list; defer graph drawing
until node identity, edge direction, duplicate handling, and review semantics
are stable. This slice gives the product a falsifiable vocabulary and lets
tests measure false-positive behavior before adding a persistent graph or live
state machine.

### Approaches

1. **Pure evidence index with human-reviewed candidate links** — Parse exact
   fields into derived records, join only explicit MAC/ID references, and show
   candidate relationships with source references and confidence/status.
   - Pros: smallest reversible boundary; preserves raw contracts; deterministic
     tests; makes uncertainty and human authority explicit; supports later
     table, graph, or report consumers.
   - Cons: requires a protocol vocabulary and identity decisions; does not
     produce automatic PASS/FAIL; incomplete retained histories limit claims.
   - Effort: Medium

2. **Live cross-port correlation panel** — Maintain a new in-memory topology and
   protocol state model as events arrive and render a dynamic gateway/edge
   table or timeline.
   - Pros: directly matches the desired operator workflow; can highlight
     missing ACKs and transitions quickly.
   - Cons: high coupling to retention/filter/clock semantics; races and
     eviction can create false state; requires reset, duplicate, timeout, and
     correction policy before it is trustworthy.
   - Effort: High

3. **Offline run report and graph generator** — Consume complete per-port logs,
   `ports.json`, and optional expected topology to generate a reviewable report
   and graph.
   - Pros: complete-run analysis avoids live eviction and can reproduce a
     result; naturally supports the reference `RESULTS.md` shape and graph
     export.
   - Cons: needs a formal manifest/schema and protocol contract; does not help
     live operators; can overfit one reference run and encourage unjustified
     verdicts.
   - Effort: High

### Recommendation

Proceed to proposal with Approach 1. Define identity, exact evidence grammar,
candidate-link statuses, source references, and human review before choosing a
graph model or verdict vocabulary. Keep the first implementation read-only and
derived. A table/aligned list is safer than the requested dynamic graph because
it exposes the evidence needed to validate node and edge semantics without
turning uncertain joins into visual facts. If offline complete-log analysis is
required, make it a separate input adapter around the same pure index rather
than teaching the live reader to reconstruct runs.

### Explicit Non-Goals

- Do not reopen, expand, or alter the completed `logs-human-readability`
  per-line parser/projection scope.
- Do not rewrite, normalize, strip, or replace raw serial input or existing raw
  per-port logs.
- Do not change current live filter admission, retained-history limits, search
  text/tag semantics, marker ownership, pause/zoom behavior, or tagged snapshot
  format in the first slice.
- Do not infer PORT/MAC/ROLE identity from panel order alone, filename alone,
  a single weak log line, or an unconfirmed heuristic.
- Do not assert automatic communication success, PASS/FAIL, topology
  completeness, causality, or fault ownership from missing/filtered events.
- Do not add heuristic multiline reconstruction, ANSI interpretation, protocol
  decoding beyond an explicit contract, or a persistent live state machine.
- Do not make graph visualization, mobile USB reading, MQTT, negotiated sensor
  schemas, TLV/fragmentation, dynamic adaptation, or report generation part of
  the safe first slice.

### Risks

- MAC identity is ambiguous when station and softAP addresses coexist; wrong
  normalization can create convincing but false edges.
- Device elapsed clocks are local and may reset or drift; cross-port ordering
  based on them can manufacture causality.
- Repeated retries, rejected frames, recovery resets, and duplicate lines make
  “warning” and “failure” non-equivalent; reference ACM1/ACM2 logs visibly
  contain rejected frames despite the run being classified PASS.
- Filtered, paused, hidden, or evicted events are absent from retained history;
  absence in the TUI cannot be treated as absence on the wire.
- A graph hides uncertainty more effectively than a table; rendering inferred
  links before review risks converting suggestions into operator belief.
- Adding a correlation state or interpretation field to `PortEvent` would
  couple raw capture, snapshots, search, and retention and create a difficult
  rollback boundary.
- The source note proposes a layout but defines neither protocol grammar nor
  truth authority; implementing its example literally would overfit and
  overclaim.

### Ready for Proposal

Yes, for a bounded proposal centered on a pure evidence index and human-reviewed
candidate links. The proposal must first state the PORT/MAC/ROLE identity
contract, exact supported evidence patterns, clock/order policy, uncertainty
states, review persistence, and whether the input is live retained history,
offline complete logs, or both. It should explicitly defer automatic verdicts,
graph visualization, and all non-goals above until those contracts are tested.

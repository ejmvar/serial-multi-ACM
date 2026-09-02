# Study a multi-device message flow

Tag related gateway and edge messages while they are still in retained display history, search a tag across all panels, then export the study set without changing the continuous raw logs.

## Quick path

1. Start all three ports and focus the gateway with `1` (or `Tab`).
2. Mark a gateway message with `T`, then `a`; mark each related edge message with `T`, then `a`.
3. Press `f`, type `#a`, and press `Enter`; use `j` and `k` to follow every tagged record across panels.
4. Press `S` to create one non-overwriting `*-tagged.log` study file for every port.

## Keymap

The keymap is rendered as a deterministic two-line bottom widget. The semantic
key pairs are arranged vertically, while remaining actions are shown compactly
on the second line.

| Lowercase | Uppercase | Behavior |
| --- | --- | --- |
| `p` | `P` | `p`: Port filter. `P`: Pause the selected port. |
| `i` | `I` | `i`: Toggle interpreted raw. `I`: Force show interpreted raw. |
| `f` | `F` | `f`: Find history. `F`: Clear find and restore retained history. |
| `b` | `B` | `b`: Adjust before. `B`: Reset before to 10. |
| `a` | `A` | `a`: Adjust after. `A`: Reset after to 10. |

## Example: one gateway and two edges

Run a three-panel session:

```bash
uv run serial-terminal /dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2 --log-dir captures
```

Assume panel 1 is a gateway and panels 2 and 3 are edge devices:

| Panel | Device | Retained message |
| --- | --- | --- |
| `1` | `/dev/ttyACM0` gateway | `TX route=42 -> edge-a` |
| `2` | `/dev/ttyACM1` edge-a | `RX route=42` |
| `3` | `/dev/ttyACM2` edge-b | `INFO route=42 observed` |

Use the exact keystrokes below. A panel number focuses it; pressing the selected number while it is zoomed restores the side-by-side layout.

| Goal | Keys | Result |
| --- | --- | --- |
| Focus gateway, then zoom it | `1`, `z` | Gateway fills the available terminal. |
| Restore all panels | `z` | Returns to three-panel view. `Escape` also restores it when no other mode is active. |
| Tag the gateway message | `1`, `T`, `a` | Adds visible label `[#a]` to the active gateway record. |
| Tag edge-a message | `2`, `T`, `a` | Adds the same correlation label. |
| Tag edge-b message | `3`, `T`, `a` | Adds the same correlation label. |
| Add a numeric investigation label | `1`, `t`, `2` | Adds `[#2 #a]` to the selected port's latest retained event. |
| Remove only numeric `2` | `u`, `2` | Removes `#2`; `#a` remains. |
| Remove only letter `a` | `U`, `a` | Removes `#a` without touching any other tag. |
| Cancel a pending tag action | `T`, `Escape` | Leaves the active event unchanged. |

### Find and follow the correlation

Press `f`, type `#a`, then press `Enter`. Find searches both original message text and explicit tag labels. The first matching record becomes active and the visible panels align around its timestamp. Press `j` for the next tagged record and `k` for the previous one; the status line reports the match number, port, timestamp, and context bounds.

While this find is active, `T`, `a` applies `#a` to the **current find match**, even if another panel is focused. Likewise, `U`, `a` removes only `#a` from that match. The result list and displayed context refresh immediately. `Escape` clears an active find after it has first exited any pending tag or context-adjustment mode.

## Find and context controls

| Keys | Use |
| --- | --- |
| `f`, text, `Enter` | Find case-insensitive message text in retained displayed history. |
| `f`, `#a`, `Enter` | Follow every event carrying tag `a` across ports. |
| `f`, `/pattern/`, `Enter` | Run a case-insensitive regex against message text and tag labels. |
| `j` / `k` | Move to next / previous find result. |
| `a` / `b` | Start AFTER / BEFORE context adjustment for the current result; `A` / `B` reset the corresponding bound to 10. |
| In context mode: `j` / `k`, `h` / `l` | Adjust by `+1` / `-1`, or `-5` / `+5` lines. |
| `F` | Clear find and restore retained history. |
| `Escape` | Exit context mode; later `Escape` also clears find and restores normal retained history. |

In side-by-side view, context bounds apply to every displayed panel. In a zoomed panel, adjustments apply only to that port.

## Read the visual markers

The panel prefix is a transient orientation aid, not part of the message:

| Marker | Meaning |
| --- | --- |
| `-` | Latest accepted event that remains in that panel's retained displayed history. |
| `+` | The exact event selected by find, identified by its port and retained history index. |
| `+-` | Both meanings apply to the same event. |

Only visible panels are marked. Zooming or restoring the side-by-side layout recomputes the visible projection: a hidden panel has no marker, while an exposed panel is evaluated independently. Tab, numeric focus, and other focus changes do not transfer `+` to the focused panel. A selected event that is merely present in another panel's timestamp context does not receive a synthetic `+`.

Markers remain attached to retained event identity, never to wrapped visual rows. Long messages can wrap into multiple rows without duplicating or moving a marker. Accepted live display events move `-`; events rejected by a live filter or by a paused panel do not. Tag changes, redraws, and context navigation preserve both marker owners. When retention evicts the selected event, find results are recomputed in `(timestamp, port, retained index)` order: the deterministic successor is selected when present; otherwise find selection clears and no `+` is fabricated.

### Presentation-only guarantee

The marker is added only while rendering the visual panel. It is not stored in the retained event text and never enters:

- raw per-port log files;
- tagged snapshot files;
- find input, searchable terms, or match results;
- live filter matching or pause/retention decisions.

Thus searching, filtering, pausing, eviction, logging, and snapshot contents use the original unmarked event and tag data.

## Export a tagged study snapshot

Press `S`. The app copies the current retained histories and writes the study files in the configured `--log-dir` in a background worker, so serial readers, visual streaming, live filters, and continuous raw logging keep running. The status line reports every path and event count, plus any error.

For the command above, the names are exactly:

```text
captures/ttyACM0-tagged.log
captures/ttyACM1-tagged.log
captures/ttyACM2-tagged.log
```

For other port paths, the final path component is safely sanitized before `-tagged.log` is appended. Snapshot files are created exclusively: an existing snapshot is never overwritten, and the status line reports that condition.

Each line preserves the event timestamp and original message with an explicit tag field:

```text
2026-08-26T12:00:00.000+00:00 TX route=42 -> edge-a [tags: #2 #a]
2026-08-26T12:00:01.000+00:00 RX route=42 [tags: #a]
2026-08-26T12:00:02.000+00:00 INFO route=42 observed [tags: -]
```

## Read the human-readable projection

Each visual event keeps its raw line and adds a derived line beneath it; no
toggle is required to recover evidence. The leading ISO-8601 UTC timestamp is
the host capture clock. A derived `device elapsed: N ms` value is the device
clock from that record, not a host timestamp.

### Session-only density controls

Use these case-sensitive keys while viewing the panels:

| Key | Visible mode | Behavior |
| --- | --- | --- |
| `i` | `RAW SHOWN` / `RAW HIDDEN` | Toggle raw rows for interpreted events globally. Press again to recover the normal two-line projection. |
| `I` | `RAW SHOWN` | Force interpreted raw rows to show. |
| `m` | `MAC:4` | Show the last two MAC octets; press `m` again for `MAC:FULL`. |
| `M` | `MAC:6` | Show the last three MAC octets; press `M` again for `MAC:FULL`. |

The controls apply to the current session only. A new invocation starts at
`RAW SHOWN` and `MAC:FULL`; `m` and `M` remain distinct, and switching from
one to the other replaces the active mode. The status line reports the active
raw and MAC modes so recovery is explicit.

These are presentation controls, not redaction. Raw bytes are decoded and
logged by the reader exactly as before, and the original `PortEvent.text`
remains authoritative. Filters, search, tags, markers, snapshots, exports,
pause, zoom, retention, evidence, candidate identities, source references,
and review records are unaffected. Only valid interpreted six-octet MAC fields
are shortened; malformed, absent, raw, and uninterpreted values remain as
provided.

With `RAW HIDDEN`, a parsed event keeps its derived line and its marker follows
the event onto that line. Unknown, malformed, ANSI-bearing, or control-bearing
input always retains its exact raw line and `Uninterpreted` label. Continuous
raw logs remain the recovery path for complete capture.

Interpretation is deliberately exact and single-line only:

```text
^(I|W|E) \((\d+)\) ([^:]+): (.+)$
```

The severity prefixes map to `INFO`, `WARN`, and `ERROR`. The only semantic
explanations are exact `handshake: peer found` → `peer discovered`, and a
message exactly equal to `ACK` or `acknowledged` → `acknowledgement received`.
All other valid records receive neutral fields. Unknown or malformed text,
bootloader output, continuation lines, concatenated records, ANSI/control
input, and incomplete records remain raw and are labeled `Uninterpreted`.
Input is never stripped, rewritten, or reconstructed; Rich styling is not
allowed to treat input ANSI/control sequences as instructions.

This projection describes one port at a time. It intentionally does not infer
cross-line communication or graph/MAC/ROLE/PORT topology, correlate PASS/FAIL
outcomes, or generate reports. Use the raw per-port logs for authoritative
evidence; find, filters, tags, markers, pause/zoom, retention, and tagged
snapshots continue to use the original raw event.

## Explicit identity and evidence decisions

The current interpreted projection identifies source, destination, and role
when the record provides sufficient evidence. It parses canonical identity and
explicit `type`, `from`, and `to` fields, then renders their metadata
conservatively. For example:

```text
WARN GW:1E:B4 RCV evt=FAKE_QUEUED sample=1234 attempt=1/3
WARN GW:1E:B4 RCV evt=HS type=1 meaning=HANDSHAKE
```

Do not manufacture fields when the record does not support them. Unknown or
conflicting evidence remains visible, and the raw record remains authoritative.
After identity is observed, the matching port title is updated with the
observed device ID and role.

The firmware role is selected from the latched GPIO4 switch: GPIO4 high means
gateway and low means edge. Infer roles from explicit runtime logs, not solely
from a USB/JTAG `/dev/serial/by-id` identifier and not from weak message
heuristics. If evidence is missing or disagrees, show `ROLE=?` or mark it
`CONFLICTING`; never silently choose a role.

After the Wi-Fi MAC is explicitly observed or configured, the serial header
should expose the physical port and a short MAC-derived device ID, for example:

```text
PORT 1 | /dev/ttyACM0 | DEV 1E:B4 | ROLE=GW
```

Do not equate USB serial numbers with Wi-Fi MACs. Verified firmware already
emits one startup record from `handshake_init()`
(`espnow_example_main.c:1992-2013`):

```text
GPIO8 initial device=<MAC> role=<gateway|edge> level=... request=...
```

This existing record is the implementation point for a recommended, separate
firmware change. Normalize or rename it into one canonical startup identity
record rather than adding a duplicate line, using the already latched role and
already-read Wi-Fi MAC:

```text
INFO identity: device=<MAC> role=gateway role_source=gpio4_latched gpio4=HIGH
```

GPIO8 is a degraded-mode request/output concept, not the source of identity;
its current `level` and `request` values may be preserved separately, for
example as `degraded_request=...`. The firmware change must not resample GPIO4,
change protocol state, or enable runtime role switching. The existing LED role
indicator is not sufficient for serial-log correlation. This documentation
does not claim that firmware change is implemented.

Apply these evidence labels to interpreted claims:

| Label | Meaning |
| --- | --- |
| `OBSERVED` | Directly present in captured evidence. |
| `DECLARED` | Explicitly stated by the device or operator. |
| `CORRELATED` | Joined by explicit shared evidence such as MAC, session, delivery ID, or correlation. |
| `UNKNOWN` | Not established by available evidence. |
| `CONFLICTING` | Incompatible evidence is present and must remain visible. |

No `PASS`/`FAIL` or topology claim is valid without explicit evidence. See
[MSG_TYPE.md](MSG_TYPE.md) for the gateway/edge wire types and for why
`EDGE_PACKET`/`DATA_MESSAGE` are wire types while `FAKE_DATA` is diagnostic
payload labeling.

The current implementation does not infer topology across lines. Unsupported
values remain `?` or `UNKNOWN`, conflicts remain `CONFLICTING`, and no
`PASS`/`FAIL` claim is produced without explicit evidence. Raw events remain
authoritative; interpreted metadata is only a conservative projection.

## Retention boundary

Tags belong only to retained `PortEvent` records in the Textual display history. They are shown after redraws and searches, and they are saved in tagged snapshots. The original per-port raw logs remain unchanged and contain every reader event independently of display filters, pauses, retention eviction, or tags.

Each panel keeps up to 5,000 **displayed** events. Consequently, `S` exports only the currently retained displayed records; it cannot export filtered-out, paused, hidden, or already-evicted raw input. Use continuous raw logs for complete capture and tagged snapshots for a bounded, human-curated study set.

# Serial Multi-Port Terminal

A Textual terminal UI that reads and logs multiple serial ports concurrently. Each port is read in its own thread, so an unavailable device is shown as an error without stopping the remaining ports. Logging always continues while a visual panel is paused.

## Run

```bash
uv run serial-terminal /dev/ttyACM0 /dev/ttyACM1
uv run serial-terminal /dev/ttyACM0 --baudrate 9600 --bytesize 7 --parity E --stopbits 1.5 --timeout 0.5 --log-dir captures
uv run serial-terminal /dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2 --log-dir captures
```

Logs are written independently as `log_<sanitized-port>_<YYYYMMDD_HHMMSS>.log` in `log/` by default. Every record starts with an ISO-8601 UTC timestamp with milliseconds.

## Reconnect behavior

Readers stay alive through transient open/read failures and retry every second by default. Set the interval with `--reconnect-delay SECONDS` (it must be greater than zero). The configured port is the **logical** reader identity: `PortEvent.port`, the TUI panel, and the per-reader log file keep the original argument even when Linux assigns a different active device path.

After the first successful open, the reader records the USB VID, PID, serial number, and location when available. On reconnect it prefers the configured path, then uses an exact, unique descriptor match. It never guesses when multiple devices match. Status messages include available `/dev/ttyACM*` and `/dev/ttyUSB*` paths so an operator can verify re-enumeration.

### Manual verification

```bash
ls -l /dev/ttyACM* /dev/ttyUSB* /dev/serial/by-id/*
uv run serial-terminal /dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2 --log-dir captures
```

Start the monitor, reset or unplug one device, then rerun the `ls` command. Confirm the TUI reports `Reconnected ... via ...` and that lines continue in the same logical per-reader log. These are manual verification instructions; no hardware test is claimed here.

## Human-readable projection

The visual panels show every retained event as two lines: the unchanged raw
record followed by a conservative derived projection. The host ISO-8601 UTC
timestamp is the capture clock; a parsed `device elapsed: N ms` value is the device's elapsed
clock. They are separate clocks and are never interchangeable. The raw record
and raw tagged snapshot remain authoritative.

Only a complete single-line record matching
`^(I|W|E) \((\d+)\) ([^:]+): (.+)$` is interpreted. `I`, `W`, and `E` become
`INFO`, `WARN`, and `ERROR`; exact `handshake: peer found`, `ACK`, and
`acknowledged` rules produce only their documented explanations. Unknown,
malformed, bootloader, continuation, concatenated, ANSI-bearing, or control-
bearing input is retained and shown as `Uninterpreted`, without stripping or
reconstructing anything.

This is a single-port/per-panel presentation aid. It does not infer
cross-line communication or graph/MAC/ROLE/PORT topology, correlate outcomes,
or generate reports.

## Operational identity and message evidence decisions

The interpreted-log format makes source, destination, and role
explicit whenever the captured evidence supports them. For example:

```text
WARN GW:1E:B4 RCV evt=FAKE_QUEUED sample=1234 attempt=1/3
WARN GW:1E:B4 RCV evt=HS type=1 meaning=HANDSHAKE
```

The current implementation parses canonical identity records and explicit
`type`, `from`, and `to` fields when present. It renders the resulting
metadata conservatively: fields are shown only when supported by the record,
and unknown or conflicting roles remain visible as `ROLE=?` or
`CONFLICTING` evidence. After a complete identity observation, the matching
port title is updated with the observed device ID and role.

Role interpretation is grounded in explicit runtime evidence. The firmware
selects and latches the device role from GPIO4: high means gateway and low
means edge. Never infer a role solely from a USB/JTAG
`/dev/serial/by-id` identifier or from weak message heuristics. The existing
LED role indicator is useful locally but is not sufficient to correlate a
serial record with a device.

Once the Wi-Fi MAC has been explicitly observed or configured, the serial
header exposes the physical port and a short device ID derived from that MAC:

```text
PORT 1 | /dev/ttyACM0 | DEV 1E:B4 | ROLE=GW
```

USB serial numbers and Wi-Fi MAC addresses are different identifiers and must
not be equated. Verified firmware already emits one startup record from
`handshake_init()` (`espnow_example_main.c:1992-2013`):

```text
GPIO8 initial device=<MAC> role=<gateway|edge> level=... request=...
```

This existing record is the implementation point for a recommended, separate
firmware change. Normalize or rename it into one canonical identity record
instead of adding a duplicate line:

```text
INFO identity: device=<MAC> role=gateway role_source=gpio4_latched gpio4=HIGH
```

Use the already latched role and already-read Wi-Fi MAC. GPIO8 is a
degraded-mode request/output concept, not the source of device identity; its
`level` and `request` values may remain as separate degraded-mode fields such
as `degraded_request=...`. The change must not resample GPIO4, change protocol
state, or enable runtime role switching. The LED indicator is insufficient for
serial correlation. This documentation does not claim that firmware change is
implemented. See [MSG_TYPE.md](MSG_TYPE.md) for the authoritative wire enum,
direction validation, and the distinction between wire `DATA_MESSAGE` and
diagnostic `FAKE_DATA`.

Use the evidence labels `OBSERVED`, `DECLARED`, `CORRELATED`, `UNKNOWN`, and
`CONFLICTING`. Do not claim `PASS`, `FAIL`, or a topology without explicit
evidence.

The parser and renderer do not infer topology across lines. Raw events remain
authoritative, and unsupported values stay visible as `?` or `UNKNOWN`;
`CONFLICTING` evidence is preserved rather than resolved by heuristic. No
`PASS`/`FAIL` claim is produced without explicit evidence.

**For the complete three-device tagging and study-export workflow, see [USAGE.md](USAGE.md).**

## Shortcuts

The keymap is rendered as a deterministic two-line bottom widget. Its semantic
key pairs are arranged vertically; remaining actions are shown compactly on the
second line.

| Lowercase | Uppercase | Behavior |
| --- | --- | --- |
| `p` | `P` | `p`: Port filter. `P`: Pause the selected port. |
| `c` | `C` | `c`: Clear all retained TUI history. `C`: Clear the selected port's retained TUI history. |
| `o` | `O` | `o`: Toggle ORIGINAL-ONLY projection for all ports. `O`: Toggle it for the selected port. |
| `i` | `I` | `i`: Toggle interpreted raw. `I`: Force show interpreted raw. |
| `f` | `F` | `f`: Find history. `F`: Clear find and restore retained history. |
| `b` | `B` | `b`: Adjust before. `B`: Reset before to 10. |
| `a` | `A` | `a`: Adjust after. `A`: Reset after to 10. |

| Key | Action |
| --- | --- |
| `Space` | Pause or resume all visual panels; disk logging continues. |
| `P` | Pause or resume the selected port panel. |
| `c` | Clear all retained TUI history; reader threads and files in `--log-dir` are untouched. |
| `C` | Clear only the selected port's retained TUI history; reader threads and files in `--log-dir` are untouched. |
| `o` | Toggle all ports between the normal interpreted projection and ORIGINAL-ONLY projection. |
| `O` | Toggle ORIGINAL-ONLY projection for the selected port only. |
| `Tab` / `1`–`9` | Focus and select a port panel. When that port is zoomed, press its number again to restore the side-by-side layout. |
| `z` | Zoom the focused port to fill the available terminal; press again to restore the side-by-side layout. |
| `f` | Search retained displayed history, using case-insensitive plain text or `/regex/`; this does not change live filters. `F` clears find and restores retained history. |
| `i` | Toggle interpreted raw lines; status shows `RAW SHOWN` or `RAW HIDDEN`. Uninterpreted raw lines are never hidden. `I` forces interpreted raw lines to show. |
| `m` / `M` | Select `MAC:4` (last two octets) / `MAC:6` (last three octets). Press the active key again for `MAC:FULL`; modes are session-only. |
| `t` then `1`–`9` / `T` then `a`–`z` | Assign a numeric / letter correlation tag to the active retained event. |
| `u` then `1`–`9` / `U` then `a`–`z` | Remove only that numeric / letter tag from the active retained event. |
| `S` | Save one non-overwriting tagged snapshot per port in the log directory. |
| `j` / `k` | Next / previous search result (when not adjusting context); visible panels align to its timestamp. |
| `a` / `b` | Adjust AFTER / BEFORE context around search results. `A` / `B` reset AFTER / BEFORE to 10. In adjustment mode, `j`/`k` change by +1/-1 and `h`/`l` by -5/+5; `Escape` exits the mode. Bounds never go below zero. Global bounds apply side-by-side; zoom changes only the selected-port bounds. |
| `g` | Set or clear the global live display filter. |
| `p` | Set or clear the selected-port live display filter. |
| `Enter` | Apply the active find or live filter. Plain text is case-insensitive; `/pattern/` is a case-insensitive regex. |
| `Escape` | Cancel pending tag/untag mode, exit context adjustment, cancel input, clear an active search, or restore the side-by-side layout. |
| `q` | Quit. |

## Visual markers

Markers are visual-only prefixes on retained display records:

| Marker | Meaning |
| --- | --- |
| `-` | The panel's latest accepted, retained displayed event. |
| `+` | The exact retained event selected by find. |
| `+-` | One event that is both the latest event and the selected find event. |

Markers are scoped to visible panels. Zoom and layout changes redraw ownership for the panels currently shown; hidden panels receive no marker, and changing focus never moves `+`. Ownership uses the retained `(port, history index)`, not wrapped `RichLog` rows, so a wrapped event receives one marker and never transfers it to another event. Find context on another panel may share a timestamp, but receives no synthetic `+`.

An accepted displayed event moves `-` to the newest retained event. Filtered-out and paused events do not move it. Tags, redraws, live updates, and retention eviction preserve event identity; after eviction, find selects the deterministic next match when available or clears `+` without inventing a row. Markers never enter raw logs, tagged snapshots, search input or terms, filtering, pause/retention decisions, or retained `PortEvent.text`.

TX, RX, ACK, NACK, and common log levels are highlighted. Find also matches visible tag labels, so enter `#a` to follow tag `a` across ports. The active event is the current find match while search is active; otherwise it is the latest retained displayed event in the selected port. Live filters affect only new TUI lines, never the complete per-port log file. Each port retains up to 5,000 displayed lines for find/navigation; readers and disk logging continue independently. Tagged snapshots export this retained displayed history only, never hidden or already-discarded raw input.

### Session-only display controls

The `c`, `C`, `o`, `O`, `i`, `m`, and `M` controls affect only the current visual
session. `c` and `C` discard retained TUI rows but never delete or truncate
files in `--log-dir`; reader disk logging continues. `o` and `O` show the exact
raw event line without its derived interpreted line. They do not rewrite
`PortEvent.text` or alter filters, snapshots, or evidence.

The `i`, `m`, and `M` controls affect only the current visual projection. They
reset for every new session and never change `PortEvent.text`, raw bytes after
decoding, reader logs, tags, filters/search terms or matches, markers, pause,
zoom, retention, snapshots, exports, candidate identities, source references,
or review records.

The status line identifies both settings: `RAW SHOWN`/`RAW HIDDEN` and
`MAC:FULL`/`MAC:4`/`MAC:6`. `m` and `M` are case-sensitive: switching keys
replaces the active MAC mode, while pressing the active key restores full MACs.
Only interpreted, complete six-octet MAC fields are shortened. Malformed,
absent, raw, and uninterpreted values remain unchanged.

When raw lines are hidden, parsed events keep their derived row and any marker
moves with the event onto that visible row. Uninterpreted, malformed, ANSI,
and control-bearing input always keeps its exact raw row. Use the continuous
raw log for complete capture; display controls provide no redaction or data
loss and introduce no protocol, inference, persistence, graphing, or verdict
semantics.

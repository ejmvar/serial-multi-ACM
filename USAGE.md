# Study a multi-device message flow

Tag related gateway and edge messages while they are still in retained display history, search a tag across all panels, then export the study set without changing the continuous raw logs.

## Quick path

1. Start all three ports and focus the gateway with `1` (or `Tab`).
2. Mark a gateway message with `T`, then `a`; mark each related edge message with `T`, then `a`.
3. Press `f`, type `#a`, and press `Enter`; use `j` and `k` to follow every tagged record across panels.
4. Press `S` to create one non-overwriting `*-tagged.log` study file for every port.

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
| `a` / `b` | Start AFTER / BEFORE context adjustment for the current result. |
| In context mode: `j` / `k`, `h` / `l` | Adjust by `+1` / `-1`, or `-5` / `+5` lines. |
| `Escape` | Exit context mode; later `Escape` clears find and restores normal retained history. |

In side-by-side view, context bounds apply to every displayed panel. In a zoomed panel, adjustments apply only to that port.

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

## Retention boundary

Tags belong only to retained `PortEvent` records in the Textual display history. They are shown after redraws and searches, and they are saved in tagged snapshots. The original per-port raw logs remain unchanged and contain every reader event independently of display filters, pauses, retention eviction, or tags.

Each panel keeps up to 5,000 **displayed** events. Consequently, `S` exports only the currently retained displayed records; it cannot export filtered-out, paused, hidden, or already-evicted raw input. Use continuous raw logs for complete capture and tagged snapshots for a bounded, human-curated study set.

# Serial Multi-Port Terminal

A Textual terminal UI that reads and logs multiple serial ports concurrently. Each port is read in its own thread, so an unavailable device is shown as an error without stopping the remaining ports. Logging always continues while a visual panel is paused.

## Run

```bash
uv run serial-terminal /dev/ttyACM0 /dev/ttyACM1
uv run serial-terminal /dev/ttyACM0 --baudrate 9600 --bytesize 7 --parity E --stopbits 1.5 --timeout 0.5 --log-dir captures
```

Logs are written independently as `log_<sanitized-port>_<YYYYMMDD_HHMMSS>.log` in `log/` by default. Every record starts with an ISO-8601 UTC timestamp with milliseconds.

## Shortcuts

| Key | Action |
| --- | --- |
| `Space` | Pause or resume all visual panels; disk logging continues. |
| `Shift+p` | Pause or resume the selected port panel. |
| `Tab` / `1`–`9` | Focus and select a port panel. When that port is zoomed, press its number again to restore the side-by-side layout. |
| `z` | Zoom the focused port to fill the available terminal; press again to restore the side-by-side layout. |
| `f` | Search retained displayed history, using case-insensitive plain text or `/regex/`; this does not change live filters. |
| `j` / `k` | Next / previous search result (when not adjusting context); visible panels align to its timestamp. |
| `a` / `b` | Adjust AFTER / BEFORE context around search results. In adjustment mode, `j`/`k` change by +1/-1 and `h`/`l` by -5/+5; `Escape` exits the mode. Bounds never go below zero. Global bounds apply side-by-side; zoom changes only the selected-port bounds. |
| `g` | Set or clear the global live display filter. |
| `p` | Set or clear the selected-port live display filter. |
| `Enter` | Apply the active find or live filter. Plain text is case-insensitive; `/pattern/` is a case-insensitive regex. |
| `Escape` | Exit context adjustment, cancel input, clear an active search, or restore the side-by-side layout. |
| `q` | Quit. |

TX, RX, ACK, NACK, and common log levels are highlighted. Live filters affect only new TUI lines, never the complete per-port log file. Each port retains up to 5,000 displayed lines for find/navigation; readers and disk logging continue independently.

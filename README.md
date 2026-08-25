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
| `p` | Pause or resume the selected port panel. |
| `Tab` / `1`–`9` | Focus and select a port panel. |
| `z` | Zoom the focused port to fill the available terminal; press again to restore the side-by-side layout. |
| `f` | Set or clear the global display filter. |
| `Shift+f` | Set or clear the selected port filter. |
| `Enter` | Apply the filter. Plain text is case-insensitive; `/pattern/` is a case-insensitive regex. |
| `Escape` | Cancel filter editing, or restore the side-by-side layout when a port is zoomed. |
| `q` | Quit. |

TX, RX, ACK, NACK, and common log levels are highlighted. Filters affect only new TUI lines, never the complete per-port log file.

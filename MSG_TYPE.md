# Gateway/edge wire message types

This is the authoritative message-type reference for the gateway/edge wire
protocol. The numeric values and symbols are taken from
`/W/NVT/espnow-master-slave/main/handshake_frame.h:29-44`. Direction describes
the sender role encoded in the frame; it is not inferred from a USB port name.

| Value | Symbol | Meaning | Direction | Payload / notes |
| ---: | --- | --- | --- | --- |
| 1 | `HANDSHAKE_MESSAGE_GATEWAY_BEACON` | Gateway discovery beacon | Gateway -> edge(s) | Exactly 1 byte: transport mode flags. Broadcast during discovery. |
| 2 | `HANDSHAKE_MESSAGE_EDGE_AVAILABLE` | Edge announces availability | Edge -> gateway | No payload. Broadcast during discovery. |
| 3 | `HANDSHAKE_MESSAGE_BIND_REQUEST` | Edge requests binding | Edge -> gateway | Exactly 3 bytes: bind correlation (`uint16_t`) and transport flags (`uint8_t`). |
| 4 | `HANDSHAKE_MESSAGE_BIND_ACCEPT` | Gateway accepts the bind request | Gateway -> edge | Exactly 3 bytes: bind correlation and transport flags. |
| 5 | `HANDSHAKE_MESSAGE_BIND_CONFIRM` | Edge confirms the bind | Edge -> gateway | Exactly 3 bytes: bind correlation and transport flags. |
| 6 | `HANDSHAKE_MESSAGE_EDGE_PACKET` | Edge test/sensor packet | Edge -> gateway | 0–64 bytes. The current test payload is JSON containing the sender MAC as `edge_id` and a voltage value. |
| 7 | `HANDSHAKE_MESSAGE_HEARTBEAT` | Edge liveness heartbeat | Edge -> gateway | Exactly 2 bytes: heartbeat correlation (`uint16_t`). |
| 8 | `HANDSHAKE_MESSAGE_HEARTBEAT_ACK` | Gateway heartbeat acknowledgement | Gateway -> edge | Exactly 6 bytes: correlation (`uint16_t`) plus gateway uptime (`uint32_t`). |
| 9 | `HANDSHAKE_MESSAGE_DATA_MESSAGE` | Edge application delivery message | Edge -> gateway | 29–229 bytes: 19-byte delivery ID, 8-byte timestamp, 1-byte payload length, then 0–200 bytes of application payload. |
| 10 | `HANDSHAKE_MESSAGE_DATA_ACK` | Gateway acknowledgement of a delivery ID | Gateway -> edge | Exactly 19 bytes: delivery ID. |
| 11 | `HANDSHAKE_MESSAGE_ERROR_FOUND` | Edge reports an undelivered message | Edge -> gateway | Exactly 20 bytes: lost delivery ID (19 bytes) plus a non-zero reason byte. |
| 12 | `HANDSHAKE_MESSAGE_FIELD_LOG` | Gateway sends a field-log record | Gateway -> edge | 7–102 bytes: correlation (`uint32_t`), flags, text length, and 1–96 bytes of text. |
| 13 | `HANDSHAKE_MESSAGE_FIELD_LOG_ACK` | Edge acknowledges a field-log record | Edge -> gateway | Exactly 4 bytes: field-log correlation (`uint32_t`). |
| 14 (implicit) | `HANDSHAKE_MESSAGE_COUNT` | Enumeration bound / array size | **Not a wire direction** | **Sentinel only. It is not a transmittable message type and must not be documented or parsed as one.** |

## Role/type validation

`handshake_frame.c:27-76` validates the frame's `role` and `type` together.
The `role` field identifies the sender role:

- Gateway-sender types are 1 (`GATEWAY_BEACON`), 4 (`BIND_ACCEPT`), 8
  (`HEARTBEAT_ACK`), and 10 (`DATA_ACK`).
- Every other wire type from 1 through 13 is an edge-sender type.
- Unknown values, values at or above `HANDSHAKE_MESSAGE_COUNT`, and roles other
  than `HANDSHAKE_ROLE_EDGE` or `HANDSHAKE_ROLE_GATEWAY` are rejected.
- The decoder also checks version, reserved byte, session/sequence values,
  sender-MAC agreement, frame length, payload length, and CRC.

The role/type check is protocol evidence about the claimed sender role. It does
not prove the physical identity of a serial port or establish a complete
topology by itself.

## Wire data versus diagnostic fake data

`HANDSHAKE_MESSAGE_EDGE_PACKET` and `HANDSHAKE_MESSAGE_DATA_MESSAGE` are wire
types. `FAKE_DATA` is not an additional wire type: it is a diagnostic label for
the current test application payload `DIAG_FAKE_DATA` carried inside a
`HANDSHAKE_MESSAGE_DATA_MESSAGE` frame. A real application payload uses the
same wire type but should be described as `DATA_MESSAGE`, not `FAKE_DATA`.

Consequently, logs may contain both the wire type (`type=9`,
`DATA_MESSAGE`) and a diagnostic event label (`FAKE_DATA`) when the payload is
the test payload. Do not treat `FAKE_DATA` as a value in the handshake message
enum, and do not confuse diagnostic delivery events with proof of a topology
or end-to-end outcome.

## Evidence labels

Interpreted records should label the strength of each identity or relationship
claim:

| Label | Use |
| --- | --- |
| `OBSERVED` | Directly present in the captured record or an explicitly observed device field. |
| `DECLARED` | A device or operator states the value, such as the frame role field or a startup identity record. |
| `CORRELATED` | Joined using explicit shared evidence, such as a delivery ID, MAC, session, or correlation value. |
| `UNKNOWN` | The available records do not establish the value. |
| `CONFLICTING` | Evidence asserts incompatible values; retain both facts rather than selecting one silently. |

No `PASS`/`FAIL` or topology claim is justified without explicit supporting
evidence.

## Startup identity record

The firmware already emits a startup record in `handshake_init()` at
`/W/NVT/espnow-master-slave/main/espnow_example_main.c:1992-2013`. Its current
form is:

```text
GPIO8 initial device=<MAC> role=<gateway|edge> level=... request=...
```

The `role` value is selected from the latched GPIO4 role
(`/W/NVT/espnow-master-slave/main/pin4_gateway_logic.c:3-7`), while GPIO8 is a
degraded-mode request/output concept. A separate firmware change should
normalize or rename this existing record into a canonical identity record,
without adding a duplicate identity line:

```text
INFO identity: device=<MAC> role=gateway role_source=gpio4_latched gpio4=HIGH
```

It should use the already-latched role and already-read Wi-Fi MAC, optionally
keeping degraded-mode fields separate. It must not resample GPIO4, change
protocol state, or enable runtime role switching. This documentation does not
claim that the firmware change is implemented; the LED indicator is
insufficient for serial correlation.

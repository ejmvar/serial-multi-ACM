"""Pure, conservative evidence extraction for retained inter-port histories."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Literal


SourceRef = tuple[str, int, str]
EvidenceStatus = Literal["OBSERVED", "UNINTERPRETED"]
RoleState = Literal["DECLARED", "UNKNOWN", "CONFLICTING"]
ReviewDecision = Literal["accepted", "rejected"]

_IDF_LINE = re.compile(r"^(I|W|E) \((\d+)\) ([^:]+): (.+)$")
_MAC = r"[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}"
_MAC_DASH = r"[0-9A-Fa-f]{2}(?:[-:][0-9A-Fa-f]{2}){5}"


@dataclass(frozen=True)
class HistoryEntry:
    """One retained raw event supplied by a caller, with stable source identity."""

    port: str
    retained_index: int
    timestamp: str
    raw_text: str

    @property
    def source(self) -> SourceRef:
        return (self.port, self.retained_index, self.timestamp)


@dataclass(frozen=True)
class EvidenceFields:
    """The small, versioned set of fields allowed by the evidence contract."""

    raw_text: str
    device_elapsed: int | None = None
    role_claim: str | None = None
    station_mac: str | None = None
    peer_mac: str | None = None
    direction: str | None = None
    protocol: str | None = None
    bind_state: str | None = None
    sample_id: str | None = None
    result: str | None = None
    role_state: RoleState = "UNKNOWN"


@dataclass(frozen=True)
class Evidence:
    source: SourceRef
    status: EvidenceStatus
    fields: EvidenceFields


@dataclass(frozen=True)
class CandidateLink:
    """An explicit, human-reviewable link; generation never accepts it."""

    identity: str
    status: Literal["candidate"]
    sources: tuple[SourceRef, ...]
    local_port: str
    peer_port: str
    mac: str
    direction: Literal["peer_to_local", "local_to_peer", "unknown"]


@dataclass(frozen=True)
class ReviewRecord:
    """An immutable human decision kept separate from captured evidence."""

    candidate_id: str
    decision: ReviewDecision
    sources: tuple[SourceRef, ...]
    reviewer: str
    decided_at: str


def _normalise_mac(value: str) -> str | None:
    if not re.fullmatch(_MAC_DASH, value):
        return None
    return value.replace("-", ":").lower()


def _extract_fields(entry: HistoryEntry, match: re.Match[str]) -> EvidenceFields | None:
    message = match.group(4)
    station_match = re.search(rf"\bWi-Fi station-MAC(?::\s*|\s+)({_MAC_DASH})(?![0-9A-Fa-f:-])", message, re.IGNORECASE)
    peer_match = re.search(rf"\bpeer(?:-MAC|\s+MAC)?\s*[=:]?\s*({_MAC_DASH})(?![0-9A-Fa-f:-])", message, re.IGNORECASE)
    send_match = re.search(r"\bsend\b.*?\bcompleted\b", message)
    if not peer_match and send_match:
        peer_match = re.search(rf"\bsend\b[^:]*?({_MAC_DASH})(?![0-9A-Fa-f:-])", message, re.IGNORECASE)
    station_mac = _normalise_mac(station_match.group(1)) if station_match else None
    peer_mac = _normalise_mac(peer_match.group(1)) if peer_match else None
    if station_match and station_mac is None or peer_match and peer_mac is None:
        return None

    role_claims = [token for token in ("pin4_gateway", "GPIO8") if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", message)]
    known = bool(station_mac or peer_mac or role_claims)
    protocol = next((token for token in ("ESP-NOW RX raw", "EDGE_PACKET", "FAKE_DATA", "ACK", "heartbeat") if token in message), None)
    bind_state = next((token for token in ("BOUND", "bind") if re.search(rf"(?<!\w){token}(?!\w)", message)), None)
    if send_match or protocol or bind_state:
        known = True
    direction: str | None = None
    if peer_mac and re.search(r"\bESP-NOW RX raw\b", message):
        direction = "peer_to_local"
    elif send_match and peer_mac:
        direction = "local_to_peer"
    sample_match = re.search(r"\b(?:EDGE_PACKET|FAKE_DATA)(?:\s+id)?[=: ]+([^\s]+)", message)
    result_match = re.search(r"\bresult[=: ]+([^\s]+)", message)
    if sample_match or result_match:
        known = True
    if not known:
        return None
    return EvidenceFields(
        raw_text=entry.raw_text,
        device_elapsed=int(match.group(2)),
        role_claim=role_claims[0] if role_claims else None,
        station_mac=station_mac,
        peer_mac=peer_mac,
        direction=direction,
        protocol=protocol,
        bind_state=bind_state,
        sample_id=sample_match.group(1) if sample_match else None,
        result=result_match.group(1) if result_match else None,
    )


def extract_evidence(entry: HistoryEntry) -> Evidence:
    """Extract one complete, whitelisted line; otherwise preserve it verbatim."""

    match = _IDF_LINE.fullmatch(entry.raw_text)
    fields = _extract_fields(entry, match) if match else None
    return Evidence(entry.source, "OBSERVED" if fields else "UNINTERPRETED", fields or EvidenceFields(entry.raw_text))


def inventory_evidence(histories: Mapping[str, Sequence[HistoryEntry]]) -> tuple[Evidence, ...]:
    """Adapt and extract histories, marking conflicting role declarations."""

    entries = adapt_histories(histories)
    evidence = [extract_evidence(entry) for entry in entries]
    roles: dict[str, set[str]] = {}
    for item in evidence:
        if item.fields.role_claim:
            claims = {
                token
                for token in ("pin4_gateway", "GPIO8")
                if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", item.fields.raw_text)
            }
            roles.setdefault(item.source[0], set()).update(claims)
    return tuple(
        Evidence(item.source, item.status, EvidenceFields(**{
            **item.fields.__dict__,
            "role_state": "CONFLICTING" if len(roles.get(item.source[0], set())) > 1 else ("DECLARED" if item.fields.role_claim else "UNKNOWN"),
        }))
        for item in evidence
    )


def generate_candidates(evidence: Sequence[Evidence]) -> tuple[CandidateLink, ...]:
    """Join only peer references to exactly one other port's station MAC."""

    stations: dict[str, set[str]] = {}
    for item in evidence:
        if item.status == "OBSERVED" and item.fields.station_mac:
            stations.setdefault(item.fields.station_mac, set()).add(item.source[0])
    grouped: dict[tuple[str, str, str, str], set[SourceRef]] = {}
    for item in evidence:
        mac = item.fields.peer_mac
        if item.status != "OBSERVED" or not mac or len(stations.get(mac, set())) != 1:
            continue
        local_port = next(iter(stations[mac]))
        peer_port = item.source[0]
        if local_port == peer_port:
            continue
        direction = item.fields.direction or "unknown"
        key = (local_port, peer_port, mac, direction)
        grouped.setdefault(key, set()).add(item.source)
    result: list[CandidateLink] = []
    for (local, peer, mac, direction), peer_sources in grouped.items():
        station_sources = {item.source for item in evidence if item.source[0] == local and item.fields.station_mac == mac}
        sources = tuple(sorted(station_sources | peer_sources))
        ref_text = ",".join(f"{port}:{index}:{timestamp}" for port, index, timestamp in sources)
        identity = f"local={local};peer={peer};mac={mac};direction={direction};sources={ref_text}"
        result.append(CandidateLink(identity, "candidate", sources, local, peer, mac, direction))
    return tuple(sorted(result, key=lambda candidate: candidate.identity))


def record_review(
    candidates: Sequence[CandidateLink],
    candidate_id: str,
    decision: ReviewDecision,
    reviewer: str,
    decided_at: str,
    sources: Sequence[SourceRef] | None = None,
) -> ReviewRecord:
    """Record an operator decision for an unchanged, generated candidate."""

    if decision not in ("accepted", "rejected"):
        raise ValueError("review decisions must be accepted or rejected")
    if not reviewer:
        raise ValueError("reviewer must be non-empty")
    if not decided_at:
        raise ValueError("decision timestamps must be non-empty")

    candidate = next((item for item in candidates if item.identity == candidate_id), None)
    if candidate is None or candidate.status != "candidate":
        raise ValueError("review must reference an existing candidate")
    if sources is not None and tuple(sources) != candidate.sources:
        raise ValueError("review source references must match the candidate")
    return ReviewRecord(candidate.identity, decision, candidate.sources, reviewer, decided_at)


def _source_text(source: SourceRef) -> str:
    return f"{source[0]}:{source[1]}:{source[2]}"


def _field_text(value: object) -> str:
    return "-" if value is None else str(value)


def render_preview(
    inventory: Sequence[Evidence],
    candidates: Sequence[CandidateLink],
    reviews: Sequence[ReviewRecord] = (),
) -> str:
    """Render the deterministic aligned-list representation for UI/export use."""

    lines = [
        "INTER-PORT EVIDENCE REVIEW | input=PARTIAL_RETAINED",
        "EVIDENCE",
        "timestamp | port | index | status | device_local | role | station_mac | peer_mac | direction | protocol | bind | sample_id | result | raw",
    ]
    ordered_inventory = sorted(inventory, key=lambda item: item.source)
    for item in ordered_inventory:
        fields = item.fields
        lines.append(
            " | ".join((
                item.source[2], item.source[0], str(item.source[1]), item.status,
                _field_text(fields.device_elapsed), _field_text(fields.role_state),
                _field_text(fields.station_mac), _field_text(fields.peer_mac),
                _field_text(fields.direction), _field_text(fields.protocol),
                _field_text(fields.bind_state), _field_text(fields.sample_id),
                _field_text(fields.result), fields.raw_text,
            ))
        )

    lines.extend(("CANDIDATES", "status | identity | sources"))
    for candidate in sorted(candidates, key=lambda item: item.identity):
        lines.append(f"{candidate.status} | {candidate.identity} | {','.join(map(_source_text, candidate.sources))}")

    lines.extend(("REVIEWS", "decision | candidate_id | reviewer | decided_at | sources"))
    for review in sorted(reviews, key=lambda item: (item.candidate_id, item.decided_at, item.reviewer, item.decision)):
        lines.append(
            f"{review.decision} | {review.candidate_id} | {review.reviewer} | "
            f"{review.decided_at} | {','.join(map(_source_text, review.sources))}"
        )
    return "\n".join(lines) + "\n"


def adapt_histories(histories: Mapping[str, Sequence[HistoryEntry]]) -> tuple[HistoryEntry, ...]:
    """Validate, de-duplicate, and deterministically order supplied histories."""

    by_source: dict[SourceRef, HistoryEntry] = {}
    for port_key, events in histories.items():
        if not isinstance(port_key, str) or not port_key:
            raise ValueError("port keys must be non-empty strings")

        indexes: set[int] = set()
        for event in events:
            if not isinstance(event, HistoryEntry):
                raise TypeError("history entries must be HistoryEntry instances")
            if event.port != port_key:
                raise ValueError("history key does not match event port")
            if not event.timestamp:
                raise ValueError("event timestamps must be non-empty")
            if event.retained_index < 0:
                raise ValueError("retained indexes must be non-negative")
            if event.retained_index in indexes:
                source = event.source
                previous = by_source.get(source)
                if previous != event:
                    raise ValueError("retained indexes must be unique within a port")
                continue
            indexes.add(event.retained_index)
            source = event.source
            previous = by_source.get(source)
            if previous is not None and previous != event:
                raise ValueError("source references must identify one raw event")
            by_source[source] = event

    return tuple(sorted(by_source.values(), key=lambda event: event.source))

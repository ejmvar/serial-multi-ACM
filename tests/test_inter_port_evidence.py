from dataclasses import FrozenInstanceError

import pytest

from serial_terminal.inter_port_evidence import (
    CandidateLink,
    Evidence,
    EvidenceFields,
    HistoryEntry,
    ReviewRecord,
    SourceRef,
    adapt_histories,
    generate_candidates,
    inventory_evidence,
    record_review,
    render_preview,
)


def entry(port: str, index: int, timestamp: str, text: str) -> HistoryEntry:
    return HistoryEntry(port=port, retained_index=index, timestamp=timestamp, raw_text=text)


def test_contract_records_are_frozen_and_preserve_source_reference() -> None:
    source: SourceRef = ("/dev/ttyACM0", 7, "2026-08-31T12:00:00+00:00")
    record = Evidence(
        source=source,
        status="UNINTERPRETED",
        fields=EvidenceFields(raw_text="partial input"),
    )

    assert record.source == source
    assert record.fields.raw_text == "partial input"
    with pytest.raises(FrozenInstanceError):
        record.source = ("other", 0, source[2])  # type: ignore[misc]


def test_adapter_validates_key_event_port_timestamp_index_and_deduplicates_sources() -> None:
    histories = {
        "port-a": [
            entry("port-a", 2, "2026-08-31T12:00:02+00:00", "same text"),
            entry("port-a", 2, "2026-08-31T12:00:02+00:00", "same text"),
            entry("port-a", 3, "2026-08-31T12:00:03+00:00", "same text"),
        ]
    }

    assert adapt_histories(histories) == (
        entry("port-a", 2, "2026-08-31T12:00:02+00:00", "same text"),
        entry("port-a", 3, "2026-08-31T12:00:03+00:00", "same text"),
    )

    invalid_cases = (
        {"port-a": [entry("port-b", 0, "2026-08-31T12:00:00+00:00", "text")]},
        {"port-a": [entry("port-a", 0, "", "text")]},
        {"port-a": [entry("port-a", -1, "2026-08-31T12:00:00+00:00", "text")]},
        {
            "port-a": [
                entry("port-a", 0, "2026-08-31T12:00:00+00:00", "first"),
                entry("port-a", 0, "2026-08-31T12:00:01+00:00", "different source"),
            ]
        },
    )
    for invalid in invalid_cases:
        with pytest.raises(ValueError):
            adapt_histories(invalid)


def test_adapter_keeps_distinct_references_for_identical_raw_text_and_orders_sources() -> None:
    histories = {
        "z-port": [entry("z-port", 1, "2026-08-31T12:00:01+00:00", "same")],
        "a-port": [
            entry("a-port", 4, "2026-08-31T12:00:01+00:00", "same"),
            entry("a-port", 0, "2026-08-31T12:00:00+00:00", "same"),
        ],
    }

    assert adapt_histories(histories) == (
        entry("a-port", 0, "2026-08-31T12:00:00+00:00", "same"),
        entry("a-port", 4, "2026-08-31T12:00:01+00:00", "same"),
        entry("z-port", 1, "2026-08-31T12:00:01+00:00", "same"),
    )


def test_adapter_rejects_empty_port_keys_and_unstructured_entries() -> None:
    with pytest.raises(ValueError):
        adapt_histories({"": [entry("", 0, "2026-08-31T12:00:00+00:00", "text")]})

    with pytest.raises(TypeError):
        adapt_histories({"port": ["raw text"]})  # type: ignore[list-item]


def test_inventory_extracts_only_complete_whitelisted_idf_records() -> None:
    histories = {
        "port-a": [
            entry("port-a", 0, "2026-08-31T12:00:00Z", "I (17) wifi: Wi-Fi station-MAC: AA:BB:CC:DD:EE:01"),
            entry("port-a", 1, "2026-08-31T12:00:01Z", "W (18) app: pin4_gateway GPIO8"),
            entry("port-a", 2, "2026-08-31T12:00:02Z", "I (19) app: ESP-NOW RX raw peer=aa-bb-cc-dd-ee-02"),
            entry("port-a", 3, "2026-08-31T12:00:03Z", "I (20) app: send AA:BB:CC:DD:EE:03 completed"),
        ],
        "port-b": [
            entry("port-b", 0, "2026-08-31T12:00:04Z", "I (21) app: heartbeat"),
            entry("port-b", 1, "2026-08-31T12:00:05Z", "not a complete ESP-IDF line"),
            entry("port-b", 2, "2026-08-31T12:00:06Z", "I (22) app: unsupported protocol event"),
            entry("port-b", 3, "2026-08-31T12:00:07Z", "\x1b[31mI (23) app: ACK\x1b[0m"),
        ],
    }

    evidence = inventory_evidence(histories)

    assert [item.status for item in evidence] == ["OBSERVED", "OBSERVED", "OBSERVED", "OBSERVED", "OBSERVED", "UNINTERPRETED", "UNINTERPRETED", "UNINTERPRETED"]
    assert evidence[0].fields.station_mac == "aa:bb:cc:dd:ee:01"
    assert evidence[1].fields.role_claim == "pin4_gateway"
    assert evidence[1].fields.role_state == "CONFLICTING"
    assert evidence[2].fields.peer_mac == "aa:bb:cc:dd:ee:02"
    assert evidence[3].fields.direction == "local_to_peer"
    assert evidence[4].fields.device_elapsed == 21
    assert evidence[5].fields.raw_text == "not a complete ESP-IDF line"


def test_inventory_handles_mac_forms_roles_and_local_uncertainty_without_inference() -> None:
    histories = {
        "a": [
            entry("a", 0, "2026-08-31T12:00:00Z", "I (1) wifi: Wi-Fi station-MAC AA-BB-CC-DD-EE-FF"),
            entry("a", 1, "2026-08-31T12:00:01Z", "I (2) app: GPIO8"),
            entry("a", 2, "2026-08-31T12:00:02Z", "I (3) app: ACK"),
        ],
        "b": [
            entry("b", 0, "2026-08-31T12:00:00Z", "I (1) app: ESP-NOW RX raw peer=aa:bb:cc:dd:ee:ff"),
            entry("b", 1, "2026-08-31T12:00:01Z", "I (2) app: send completed"),
        ],
    }

    evidence = inventory_evidence(histories)
    assert evidence[0].fields.station_mac == "aa:bb:cc:dd:ee:ff"
    by_source = {item.source: item for item in evidence}
    assert by_source[("a", 1, "2026-08-31T12:00:01Z")].fields.role_state == "DECLARED"
    assert by_source[("a", 2, "2026-08-31T12:00:02Z")].fields.protocol == "ACK"
    assert by_source[("b", 0, "2026-08-31T12:00:00Z")].fields.direction == "peer_to_local"
    assert by_source[("b", 1, "2026-08-31T12:00:01Z")].status == "OBSERVED"
    assert by_source[("b", 1, "2026-08-31T12:00:01Z")].fields.direction is None


def test_candidates_require_unique_explicit_mac_owner_and_are_deterministic() -> None:
    histories = {
        "b": [entry("b", 5, "2026-08-31T12:00:05Z", "I (8) espnow: ESP-NOW RX raw peer=AA:BB:CC:DD:EE:FF")],
        "a": [entry("a", 2, "2026-08-31T12:00:02Z", "I (9) wifi: Wi-Fi station-MAC: aa:bb:cc:dd:ee:ff")],
    }
    evidence = inventory_evidence(histories)
    candidates = generate_candidates(evidence)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert isinstance(candidate, CandidateLink)
    assert candidate.status == "candidate"
    assert candidate.local_port == "a"
    assert candidate.peer_port == "b"
    assert candidate.direction == "peer_to_local"
    assert candidate.sources == (evidence[0].source, evidence[1].source)
    assert "aa:bb:cc:dd:ee:ff" in candidate.identity

    no_link = inventory_evidence({
        "a": [entry("a", 0, "2026-08-31T12:00:00Z", "I (10) app: GPIO8 EDGE_PACKET id=7")],
        "b": [entry("b", 0, "2026-08-31T12:00:00Z", "I (10) app: ACK result=OK")],
    })
    assert generate_candidates(no_link) == ()


def test_ambiguous_station_owner_and_same_port_reference_never_link() -> None:
    evidence = inventory_evidence({
        "a": [entry("a", 0, "2026-08-31T12:00:00Z", "I (1) wifi: Wi-Fi station-MAC AA:BB:CC:DD:EE:FF")],
        "c": [entry("c", 0, "2026-08-31T12:00:01Z", "I (2) wifi: Wi-Fi station-MAC aa:bb:cc:dd:ee:ff")],
        "b": [entry("b", 0, "2026-08-31T12:00:02Z", "I (3) app: ESP-NOW RX raw peer=aa:bb:cc:dd:ee:ff")],
        "d": [entry("d", 0, "2026-08-31T12:00:03Z", "I (4) app: ESP-NOW RX raw peer=11:22:33:44:55:66")],
    })

    assert generate_candidates(evidence) == ()


def test_reviews_are_immutable_human_decisions_for_existing_candidates() -> None:
    evidence = inventory_evidence({
        "b": [entry("b", 0, "2026-08-31T12:00:01Z", "I (2) app: ESP-NOW RX raw peer=AA:BB:CC:DD:EE:FF")],
        "a": [entry("a", 0, "2026-08-31T12:00:00Z", "I (1) wifi: Wi-Fi station-MAC AA:BB:CC:DD:EE:FF")],
    })
    candidate = generate_candidates(evidence)[0]

    review = record_review(
        (candidate,), candidate.identity, "accepted", "operator-1", "2026-08-31T12:01:00Z"
    )

    assert isinstance(review, ReviewRecord)
    assert review.candidate_id == candidate.identity
    assert review.decision == "accepted"
    assert review.sources == candidate.sources
    assert review.reviewer == "operator-1"
    with pytest.raises(FrozenInstanceError):
        review.decision = "rejected"  # type: ignore[misc]

    rejected = record_review(
        (candidate,), candidate.identity, "rejected", "operator-2", "2026-08-31T12:02:00Z"
    )
    assert rejected.decision == "rejected"
    assert candidate.status == "candidate"
    assert evidence[0].fields.raw_text.endswith("EE:FF")


def test_review_rejects_unknown_or_invalid_references_and_non_human_inputs() -> None:
    candidate = CandidateLink(
        "candidate-1", "candidate", (("a", 0, "2026-08-31T12:00:00Z"),), "a", "b", "aa:bb:cc:dd:ee:ff", "unknown"
    )
    with pytest.raises(ValueError):
        record_review((candidate,), "missing", "accepted", "operator", "2026-08-31T12:00:00Z")
    with pytest.raises(ValueError):
        record_review((candidate,), candidate.identity, "candidate", "operator", "2026-08-31T12:00:00Z")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        record_review((candidate,), candidate.identity, "accepted", "", "2026-08-31T12:00:00Z")
    with pytest.raises(ValueError):
        record_review((candidate,), candidate.identity, "accepted", "operator", "")
    invalid_sources = CandidateLink(
        candidate.identity, candidate.status, (("other", 1, "2026-08-31T12:00:01Z"),), candidate.local_port,
        candidate.peer_port, candidate.mac, candidate.direction
    )
    with pytest.raises(ValueError):
        record_review(
            (candidate,), candidate.identity, "accepted", "operator", "2026-08-31T12:00:00Z",
            invalid_sources.sources,
        )


def test_render_preview_is_sorted_byte_stable_and_exposes_uncertainty_without_verdicts() -> None:
    histories = {
        "b": [entry("b", 1, "2026-08-31T12:00:01Z", "I (2) app: ESP-NOW RX raw peer=AA:BB:CC:DD:EE:FF")],
        "a": [
            entry("a", 0, "2026-08-31T12:00:00Z", "I (1) wifi: Wi-Fi station-MAC AA:BB:CC:DD:EE:FF"),
            entry("a", 2, "2026-08-31T12:00:02Z", "I (3) app: unsupported protocol event"),
        ],
    }
    evidence = inventory_evidence(histories)
    candidates = generate_candidates(evidence)
    review = record_review((candidates[0],), candidates[0].identity, "rejected", "operator", "2026-08-31T12:03:00Z")

    first = render_preview(evidence, candidates, (review,))
    permuted = inventory_evidence({"a": list(reversed(histories["a"])), "b": histories["b"]})
    second = render_preview(permuted, generate_candidates(permuted), (review,))

    assert first == second
    assert "PARTIAL_RETAINED" in first
    assert "UNINTERPRETED" in first
    assert "rejected" in first
    assert "candidate" in first
    assert "12:00:00Z" in first and "12:00:01Z" in first
    assert all(word not in first for word in ("PASS", "FAIL", "causal", "complete", "fault", "graph", "report", "live-state"))

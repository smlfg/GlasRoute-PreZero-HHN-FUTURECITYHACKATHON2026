"""Disponent approval behaviour: the agent proposes, the human disposes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from prezero.approval import (
    ApprovalError,
    approve_route,
    load_proposal,
    propose_route,
    rejection_record,
)


def route_fixture() -> dict:
    """Minimal route payload with the fields the approval needs."""
    return {
        "date": "2026-04-15",
        "num_stops": 2,
        "planned_km": 12.5,
        "saved_km": 4.25,
        "saved_pct": 25.4,
        "vehicles_needed": 1,
        "shift_hours": 6.25,
        "t_collected": 9.2,
        "total_critical_locations": 169,
        "comparison": "12.50 km planned (2 stops) vs. 16.75 km full round (431 stops)",
        "stops": [
            {
                "order": 1,
                "stop_type": "collection",
                "Location_id": "A",
                "lat": 49.14,
                "lon": 9.21,
                "score": 0.91,
                "primary_material": "white",
                "leg_km": 0.5,
                "cumulative_km": 0.5,
            },
            {
                "order": 2,
                "stop_type": "collection",
                "Location_id": "B",
                "lat": 49.15,
                "lon": 9.22,
                "score": 0.77,
                "primary_material": "green",
                "leg_km": 1.0,
                "cumulative_km": 1.5,
            },
        ],
    }


def test_proposal_is_not_yet_an_approved_route(tmp_path: Path) -> None:
    proposal = propose_route(route_fixture())
    assert proposal["status"] == "proposed"
    assert proposal["approved"] is False
    assert proposal["date"] == "2026-04-15"
    assert proposal["stops"], "the proposal carries the proposed stops"


def test_approval_writes_record_with_evidence(tmp_path: Path) -> None:
    proposal = propose_route(route_fixture())
    record = approve_route(
        proposal,
        approved_by="disponent-1",
        output_dir=tmp_path,
    )
    assert record["status"] == "approved"
    assert record["approved"] is True
    assert record["approved_by"] == "disponent-1"
    assert record["approved_at"], "the approval carries a timestamp"
    # Evidence: the decisive numbers travel with the record.
    assert record["evidence"]["saved_km"] == 4.25
    assert record["evidence"]["saved_pct"] == 25.4
    assert record["evidence"]["num_stops"] == 2
    assert record["evidence"]["planned_km"] == 12.5
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text(encoding="utf-8"))["status"] == "approved"


def test_approval_does_not_mutate_the_proposal(tmp_path: Path) -> None:
    proposal = propose_route(route_fixture())
    approve_route(proposal, approved_by="disponent-1", output_dir=tmp_path)
    assert proposal["status"] == "proposed"
    assert proposal["approved"] is False


def test_rejection_discards_the_proposal_and_records_reason(tmp_path: Path) -> None:
    proposal = propose_route(route_fixture())
    record = rejection_record(
        proposal,
        rejected_by="disponent-1",
        reason="Stop 7 ist nicht erreichbar",
        output_dir=tmp_path,
    )
    assert record["status"] == "rejected"
    assert record["approved"] is False
    assert record["reason"] == "Stop 7 ist nicht erreichbar"
    assert record["rejected_at"]
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text(encoding="utf-8"))["status"] == "rejected"


def test_approval_requires_a_decision_reason_for_rejection(tmp_path: Path) -> None:
    proposal = propose_route(route_fixture())
    with pytest.raises(ApprovalError):
        rejection_record(
            proposal,
            rejected_by="disponent-1",
            reason="",
            output_dir=tmp_path,
        )
    assert not list(tmp_path.glob("*.json")), "no record without a reason"


def test_proposal_round_trips_through_disk(tmp_path: Path) -> None:
    proposal = propose_route(route_fixture())
    path = tmp_path / "proposal.json"
    proposal_path = proposal["proposal_path"] if "proposal_path" in proposal else None
    assert proposal_path is None or Path(proposal_path).exists() is False
    # Writing and reading a proposal preserves the payload.
    path.write_text(json.dumps(proposal), encoding="utf-8")
    loaded = load_proposal(path)
    assert loaded["date"] == "2026-04-15"
    assert loaded["status"] == "proposed"
    assert len(loaded["stops"]) == 2

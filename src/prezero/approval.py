"""Disponent approval: the agent proposes, the human disposes.

This is the Human-Agent-Interface step of GlasRoute. The route engine produces
a *proposal*; nothing becomes an executable route until a dispatcher confirms
it. Every decision is written as a record carrying the decisive numbers, so
the pitch can point at evidence instead of claims.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

APPROVED = "approved"
PROPOSED = "proposed"
REJECTED = "rejected"

#: The numbers that decide whether a proposal is worth acting on.
EVIDENCE_FIELDS = (
    "planned_km",
    "saved_km",
    "saved_pct",
    "num_stops",
    "vehicles_needed",
    "shift_hours",
    "max_vehicle_shift_hours",
    "t_collected",
    "total_critical_locations",
    "comparison",
)


class ApprovalError(RuntimeError):
    """Raised when a decision cannot be recorded."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _evidence(route_data: Mapping[str, Any]) -> dict[str, Any]:
    return {field: route_data.get(field) for field in EVIDENCE_FIELDS if field in route_data}


def propose_route(route_data: Mapping[str, Any]) -> dict[str, Any]:
    """Wrap a route payload as a proposal awaiting dispatcher confirmation."""
    proposal = dict(route_data)
    proposal["status"] = PROPOSED
    proposal["approved"] = False
    proposal["proposed_at"] = _now()
    proposal["evidence"] = _evidence(route_data)
    return proposal


def load_proposal(path: str | Path) -> dict[str, Any]:
    """Read a proposal that was written to disk."""
    file_path = Path(path)
    if not file_path.is_file():
        raise ApprovalError(f"Proposal does not exist: {file_path}")
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if payload.get("status") != PROPOSED:
        raise ApprovalError(f"Not a proposal (status={payload.get('status')}): {file_path}")
    return payload


def _write_record(record: Mapping[str, Any], output_dir: str | Path, prefix: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = str(record["date"])
    target = directory / f"{prefix}_{stamp}.json"
    target.write_text(json.dumps(dict(record), indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def approve_route(
    proposal: Mapping[str, Any],
    approved_by: str,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Confirm a proposal and write the approval record with its evidence."""
    if not approved_by:
        raise ApprovalError("Approval needs an approver")
    if proposal.get("status") != PROPOSED:
        raise ApprovalError(f"Only a proposal can be approved (status={proposal.get('status')})")

    record = dict(proposal)
    record["status"] = APPROVED
    record["approved"] = True
    record["approved_by"] = approved_by
    record["approved_at"] = _now()
    record["evidence"] = _evidence(proposal)
    record_path = _write_record(record, output_dir, "approval")
    record["record_path"] = str(record_path)
    return record


def rejection_record(
    proposal: Mapping[str, Any],
    rejected_by: str,
    reason: str,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Reject a proposal and write the record including the stated reason."""
    if not rejected_by:
        raise ApprovalError("Rejection needs a decision maker")
    if not reason:
        raise ApprovalError("Rejection needs a reason")
    if proposal.get("status") != PROPOSED:
        raise ApprovalError(f"Only a proposal can be rejected (status={proposal.get('status')})")

    record = dict(proposal)
    record["status"] = REJECTED
    record["approved"] = False
    record["rejected_by"] = rejected_by
    record["reason"] = reason
    record["rejected_at"] = _now()
    record["evidence"] = _evidence(proposal)
    record_path = _write_record(record, output_dir, "rejection")
    record["record_path"] = str(record_path)
    return record


def format_proposal_summary(proposal: Mapping[str, Any]) -> str:
    """Human-readable summary of a proposal for the dispatcher."""
    evidence = proposal.get("evidence", {})
    lines = [
        f"Route proposal for {proposal.get('date')}",
        f"  stops:          {evidence.get('num_stops')}",
        f"  planned:        {evidence.get('planned_km')} km",
        f"  saved:          {evidence.get('saved_km')} km ({evidence.get('saved_pct')} %)",
        f"  vehicles:       {evidence.get('vehicles_needed')}",
        f"  vehicle hours:  {evidence.get('shift_hours')} (sum over all vehicles)",
        f"  longest shift:  {evidence.get('max_vehicle_shift_hours', '-')} h",
        f"  collected:      {evidence.get('t_collected')} t",
        f"  comparison:     {evidence.get('comparison')}",
    ]
    return "\n".join(lines)

"""API endpoints for the SI-vs-BL Comparison Requests view."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import ComparisonCase, Email, get_db
from backend.schemas import ComparisonCaseOut, ComparisonListOut, ComparisonResolveIn
from pipeline.comparison import FIELD_KEYS

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


def serialize_case(record: ComparisonCase, body: str = "") -> ComparisonCaseOut:
    return ComparisonCaseOut(
        email_id=record.email_id,
        sender=record.sender,
        subject=record.subject,
        si_file=record.si_file,
        bl_file=record.bl_file,
        status=record.status,
        has_defect=record.has_defect,
        defect_fields=record.defect_field_list(),
        review_reason=record.review_reason,
        fields=record.field_list(),
        is_resolved=record.is_resolved,
        body=body,
        error=record.review_reason,
    )


def _email_bodies(db: Session, email_ids: list[str]) -> dict[str, str]:
    """Map email_id -> full body so list responses avoid N+1 queries."""
    if not email_ids:
        return {}
    rows = db.query(Email.email_id, Email.body).filter(Email.email_id.in_(email_ids)).all()
    return {email_id: body for email_id, body in rows}


@router.get("", response_model=ComparisonListOut)
def list_comparison_cases(
    status: str | None = None,
    search: str | None = None,
    include_resolved: bool = False,
    db: Session = Depends(get_db),
) -> ComparisonListOut:
    query = db.query(ComparisonCase)
    if not include_resolved:
        query = query.filter(ComparisonCase.is_resolved.is_(False))
    if status:
        query = query.filter(ComparisonCase.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (ComparisonCase.sender.ilike(pattern))
            | (ComparisonCase.subject.ilike(pattern))
            | (ComparisonCase.email_id.ilike(pattern))
        )
    records = query.order_by(ComparisonCase.email_id).all()
    bodies = _email_bodies(db, [record.email_id for record in records])
    return ComparisonListOut(
        items=[serialize_case(record, body=bodies.get(record.email_id, "")) for record in records],
        total=len(records),
    )


@router.get("/stats")
def comparison_stats(db: Session = Depends(get_db)) -> dict[str, int]:
    rows = db.query(ComparisonCase.status, ComparisonCase.id).all()
    counts = {"OK": 0, "MISMATCH": 0, "NEEDS_REVIEW": 0, "total": len(rows)}
    for status, _ in rows:
        counts[status] = counts.get(status, 0) + 1
    counts["resolved"] = db.query(ComparisonCase).filter(ComparisonCase.is_resolved.is_(True)).count()
    return counts


@router.get("/{email_id}", response_model=ComparisonCaseOut)
def get_comparison_case(email_id: str, db: Session = Depends(get_db)) -> ComparisonCaseOut:
    record = db.query(ComparisonCase).filter(ComparisonCase.email_id == email_id).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Comparison case not found")
    email = db.query(Email).filter(Email.email_id == email_id).one_or_none()
    return serialize_case(record, body=email.body if email else "")


@router.post("/{email_id}/resolve", response_model=ComparisonCaseOut)
def resolve_comparison_case(
    email_id: str,
    payload: ComparisonResolveIn,
    db: Session = Depends(get_db),
) -> ComparisonCaseOut:
    record = db.query(ComparisonCase).filter(ComparisonCase.email_id == email_id).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Comparison case not found")

    if payload.fields:
        corrected = _apply_field_corrections(record, payload.fields)
        record.fields = json.dumps(corrected, ensure_ascii=False)
        record.has_defect = any(entry["status"] == "mismatch" for entry in corrected)
        record.defect_fields = json.dumps(
            [entry["name"] for entry in corrected if entry["status"] == "mismatch"],
            ensure_ascii=False,
        )
        record.status = "MISMATCH" if record.has_defect else "OK"

    record.is_resolved = True
    db.commit()
    db.refresh(record)
    email = db.query(Email).filter(Email.email_id == email_id).one_or_none()
    return serialize_case(record, body=email.body if email else "")


def _apply_field_corrections(record: ComparisonCase, corrections: dict[str, str]) -> list[dict[str, str]]:
    """Overwrite BL values with the human-entered corrections and re-verify."""
    rows = record.field_list()
    by_name = {row["name"]: row for row in rows}
    for name, value in corrections.items():
        if name not in by_name or name not in FIELD_KEYS:
            continue
        row = by_name[name]
        row["bl"] = value or "—"
        si = row.get("si", "")
        bl = row.get("bl", "")
        missing = _is_missing(si) or _is_missing(bl)
        row["status"] = "review" if missing else ("match" if _eq(si, bl) else "mismatch")
    return rows


def _is_missing(value: str) -> bool:
    return value in {"", "—", "-", "--", "n/a", "missing", "nil", "none", "tbd", "unknown"}


def _eq(a: str, b: str) -> bool:
    def clean(value: str) -> str:
        return "".join(ch for ch in value.strip().casefold() if ch.isalnum())

    return clean(a) == clean(b)

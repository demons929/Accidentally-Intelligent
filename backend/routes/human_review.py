from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import Email, get_db
from backend.schemas import HumanReviewOut, HumanReviewResolveIn


router = APIRouter(prefix="/api/human-review", tags=["human-review"])


def serialize_review(record: Email) -> HumanReviewOut:
    return HumanReviewOut(
        id=record.id,
        email_id=record.email_id,
        sender=record.sender,
        subject=record.subject,
        preview=record.preview,
        body=record.body,
        category=record.category,
        status=record.status,
        received_time=record.received_time.isoformat(),
        is_human_review=record.is_human_review,
        review_type=record.review_type,
        is_resolved=record.is_resolved,
        confidence=record.confidence,
        attachments=json.loads(record.attachments or "[]"),
        error=record.error,
        review_remark=record.review_remark,
    )


def _review_cases(db: Session, review_type: str | None = None, resolved: bool | None = False) -> list[HumanReviewOut]:
    query = db.query(Email).filter(Email.is_human_review.is_(True))
    if review_type:
        query = query.filter(Email.review_type == review_type)
    if resolved is not None:
        query = query.filter(Email.is_resolved.is_(resolved))
    return [serialize_review(record) for record in query.order_by(Email.email_id).all()]


@router.get("", response_model=list[HumanReviewOut])
def list_review_cases(include_resolved: bool = False, db: Session = Depends(get_db)) -> list[HumanReviewOut]:
    return _review_cases(db, resolved=None if include_resolved else False)


@router.get("/unreadable", response_model=list[HumanReviewOut])
def unreadable_cases(db: Session = Depends(get_db)) -> list[HumanReviewOut]:
    return _review_cases(db, review_type="unreadable", resolved=False)


@router.get("/corrupted", response_model=list[HumanReviewOut])
def corrupted_cases(db: Session = Depends(get_db)) -> list[HumanReviewOut]:
    return _review_cases(db, review_type="corrupted", resolved=False)


@router.get("/resolved", response_model=list[HumanReviewOut])
def resolved_cases(db: Session = Depends(get_db)) -> list[HumanReviewOut]:
    return _review_cases(db, resolved=True)


@router.post("/{email_id}/resolve", response_model=HumanReviewOut)
def resolve_case(email_id: str, payload: HumanReviewResolveIn | None = None, db: Session = Depends(get_db)) -> HumanReviewOut:
    record = db.query(Email).filter((Email.email_id == email_id) | (Email.id == _int_or_none(email_id))).one_or_none()
    if record is None or not record.is_human_review:
        raise HTTPException(status_code=404, detail="Human review case not found")
    record.is_resolved = True
    record.status = "Classified" if record.category else "Pending"
    if payload is not None and payload.remark:
        record.review_remark = payload.remark
    db.commit()
    db.refresh(record)
    return serialize_review(record)


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None

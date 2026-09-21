from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import Email, get_db
from backend.schemas import EmailOut, MoveEmailIn, PaginatedEmailsOut, SummaryOut
from config import get_settings
from pipeline import CANONICAL_CATEGORIES


router = APIRouter(tags=["emails"])
settings = get_settings()


def serialize_email(record: Email) -> EmailOut:
    return EmailOut(
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
    )


def _email_query(db: Session, category: str | None, search: str | None):
    query = db.query(Email)
    if category and category != "All":
        query = query.filter(Email.category == category)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Email.sender.ilike(pattern))
            | (Email.subject.ilike(pattern))
            | (Email.preview.ilike(pattern))
        )
    return query


@router.get("/api/emails", response_model=PaginatedEmailsOut)
def list_emails(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> PaginatedEmailsOut:
    query = _email_query(db, category, search)
    total = query.count()
    records = (
        query.order_by(Email.received_time.desc(), Email.email_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedEmailsOut(
        items=[serialize_email(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/api/emails/stats", response_model=SummaryOut)
def email_stats(db: Session = Depends(get_db)) -> SummaryOut:
    category_counts = {category: 0 for category in CANONICAL_CATEGORIES}
    for category, count in db.query(Email.category, Email.id).all():
        if category in category_counts:
            category_counts[category] += 1

    pending_review = db.query(Email).filter(
        Email.is_human_review.is_(True),
        Email.is_resolved.is_(False),
    )
    review_counts = {"unreadable": 0, "corrupted": 0, "resolved": 0, "pending": 0}
    for record in pending_review.all():
        review_counts["pending"] += 1
        if record.review_type in {"unreadable", "corrupted"}:
            review_counts[record.review_type] += 1
    review_counts["resolved"] = db.query(Email).filter(
        Email.is_human_review.is_(True),
        Email.is_resolved.is_(True),
    ).count()

    return SummaryOut(
        total=sum(category_counts.values()),
        categories=category_counts,
        human_review=review_counts,
    )


@router.post("/api/emails/{email_id}/move", response_model=EmailOut)
def move_email(email_id: str, payload: MoveEmailIn, db: Session = Depends(get_db)) -> EmailOut:
    if payload.category not in CANONICAL_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Unknown category: {payload.category}")
    record = db.query(Email).filter((Email.email_id == email_id) | (Email.id == _int_or_none(email_id))).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Email not found")
    record.category = payload.category
    record.status = "Classified"
    record.is_human_review = False
    record.review_type = None
    db.commit()
    db.refresh(record)
    return serialize_email(record)


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


@router.get("/api/inbox", response_model=PaginatedEmailsOut)
def list_inbox_alias(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> PaginatedEmailsOut:
    return list_emails(category=category, search=search, page=page, page_size=page_size, db=db)


@router.get("/api/inbox/summary", response_model=SummaryOut)
def inbox_summary_alias(db: Session = Depends(get_db)) -> SummaryOut:
    return email_stats(db=db)

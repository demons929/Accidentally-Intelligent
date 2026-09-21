"""SQLite setup and SQLAlchemy models for the HarryPort backend."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from config import get_settings


settings = get_settings()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Email(Base):
    """One classified email shown in the Inbox / Human Review views."""

    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    sender: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(500), default="")
    preview: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str | None] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="Classified", index=True)
    received_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    is_human_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    review_type: Mapped[str | None] = mapped_column(String(40), index=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    attachments: Mapped[str] = mapped_column(Text, default="[]")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


EmailRecord = Email


class ComparisonCase(Base):
    """SI-vs-BL verification case for a Comparison request email.

    The seven compared fields are defined in pipeline.comparison.FIELD_NAMES.
    `fields` stores the per-field detail as JSON so the frontend can render
    the field-by-field table without extra queries.
    """

    __tablename__ = "comparison_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    sender: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(500), default="")
    si_file: Mapped[str] = mapped_column(String(255), default="")
    bl_file: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(40), default="NEEDS_REVIEW", index=True)  # OK | MISMATCH | NEEDS_REVIEW
    has_defect: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    defect_fields: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str]
    review_reason: Mapped[str | None] = mapped_column(String(80))
    fields: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of field rows
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    compared_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def defect_field_list(self) -> list[str]:
        return list(json.loads(self.defect_fields or "[]"))

    def field_list(self) -> list[dict[str, Any]]:
        return list(json.loads(self.fields or "[]"))


def init_db() -> None:
    _recreate_emails_table_if_schema_changed()
    Base.metadata.create_all(bind=engine)


def _recreate_emails_table_if_schema_changed() -> None:
    """Recreate the emails table when its schema drifted from the model.

    Only used during local development; keeps the app robust across branches
    that evolved the Email model without a migration system.
    """
    required_columns = {
        "email_id",
        "sender",
        "subject",
        "preview",
        "body",
        "category",
        "status",
        "received_time",
        "is_human_review",
        "review_type",
        "is_resolved",
    }
    inspector = inspect(engine)
    if "emails" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("emails")}
    if required_columns.issubset(existing_columns):
        return
    Base.metadata.drop_all(bind=engine, tables=[Email.__table__])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def upsert_email_records(db: Session, records: list[Email]) -> None:
    """Insert or update emails keyed by the unique email_id column."""
    for incoming in records:
        existing = db.query(Email).filter(Email.email_id == incoming.email_id).one_or_none()
        if existing is None:
            db.add(incoming)
            continue
        for field in [
            "sender",
            "subject",
            "preview",
            "body",
            "category",
            "confidence",
            "status",
            "received_time",
            "is_human_review",
            "review_type",
            "is_resolved",
            "attachments",
            "error",
        ]:
            value = getattr(incoming, field)
            if field == "received_time" and value is None:
                continue
            setattr(existing, field, value)
    db.commit()


def upsert_comparison_cases(db: Session, cases: Sequence[ComparisonCase]) -> None:
    """Insert or update comparison cases keyed by the unique email_id column."""
    for incoming in cases:
        existing = db.query(ComparisonCase).filter(ComparisonCase.email_id == incoming.email_id).one_or_none()
        if existing is None:
            db.add(incoming)
            continue
        for field in [
            "sender",
            "subject",
            "si_file",
            "bl_file",
            "status",
            "has_defect",
            "defect_fields",
            "review_reason",
            "fields",
            "is_resolved",
        ]:
            setattr(existing, field, getattr(incoming, field))
        if incoming.compared_at is not None:
            existing.compared_at = incoming.compared_at
    db.commit()

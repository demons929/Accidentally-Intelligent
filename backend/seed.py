"""Seeding helpers shared by ``run_pipeline.py`` and the FastAPI startup hook.

Both entry points funnel through these functions so the SQLite database always
reflects the same pipeline output regardless of which command started it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.database import ComparisonCase, Email, upsert_comparison_cases, upsert_email_records
from config import Settings, get_settings
from pipeline.comparison import analyze_email
from pipeline.inference import Prediction, predict_directory


def prediction_to_email(prediction: Prediction) -> Email:
    is_human_review = prediction.status == "HUMAN_REVIEW"
    review_type = None
    if prediction.review_reason == "Unreadable Attachment":
        review_type = "unreadable"
    elif prediction.review_reason == "Corrupted Email":
        review_type = "corrupted"
    return Email(
        email_id=prediction.email_id,
        sender=prediction.sender,
        subject=prediction.subject or prediction.email_id,
        preview=prediction.preview,
        body=prediction.body,
        category=prediction.category,
        status="Pending" if is_human_review else "Classified",
        received_time=datetime.now(UTC).replace(tzinfo=None),
        is_human_review=is_human_review,
        review_type=review_type,
        is_resolved=False,
        confidence=prediction.confidence,
        attachments=json.dumps(prediction.attachments or []),
        error=prediction.error,
    )


def seed_emails_from_pipeline(db: Session, settings: Settings | None = None) -> int:
    """Classify the inbox corpus and upsert every email into the database."""
    settings = settings or get_settings()
    input_dir = settings.data_dir / "inbox"
    if not input_dir.exists():
        input_dir = settings.test_dir
    if not input_dir.exists():
        return 0
    predictions = predict_directory(input_dir, base_dir=settings.data_dir)
    records = [prediction_to_email(prediction) for prediction in predictions]
    upsert_email_records(db, records)
    return len(records)


def seed_comparison_cases(db: Session, settings: Settings | None = None) -> int:
    """Run SI-vs-BL verification for every Comparison request email."""
    settings = settings or get_settings()
    emails = (
        db.query(Email)
        .filter(Email.category == "Comparison requests")
        .order_by(Email.email_id)
        .all()
    )
    cases: list[ComparisonCase] = []
    payloads: list[dict] = []
    for email in emails:
        try:
            attachments = json.loads(email.attachments or "[]")
        except json.JSONDecodeError:
            attachments = []
        result = analyze_email(
            email_id=email.email_id,
            sender=email.sender,
            subject=email.subject,
            attachment_paths=[str(item) for item in attachments],
            base_dir=settings.data_dir,
        )
        payload = result.to_case_dict()
        payloads.append(payload)
        cases.append(
            ComparisonCase(
                email_id=payload["email_id"],
                sender=payload["sender"],
                subject=payload["subject"],
                si_file=payload["si_file"],
                bl_file=payload["bl_file"],
                status=payload["status"],
                has_defect=payload["has_defect"],
                defect_fields=json.dumps(payload["defect_fields"], ensure_ascii=False),
                review_reason=payload["review_reason"],
                fields=json.dumps(payload["fields"], ensure_ascii=False),
                is_resolved=False,
            )
        )
    upsert_comparison_cases(db, cases)
    # Sync review flags onto the emails table so the Human Review queue shows
    # every case a human must look at, with its exact reason:
    #   unreadable / wrong_doc_type / missing_attachment / missing_value.
    for payload in payloads:
        email = db.query(Email).filter(Email.email_id == payload["email_id"]).one_or_none()
        if email is None:
            continue
        reason = payload["review_reason"]
        genuine = payload["status"] == "NEEDS_REVIEW" and reason
        # A "missing attachment" escalation is a genuine edge case only when the
        # email explicitly asked to compare an SI and a BL (e.g. "Please compare
        # the SI and draft BL ... attachments dropped"). A routine "please send
        # the draft BL" follow-up with no docs is not a human-review defect.
        if genuine and reason == "missing_attachment":
            text = f"{email.subject or ''} {email.body or ''}".casefold()
            genuine = "compare" in text and (
                "si" in text or "draft bl" in text or "bill of lading" in text
            )
        if genuine:
            email.is_human_review = True
            email.review_type = reason
            email.status = "Pending"
        elif email.review_type in {"wrong_doc_type", "missing_attachment", "missing_value"}:
            # No longer a review case (e.g. after a re-parse) -> drop the flag.
            email.is_human_review = False
            email.review_type = None
            email.status = "Classified"
    db.commit()
    # Sync: drop any persisted case whose email is no longer a Comparison
    # request (e.g. a retrained pipeline reclassified it). Keeps the table
    # canonical instead of accumulating stale rows across re-seeds.
    valid_ids = {case.email_id for case in cases}
    stale = (
        db.query(ComparisonCase)
        .filter(ComparisonCase.email_id.notin_(valid_ids))
        .delete(synchronize_session=False)
        if valid_ids
        else db.query(ComparisonCase).delete(synchronize_session=False)
    )
    db.commit()
    if stale:
        print(f"[seed] removed {stale} stale comparison case(s).")
    return len(cases)

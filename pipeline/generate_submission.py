"""Format pipeline predictions into ``submission.json``.

Three output shapes are supported (switch with ``HARRYPORT_SUBMISSION_FORMAT``):

* ``standard_list`` (default, project brief format)
      [{"email_id": "email_001", "category": "New SI requests"}, ...]

* ``organizer``  (SDOC bundle / docker scoring format)
      {"email_001": {"category": "BL_COMPARISON", "status": "OK",
                     "review_reason": null, "defect_fields": [],
                     "has_defect": false}, ...}

* ``legacy_mapping``
      {"email_001": {"email_id": "email_001", "category": "..."}, ...}

``submission_category_style`` additionally switches the category values between
the dashboard names (``frontend``) and the competition codes (``organizer``).
"""

from __future__ import annotations

import json
from pathlib import Path

from config import get_settings
from pipeline.inference import Prediction

# Dashboard category name -> competition category code
SUBMISSION_CATEGORY_MAP = {
    "Comparison requests": "BL_COMPARISON",
    "New SI requests": "SI_REQUEST",
    "Invoice queries": "INVOICE_QUERY",
    "General mail": "GENERAL",
    "Spam": "SPAM",
}

# Pipeline review reasons -> bundle review reasons
REVIEW_REASON_MAP = {
    "Unreadable Attachment": "unreadable",
    "Corrupted Email": "unreadable",
}


def _category_for(prediction: Prediction) -> str:
    settings = get_settings()
    category = prediction.category or "General mail"
    if settings.submission_category_style == "organizer":
        return SUBMISSION_CATEGORY_MAP.get(category, "GENERAL")
    return category


def _review_reason_for(prediction: Prediction) -> str | None:
    return REVIEW_REASON_MAP.get(prediction.review_reason or "")


def prediction_to_submission_item(
    prediction: Prediction,
    comparison_map: dict[str, dict] | None = None,
) -> dict:
    """Convert one prediction into one submission entry.

    ``comparison_map`` maps email_id -> comparison result dict (the payload of
    ``ComparisonResult.to_case_dict()``) and is only used by the ``organizer``
    format for Comparison request emails.
    """
    settings = get_settings()

    if settings.submission_format == "organizer":
        return _organizer_item(prediction, comparison_map or {})

    if prediction.status == "HUMAN_REVIEW":
        item: dict = {
            "email_id": prediction.email_id,
            "category": None,
        }
        if settings.submission_include_review_metadata:
            item.update(
                {
                    "status": "Pending",
                    "review_type": prediction.review_reason,
                }
            )
        return item

    return {
        "email_id": prediction.email_id,
        "category": _category_for(prediction),
    }


def _organizer_item(prediction: Prediction, comparison_map: dict[str, dict]) -> dict:
    """Bundle-compatible entry: category + verification outcome + defects."""
    comparison = comparison_map.get(prediction.email_id)

    if prediction.status == "HUMAN_REVIEW":
        return {
            "category": _category_for(prediction),
            "status": "NEEDS_REVIEW",
            "review_reason": _review_reason_for(prediction),
            "defect_fields": [],
            "has_defect": False,
        }

    if prediction.category == "Comparison requests" and comparison:
        return {
            "category": _category_for(prediction),
            "status": comparison["status"],
            "review_reason": comparison.get("review_reason"),
            "defect_fields": comparison.get("defect_fields", []),
            "has_defect": comparison.get("has_defect", False),
        }

    return {
        "category": _category_for(prediction),
        "status": "OK",
        "review_reason": None,
        "defect_fields": [],
        "has_defect": False,
    }


def write_submission(
    predictions: list[Prediction],
    output_path: Path,
    comparison_map: dict[str, dict] | None = None,
) -> list[dict] | dict:
    """Write the submission file and return the written payload."""
    settings = get_settings()
    comparison_map = comparison_map or {}
    ordered = sorted(predictions, key=lambda item: item.email_id)

    if settings.submission_format in {"organizer", "legacy_mapping"}:
        submission: list[dict] | dict = {
            prediction.email_id: prediction_to_submission_item(prediction, comparison_map)
            for prediction in ordered
        }
    else:
        submission = [prediction_to_submission_item(prediction, comparison_map) for prediction in ordered]

    output_path.write_text(json.dumps(submission, indent=2, ensure_ascii=False), encoding="utf-8")
    return submission

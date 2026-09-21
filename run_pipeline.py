"""Main pipeline: classify the test inbox, verify Comparison requests,
save everything to SQLite, and write ``submission.json``.

Usage:
    python run_pipeline.py
    python run_pipeline.py --input-dir data/test --output submission.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.database import SessionLocal, init_db
from backend.seed import seed_comparison_cases, seed_emails_from_pipeline
from config import get_settings
from pipeline.generate_submission import write_submission
from pipeline.inference import Prediction, predict_directory


def _has_email_files(path: Path) -> bool:
    return path.exists() and any(path.glob("*.json"))


def _collect_predictions(input_dir: Path, base_dir: Path | None) -> list[Prediction]:
    if _has_email_files(input_dir):
        return predict_directory(input_dir, base_dir=base_dir or input_dir.parent)
    settings = get_settings()
    fallback = settings.data_dir / "inbox"
    return predict_directory(fallback, base_dir=settings.data_dir)


def _load_comparison_map() -> dict[str, dict]:
    """Read the persisted comparison cases back into a map for submission."""
    from backend.database import ComparisonCase, SessionLocal as _SessionLocal

    with _SessionLocal() as db:
        rows = db.query(ComparisonCase).all()
    return {
        row.email_id: {
            "email_id": row.email_id,
            "status": row.status,
            "has_defect": row.has_defect,
            "defect_fields": row.defect_field_list(),
            "review_reason": row.review_reason,
        }
        for row in rows
    }


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run HarryPort email inference, verify comparisons, write submission.json")
    parser.add_argument("--input-dir", type=Path, default=settings.test_dir)
    parser.add_argument("--base-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=settings.submission_path)
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Only write submission.json; do not touch the SQLite database",
    )
    args = parser.parse_args()

    predictions = _collect_predictions(args.input_dir, args.base_dir)

    if not args.skip_db:
        init_db()
        with SessionLocal() as db:
            seeded = seed_emails_from_pipeline(db)
            compared = seed_comparison_cases(db)
        print(f"SQLite: {seeded} emails, {compared} comparison cases.")

    comparison_map = _load_comparison_map()
    submission = write_submission(predictions, args.output, comparison_map=comparison_map)

    review_count = sum(1 for item in predictions if item.status == "HUMAN_REVIEW")
    comparison_count = sum(1 for item in predictions if item.category == "Comparison requests")
    print(
        f"Wrote {args.output} ({len(submission)} entries, format={settings.submission_format!r}) "
        f"with {comparison_count} comparison requests and {review_count} human-review cases."
    )


if __name__ == "__main__":
    main()

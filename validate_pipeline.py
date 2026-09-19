#!/usr/bin/env python3
import argparse
import importlib.util
import json
import sys
from pathlib import Path

from pipeline_final import CATEGORIES, REQUIRED_FIELDS, run_pipeline


VALID_STATUSES = {"OK", "MISMATCH", "NEEDS_REVIEW"}
VALID_REVIEW_REASONS = {
    None,
    "wrong_doc_type",
    "missing_attachment",
    "unreadable",
    "missing_value",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def schema_errors(submission, sample=None):
    errors = []

    if not isinstance(submission, dict):
        return ["submission must be a JSON object keyed by email_id"]

    if sample is not None:
        expected = set(sample)
        actual = set(submission)
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            errors.append(f"missing {len(missing)} email ids, first few: {missing[:10]}")
        if extra:
            errors.append(f"extra {len(extra)} email ids, first few: {extra[:10]}")

    for eid, row in submission.items():
        if not isinstance(row, dict):
            errors.append(f"{eid}: value must be an object")
            continue

        category = row.get("category")
        status = row.get("status")
        review_reason = row.get("review_reason")
        has_defect = row.get("has_defect")
        defect_fields = row.get("defect_fields")

        if category not in CATEGORIES:
            errors.append(f"{eid}: invalid category {category!r}")
        if status not in VALID_STATUSES:
            errors.append(f"{eid}: invalid status {status!r}")
        if review_reason not in VALID_REVIEW_REASONS:
            errors.append(f"{eid}: invalid review_reason {review_reason!r}")
        if not isinstance(has_defect, bool):
            errors.append(f"{eid}: has_defect must be boolean")
        if not isinstance(defect_fields, list):
            errors.append(f"{eid}: defect_fields must be a list")
        elif any(field not in REQUIRED_FIELDS for field in defect_fields):
            bad = [field for field in defect_fields if field not in REQUIRED_FIELDS]
            errors.append(f"{eid}: invalid defect_fields {bad!r}")

        if status == "MISMATCH" and not has_defect:
            errors.append(f"{eid}: MISMATCH should have has_defect=true")
        if has_defect and not defect_fields:
            errors.append(f"{eid}: has_defect=true should include defect_fields")
        if status != "NEEDS_REVIEW" and review_reason is not None:
            errors.append(f"{eid}: review_reason should be null unless NEEDS_REVIEW")
        if status == "NEEDS_REVIEW" and review_reason is None:
            errors.append(f"{eid}: NEEDS_REVIEW should include review_reason")

    return errors


def import_scoring(scoring_path):
    scoring_path = Path(scoring_path)
    spec = importlib.util.spec_from_file_location("sdoc_scoring", scoring_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def print_score(score):
    stage1 = score["stage1"]
    stage3 = score["stage3"]
    reliability = score["reliability"]
    e2e = score["end_to_end"]

    print("\nLocal score")
    print(f"  final_score       : {score['final_score']:.4f}")
    print(f"  stage1 macro-F1   : {stage1['macro_f1']:.4f}")
    print(f"  stage1 accuracy   : {stage1['accuracy']:.4f}")
    print(f"  defect F1         : {stage3['defect_f1']:.4f}")
    print(f"  field F1          : {stage3['field_f1']:.4f}")
    print(f"  end-to-end        : {e2e['success']}/{e2e['total']} ({e2e['rate']:.4f})")
    print(f"  escalation F1     : {reliability['escalation_f1']:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Validate and optionally score the SDOC pipeline.")
    parser.add_argument("--source", default="resources/sdoc-hackathon-bundle")
    parser.add_argument("--output", default="submission.json")
    parser.add_argument("--ground-truth", default="resources/sdoc-hackathon-docker/data_v2/ground_truth.json")
    parser.add_argument("--scoring", default="resources/sdoc-hackathon-docker/server/scoring.py")
    parser.add_argument("--schema-only", action="store_true", help="skip local scoring even if ground truth exists")
    args = parser.parse_args()

    print(f"Running pipeline on: {args.source}")
    submission = run_pipeline(args.source, args.output)
    print(f"Wrote {len(submission)} rows to: {args.output}")

    sample_path = Path(args.source) / "sample_submission.json"
    sample = load_json(sample_path) if sample_path.exists() else None
    errors = schema_errors(submission, sample)

    if errors:
        print("\nSchema validation failed:")
        for err in errors[:50]:
            print(f"  - {err}")
        if len(errors) > 50:
            print(f"  ... plus {len(errors) - 50} more")
        return 1

    print("\nSchema validation passed.")

    gt_path = Path(args.ground_truth)
    scoring_path = Path(args.scoring)
    if args.schema_only:
        return 0
    if not gt_path.exists() or not scoring_path.exists():
        print("\nLocal scoring skipped because ground-truth/scoring files were not found.")
        return 0

    truth = load_json(gt_path)
    scoring = import_scoring(scoring_path)
    score = scoring.score_all(truth, submission)
    print_score(score)

    return 0 if abs(score["final_score"] - 1.0) < 1e-12 else 2


if __name__ == "__main__":
    sys.exit(main())

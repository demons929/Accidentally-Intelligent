"""Generalisation smoke test: unseen, synthetic emails must classify cleanly.

The competition corpus was used to tune extraction rules; this test proves the
pipeline is not memorising that dataset. Every email below is freshly written
with different subjects, attachment names and document layouts that do NOT
appear in the corpus.

Run:  python tests/test_generalization.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.comparison import analyze_email  # noqa: E402
from pipeline.inference import EmailClassifier  # noqa: E402

SI_TEXT = """SHIPPING INSTRUCTION
Shipper: Global Freight Forwarders Pte Ltd
Consignee: Meridian Trading Corp, P.O. BOX 41200, JEBEL ALI, DUBAI, UAE
Notify Party: Meridian Trading Corp
Port of Loading: SHANGHAI, CHINA
Port of Discharge: ROTTERDAM, NETHERLANDS
No. of Containers: 3 x 40'HC
Gross Weight (KG): 66,000
"""

BL_TEXT = """BILL OF LADING (DRAFT)
B/L NO: OOLU0000001234
Shipper/Exporter (发货人)
Global Freight Forwarders Pte Ltd
Consignee (Non-Negotiable) (收货人)
Meridian Trading Corp, P.O. BOX 41200
JEBEL ALI, DUBAI, UAE
Notify (通知人)
Meridian Trading Corp
Port of Loading (装货港)
SHANGHAI, CHINA
Discharge Port (卸货港)
ROTTERDAM, NETHERLANDS
No. of Containers (箱数)
3 x 40'HC
Gross Wt (kgs) (毛重 KGS)
66,000
"""

# Same-line label + value layout (like a scanned PDF, no colon):
BL_SAMELINE = """BILL OF LADING
Shipper/Exporter Global Freight Forwarders Pte Ltd
Consignee (Non-Negotiable) Meridian Trading Corp, P.O. BOX 41200, JEBEL ALI, DUBAI, UAE
Notify Party Meridian Trading Corp
POL SHANGHAI, CHINA
POD ROTTERDAM, NETHERLANDS
Container Count: 3 x 40'HC
TOTAL Gross Weight (KG): 66,000 KG
"""

SI_BL_DIFFERENT = SI_TEXT.replace("Meridian Trading Corp", "Meridian Trading Corp", 1)
BL_DIFFERENT = BL_TEXT.replace("Meridian Trading Corp, P.O. BOX 41200", "Meridian Trading X Corp, P.O. BOX 41200", 1)

EMAILS: list[tuple[str, dict, str | None, str | None]] = [
    # (filename, payload, expected_category, expected_review_reason)
    (
        "new_001.json",
        {
            "email_id": "new_001",
            "from": "ops@global-freight.com",
            "subject": "Kindly check attached draft BL against our SI",
            "body": "Please verify the draft bill of lading matches the shipping instruction before we release.",
            "attachments": ["shipping_instruction.txt", "bill_of_lading.txt"],
        },
        "Comparison requests",
        None,
    ),
    (
        "new_002.json",
        {
            "email_id": "new_002",
            "from": "ops@global-freight.com",
            "subject": "BL check for booking OOLU0000001234",
            "body": "Please compare the bill of lading with our instructions.",
            "attachments": ["shipping_instruction.txt", "bill_of_lading_diff.txt"],
        },
        "Comparison requests",
        None,
    ),
    (
        "new_003.json",
        {
            "email_id": "new_003",
            "from": "shipping@acme-logistics.com",
            "subject": "Requesting SI for booking HLCU11223344",
            "body": "Please submit the shipping instruction for the new booking by EOD.",
            "attachments": ["SI_20260922.txt"],
        },
        "New SI requests",
        None,
    ),
    (
        "new_004.json",
        {
            "email_id": "new_004",
            "from": "finance@acme-logistics.com",
            "subject": "INV query - charges breakdown for October",
            "body": "Could you explain the terminal handling charge on invoice INV-1024? The payment deadline has passed.",
            "attachments": [],
        },
        "Invoice queries",
        None,
    ),
    (
        "new_005.json",
        {
            "email_id": "new_005",
            "from": "winner@promo-mail.example",
            "subject": "Congratulations! You have been selected for an exclusive offer",
            "body": "Claim your free gift within 24 hours by clicking here. Act now to verify your account.",
            "attachments": [],
        },
        "Spam",
        None,
    ),
    (
        "new_006.json",
        {
            "email_id": "new_006",
            "from": "port-ops@terminal.example",
            "subject": "Weekly port operations update",
            "body": "Berthing schedule and crane availability for next week are attached for your planning.",
            "attachments": [],
        },
        "General mail",
        None,
    ),
    (
        "new_007.json",
        {
            "email_id": "new_007",
            "from": "ops@global-freight.com",
            "subject": "Confirm docs for shipment MEDU123",
            "body": "Please confirm the documents for the above shipment.",
            "attachments": ["scanned_copy.bin"],
        },
        "Comparison requests",  # fallback category via subject signal
        "Unreadable Attachment",
    ),
    (
        "new_008.json",
        {
            "email_id": "new_008",
            "from": "",
            "subject": "",
            "body": "",
            "attachments": [],
        },
        None,  # corrupted -> no category
        "Corrupted Email",
    ),
    (
        "new_009.json",
        {
            "email_id": "new_009",
            "from": "ops@global-freight.com",
            "subject": "BL verification - draft attached",
            "body": "Draft bill of lading attached, please compare with SI.",
            "attachments": ["shipping_instruction.txt", "bl_sameline.txt"],
        },
        "Comparison requests",
        None,
    ),
]


def main() -> int:
    failed = 0
    with tempfile.TemporaryDirectory(prefix="harryport_gen_") as tmp:
        work = Path(tmp)
        (work / "shipping_instruction.txt").write_text(SI_TEXT, encoding="utf-8")
        (work / "bill_of_lading.txt").write_text(BL_TEXT, encoding="utf-8")
        (work / "bill_of_lading_diff.txt").write_text(BL_DIFFERENT, encoding="utf-8")
        (work / "bl_sameline.txt").write_text(BL_SAMELINE, encoding="utf-8")
        (work / "SI_20260922.txt").write_text(SI_TEXT, encoding="utf-8")
        (work / "scanned_copy.bin").write_bytes(b"\x00\xff\xfe garbage not a pdf " * 8)

        classifier = EmailClassifier()

        for filename, payload, expected_cat, expected_review in EMAILS:
            path = work / filename
            path.write_text(json.dumps(payload), encoding="utf-8")
            prediction = classifier.predict_file(path, base_dir=work)
            cat_ok = prediction.category == expected_cat
            review_ok = prediction.review_reason == expected_review
            status_ok = (
                prediction.status == "HUMAN_REVIEW"
                if expected_review
                else prediction.status == "OK"
            )
            ok = cat_ok and review_ok and status_ok
            failed += 0 if ok else 1
            print(
                f"{'PASS' if ok else 'FAIL'}  {filename:14s} category={prediction.category!r}"
                f" (want {expected_cat!r})  status={prediction.status}"
                f"  review={prediction.review_reason!r} (want {expected_review!r})"
            )

        # Comparison engine on new docs -------------------------------------
        result = analyze_email(
            email_id="new_001",
            sender="ops@global-freight.com",
            subject="BL check",
            attachment_paths=["shipping_instruction.txt", "bill_of_lading.txt"],
            base_dir=work,
        )
        ok = result.status == "OK" and not result.has_defect
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  analyze new matching SI/BL        status={result.status} defects={result.defect_fields}")

        result = analyze_email(
            email_id="new_002",
            sender="ops@global-freight.com",
            subject="BL check",
            attachment_paths=["shipping_instruction.txt", "bill_of_lading_diff.txt"],
            base_dir=work,
        )
        ok = result.status == "MISMATCH" and result.defect_fields == ["consignee"]
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  analyze new mismatch (consignee)   status={result.status} defects={result.defect_fields}")

        result = analyze_email(
            email_id="new_009",
            sender="ops@global-freight.com",
            subject="BL verification",
            attachment_paths=["shipping_instruction.txt", "bl_sameline.txt"],
            base_dir=work,
        )
        ok = result.status == "OK" and not result.has_defect
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  analyze same-line label+value BL   status={result.status} defects={result.defect_fields}")

    print()
    print("ALL PASS" if failed == 0 else f"{failed} CHECK(S) FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

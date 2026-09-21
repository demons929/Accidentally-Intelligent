from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from config import get_settings
from pipeline import CANONICAL_CATEGORIES, attachment_kind
from pipeline.preprocess import (
    CorruptedEmailError,
    ParsedEmail,
    UnreadableAttachmentError,
    build_model_text,
    clean_text,
    parse_email_file,
)


@dataclass
class Prediction:
    email_id: str
    category: str | None
    confidence: float
    status: str
    review_reason: str | None
    sender: str = ""
    subject: str = ""
    preview: str = ""
    body: str = ""
    attachments: list[str] | None = None
    error: str | None = None


class EmailClassifier:
    def __init__(self, model_dir: Path | None = None) -> None:
        self.settings = get_settings()
        self.model_dir = model_dir or self.settings.model_dir
        self.tokenizer = None
        self.model = None
        self.id2label = {index: label for index, label in enumerate(CANONICAL_CATEGORIES)}
        self._load_model_if_available()

    def _load_model_if_available(self) -> None:
        if not (self.model_dir / "config.json").exists():
            return
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_dir)
        self.model.eval()
        if getattr(self.model.config, "id2label", None):
            self.id2label = {int(key): value for key, value in self.model.config.id2label.items()}

    @property
    def using_transformer(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def predict_file(self, path: Path, base_dir: Path | None = None) -> Prediction:
        try:
            parsed = parse_email_file(path, base_dir=base_dir)
            return self.predict_parsed(parsed)
        except UnreadableAttachmentError as exc:
            return Prediction(
                email_id=path.stem,
                category=self._fallback_category(path),
                confidence=0.0,
                status="HUMAN_REVIEW",
                review_reason="Unreadable Attachment",
                body=self._raw_body(path),
                error=str(exc),
            )
        except CorruptedEmailError as exc:
            return Prediction(
                email_id=path.stem,
                category=self._fallback_category(path),
                confidence=0.0,
                status="HUMAN_REVIEW",
                review_reason="Corrupted Email",
                body=self._raw_body(path),
                error=str(exc),
            )

    def _raw_body(self, path: Path) -> str:
        """Best-effort full body for human-review cases whose attachment/body failed."""
        try:
            import json

            payload = json.loads(path.read_text(encoding="utf-8"))
            return clean_text(payload.get("body") or "")
        except Exception:
            return ""

    def _fallback_category(self, path: Path) -> str | None:
        """Best-effort category from the raw record when attachments/body broke.

        Keeps human-review cases routable (e.g. an unreadable BL PDF whose
        subject is a comparison request still counts as BL_COMPARISON).
        """
        try:
            import json

            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        subject = clean_text(payload.get("subject") or "").casefold()
        body = clean_text(payload.get("body") or "").casefold()[:400]
        text = f"{subject} {body}"
        if any(signal in text for signal in (
            "confirm docs", "draft bl", "bl draft", "amend bl", "request bl draft",
            "aie - ", "afrt - ", "afemy - ", "afptme - ",
        )):
            return "Comparison requests"
        if any(signal in text for signal in (
            "si - ", "si needed", "submit si", "request si", "cust si", "shipping instruction",
        )):
            return "New SI requests"
        if any(signal in text for signal in ("invoice", "billing", "charges", "payment", "debit", "credit note")):
            return "Invoice queries"
        if any(signal in text for signal in ("weird trick", "bitcoin", "lottery", "winner", "unsubscribe", "exclusive offer")):
            return "Spam"
        return None

    def predict_parsed(self, parsed: ParsedEmail) -> Prediction:
        if self.using_transformer:
            category, confidence = self._predict_with_transformer(build_model_text(parsed))
        else:
            category, confidence = self._predict_with_rules(parsed)

        return Prediction(
            email_id=parsed.email_id,
            category=category,
            confidence=confidence,
            status="OK",
            review_reason=None,
            sender=parsed.sender,
            subject=parsed.subject,
            preview=parsed.body[:240],
            body=parsed.body,
            attachments=parsed.attachments,
        )

    def _predict_with_transformer(self, text: str) -> tuple[str, float]:
        import torch

        assert self.tokenizer is not None and self.model is not None
        encoded = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=self.settings.max_sequence_length,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = self.model(**encoded).logits[0]
        probabilities = torch.softmax(logits, dim=-1)
        score, label_id = torch.max(probabilities, dim=-1)
        category = self.id2label.get(int(label_id), "General mail")
        confidence = float(score)
        if confidence < self.settings.confidence_threshold:
            return "General mail", confidence
        return category, confidence

    def _predict_with_rules(self, parsed: ParsedEmail) -> tuple[str, float]:
        # Strong structural signal: an email carrying BOTH a Shipping
        # Instruction and a Bill of Lading attachment is a Comparison request.
        attachment_kinds = [
            kind
            for path in (parsed.attachments or [])
            if (kind := attachment_kind(str(path))) is not None
        ]
        has_si = "SI" in attachment_kinds
        has_bl = "BL" in attachment_kinds
        if has_si and has_bl:
            return "Comparison requests", 0.92

        subject = (parsed.subject or "").casefold()
        subject_has_si_signal = any(
            signal in subject for signal in ("si - ", "si needed", "submit si", "cust si", "request si", "si:")
        )
        subject_has_cmp_signal = any(
            signal in subject for signal in (
                "confirm docs", "draft bl", "bl draft", "amend bl", "request bl draft",
                "aie - ", "afrt - ", "afemy - ", "afptme - ",
            )
        )

        # SI-only / BL-only emails: route by the subject instead of guessing.
        if has_si or has_bl:
            if subject_has_cmp_signal and not subject_has_si_signal:
                return "Comparison requests", 0.90
            if subject_has_si_signal:
                return "New SI requests", 0.90
            if subject_has_cmp_signal:
                return "Comparison requests", 0.90

        text = " ".join([parsed.subject, (parsed.body or ""), (parsed.attachment_text or "")]).casefold()

        # Strong general-mail signals (operations notices, RPA/reminder bots…)
        # are checked before keyword scoring so "billing"/"si" phrases inside
        # them do not hijack the category.
        for signal in (
            "update summary", "berthing report", "_reminder", "reminder_", "time off request",
            "approval required", "miss connection", "delivery planning", "pending bl release",
            "_rpa_", "rpa ",
        ):
            if signal in text:
                return "General mail", 0.90

        for signal in (
            "weird trick", "increase your", "bitcoin", "investment opportunity", "exclusive offer",
            "this week only", "premium logistics software", "one weird", "shipping revenue",
            "guaranteed", "limited time", "congratulations", "you have been selected", "act now",
            "update your account", "avoid suspension", "hot singles", "want to connect",
            "storage is full", "verify account", "undelivered messages", "your mailbox",
            "confirm your bank", "won a", "gift card", "claim now", "dear valued customer",
        ):
            if signal in text:
                return "Spam", 0.92

        scores = {category: 0.0 for category in CANONICAL_CATEGORIES}

        keyword_map = {
            "Comparison requests": [
                "compare", "comparison", "rate matrix", "quote", "quotation", "freight rate",
                "benchmark", "pricing comparison", "rate request",
                "draft bl", "bl draft", "amend bl", "confirm docs", "request bl draft",
            ],
            "New SI requests": [
                "shipping instruction", "shipping instructions", " si ", "si - ", "si needed",
                "submit si", "request si", "cust si", "bill of lading",
                "container", "vessel", "voyage",
            ],
            "Invoice queries": [
                "invoice", "inv-", "billing", "charges", "payment", "thc", "debit",
                "credit note", "breakdown", "local charge",
            ],
            "Spam": [
                "lottery", "winner", "free money", "crypto", "urgent offer", "marketing deal",
                "unsubscribe", "click here", "limited time",
            ],
        }
        for category, keywords in keyword_map.items():
            for keyword in keywords:
                if keyword in text:
                    scores[category] += 1.0

        if parsed.attachments:
            scores["New SI requests"] += 0.4
        if re.search(r"\b(re|fw):", subject):
            scores["General mail"] += 0.2

        best_category = max(scores, key=scores.get)
        if math.isclose(scores[best_category], 0.0):
            return "General mail", 0.55
        total = sum(scores.values()) or 1.0
        return best_category, min(0.97, 0.55 + scores[best_category] / total * 0.4)


def predict_directory(input_dir: Path, base_dir: Path | None = None) -> list[Prediction]:
    classifier = EmailClassifier()
    files = sorted(path for path in input_dir.glob("*") if path.suffix.lower() in {".json", ".eml", ".msg", ".txt"})
    return [classifier.predict_file(path, base_dir=base_dir or input_dir.parent) for path in files]

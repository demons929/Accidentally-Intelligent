from __future__ import annotations

import json
import re
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from config import get_settings


class CorruptedEmailError(ValueError):
    pass


class UnreadableAttachmentError(ValueError):
    pass


@dataclass
class ParsedEmail:
    email_id: str
    sender: str
    subject: str
    body: str
    attachments: list[str]
    attachment_text: str
    raw: dict[str, Any]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ")
    text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_email_file(path: Path, base_dir: Path | None = None) -> ParsedEmail:
    base_dir = base_dir or path.parent
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
        elif suffix in {".eml", ".msg"}:
            payload = _parse_mime_email(path)
        else:
            payload = {
                "email_id": path.stem,
                "from": "",
                "subject": path.stem,
                "body": path.read_text(encoding="utf-8", errors="replace"),
                "attachments": [],
            }
    except Exception as exc:
        raise CorruptedEmailError(f"MIME or JSON parsing failed for {path.name}: {exc}") from exc

    body = clean_text(payload.get("body", ""))
    if "\x00" in str(payload.get("body", "")) or not body and not payload.get("subject"):
        raise CorruptedEmailError("Email body is empty, null-byte corrupted, or unparseable")

    attachment_paths = [str(item) for item in payload.get("attachments", []) or []]
    attachment_texts = []
    for item in attachment_paths:
        attachment_path = (base_dir / item).resolve()
        if not attachment_path.exists():
            raise UnreadableAttachmentError(f"Attachment missing: {item}")
        attachment_texts.append(extract_attachment_text(attachment_path))

    return ParsedEmail(
        email_id=str(payload.get("email_id") or path.stem),
        sender=clean_text(payload.get("from") or payload.get("sender") or ""),
        subject=clean_text(payload.get("subject") or ""),
        body=body,
        attachments=attachment_paths,
        attachment_text="\n".join(text for text in attachment_texts if text),
        raw=payload,
    )


def _parse_mime_email(path: Path) -> dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    body_parts: list[str] = []
    attachments: list[str] = []
    for part in message.walk():
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if disposition == "attachment" and filename:
            attachments.append(filename)
            continue
        if part.get_content_type() in {"text/plain", "text/html"}:
            body_parts.append(part.get_content())
    return {
        "email_id": path.stem,
        "from": message.get("from", ""),
        "subject": message.get("subject", ""),
        "body": "\n".join(body_parts),
        "attachments": attachments,
    }


def extract_attachment_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".csv"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".xlsx", ".xls"}:
        return _extract_xlsx_text(path)
    if suffix == ".pdf":
        text = _extract_pdf_with_azure(path)
        if text.strip():
            return text
        text = _extract_pdf_with_pymupdf(path)
        if text.strip():
            return text
        raise UnreadableAttachmentError(f"No text could be extracted from PDF: {path.name}")
    if suffix == ".docx":
        return _extract_docx_text(path)
    raise UnreadableAttachmentError(f"Unsupported attachment type: {path.name}")


def _extract_xlsx_text(path: Path) -> str:
    """Read an xlsx workbook into a line-per-row text.

    Two-cell rows become ``Label: value`` so the field extractors' single-line
    patterns apply; multi-cell rows (container tables) keep one cell per line
    so per-row and next-line extraction both work.
    """
    try:
        frame_map = pd.read_excel(path, sheet_name=None, header=None)
    except Exception as exc:
        raise UnreadableAttachmentError(f"XLSX parsing failed for {path.name}: {exc}") from exc
    parts: list[str] = []
    for frame in frame_map.values():
        for row in frame.fillna("").itertuples(index=False):
            cells = [str(cell).strip() for cell in row if str(cell).strip()]
            if not cells:
                continue
            if len(cells) == 2:
                parts.append(f"{cells[0]}: {cells[1]}")
            else:
                parts.append(" | ".join(cells))
                parts.extend(cells)
    return "\n".join(parts)


def _extract_docx_text(path: Path) -> str:
    """Read a .docx preserving paragraph and line breaks (labels and values
    keep their own lines instead of being flattened into one long string)."""
    try:
        import zipfile
        import xml.etree.ElementTree as ET

        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        word_namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(word_namespace + "p"):
            pieces: list[str] = []
            for node in paragraph.iter():
                if node.tag == word_namespace + "t":
                    pieces.append(node.text or "")
                elif node.tag in {word_namespace + "br", word_namespace + "cr"}:
                    pieces.append("\n")
            text = "".join(pieces).strip()
            if text:
                paragraphs.append(text)
        if not paragraphs:
            raise UnreadableAttachmentError(f"DOCX contained no text: {path.name}")
        return "\n".join(paragraphs)
    except UnreadableAttachmentError:
        raise
    except Exception as exc:
        raise UnreadableAttachmentError(f"DOCX extraction failed for {path.name}: {exc}") from exc


def _extract_pdf_with_pymupdf(path: Path) -> str:
    try:
        try:
            import pymupdf as fitz
        except ModuleNotFoundError:
            import fitz

        with fitz.open(path) as document:
            if document.is_encrypted:
                raise UnreadableAttachmentError(f"Encrypted PDF: {path.name}")
            return "\n".join(page.get_text("text") for page in document)
    except UnreadableAttachmentError:
        raise
    except Exception:
        return ""


def _extract_pdf_with_azure(path: Path) -> str:
    settings = get_settings()
    if not settings.azure_form_recognizer_endpoint or not settings.azure_form_recognizer_key:
        return ""
    try:
        from azure.ai.formrecognizer import DocumentAnalysisClient
        from azure.core.credentials import AzureKeyCredential

        client = DocumentAnalysisClient(
            endpoint=settings.azure_form_recognizer_endpoint,
            credential=AzureKeyCredential(settings.azure_form_recognizer_key),
        )
        poller = client.begin_analyze_document("prebuilt-read", path.read_bytes())
        result = poller.result()
        return "\n".join(line.content for page in result.pages for line in page.lines)
    except Exception:
        return ""


def build_model_text(parsed: ParsedEmail) -> str:
    pieces = [
        f"From: {parsed.sender}",
        f"Subject: {parsed.subject}",
        f"Body: {parsed.body}",
    ]
    if parsed.attachment_text:
        pieces.append(f"Attachments: {clean_text(parsed.attachment_text)}")
    return "\n".join(pieces)

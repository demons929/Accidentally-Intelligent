"""Email classification pipeline for the HarryPort competition."""

import re

CANONICAL_CATEGORIES = [
    "Comparison requests",
    "New SI requests",
    "Invoice queries",
    "General mail",
    "Spam",
]

HUMAN_REVIEW_REASONS = ["Unreadable Attachment", "Corrupted Email"]

# --- attachment kind detection ----------------------------------------------
# The competition corpus names attachments ``*_SI.txt`` / ``*_BL.pdf``, but
# real inboxes also attach "shipping_instruction.pdf" or "Bill of Lading.xlsx".
# ``attachment_kind`` recognises both conventions so the classifier and the
# comparison engine do not depend on the corpus' exact naming.
_SI_BOUNDARY = re.compile(r"(?:^|[_/\s\-])si(?:$|[_/\s\-])", re.I)
_BL_BOUNDARY = re.compile(r"(?:^|[_/\s\-])bl(?:$|[_/\s\-])", re.I)


def attachment_kind(filename: str | None) -> str | None:
    """Return ``"SI"``, ``"BL"`` or ``None`` for an attachment filename.

    Matches the suffix convention (``xxx_SI.pdf``, ``SI_2026.txt``) as well as
    natural names (``shipping_instruction.pdf``, ``Bill of Lading.xlsx``,
    ``draft_bl_v2.docx``).
    """
    if not filename:
        return None
    stem = filename.strip().casefold()
    # Remove common extensions so "SI.txt" does not read as "SI" + junk.
    for ext in (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".csv", ".eml"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    stem = stem.strip(" _-")

    spaced = stem.replace("-", " ").replace("_", " ")
    if "shipping instruction" in spaced or spaced.endswith("instruction"):
        return "SI"
    if "bill of lading" in spaced or "lading" in spaced:
        return "BL"
    if _SI_BOUNDARY.search(stem):
        return "SI"
    if _BL_BOUNDARY.search(stem):
        return "BL"
    return None

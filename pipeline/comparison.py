"""SI-vs-BL document comparison for "Comparison requests".

The competition compares seven fields between the Shipping Instruction (SI)
and the draft Bill of Lading (BL) attachments of an email:

    shipper, consignee, notify_party, port_of_loading,
    port_of_discharge, container_count, gross_weight_kg

Both documents often label the same field differently (``Port of Loading`` vs
``Load Port``, ``No. of Containers or Packages`` vs ``Container Count``), so
fields are aligned by meaning, not by header text.

Outcome status follows the SDOC bundle contract:
    OK            -> all 7 fields match
    MISMATCH      -> at least one field differs (defect_fields lists them)
    NEEDS_REVIEW  -> the pipeline could not decide (review_reason set)

A blank / unreadable field is NOT a mismatch: the system genuinely cannot
decide, so NEEDS_REVIEW takes precedence over MISMATCH (matches the ground
truth semantics of the v2 dataset).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pipeline import attachment_kind
from pipeline.preprocess import UnreadableAttachmentError, extract_attachment_text

# ---------------------------------------------------------------------------
# Field catalogue
# ---------------------------------------------------------------------------

# key -> human readable label used by the frontend
FIELD_LABELS: list[tuple[str, str]] = [
    ("shipper", "Shipper"),
    ("consignee", "Consignee"),
    ("notify_party", "Notify Party"),
    ("port_of_loading", "Port of Loading"),
    ("port_of_discharge", "Port of Discharge"),
    ("container_count", "Container Count"),
    ("gross_weight_kg", "Gross Weight"),
]
FIELD_KEYS = [key for key, _ in FIELD_LABELS]

# key -> (same-line patterns, next-line label patterns)
# same-line:  "Label: value" on one line (value captured). ``[^\S\n]*`` keeps
#             the match on a single line so an empty "Label: " cannot swallow
#             the following line's content.
# next-line:  "Label" alone on a line, value is the following non-label lines.
# ``[^\S\n]*(?:\([^)]*\)[^\S\n]*)*`` tolerates translated label annotations, e.g.
# "Consignee (Non-Negotiable) (收货人)" or "Port of Discharge (POD) (卸货港)".
_FIELD_PATTERNS: dict[str, tuple[list[re.Pattern[str]], list[re.Pattern[str]]]] = {
    'shipper': (
        [
            re.compile('^\\s*shipper[^\\S\\n]*/[^\\S\\n]*exporter[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
            re.compile('^\\s*shipper[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
        ],
        [
            re.compile('^\\s*shipper[^\\S\\n]*/[^\\S\\n]*exporter[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
            re.compile('^\\s*shipper[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
        ],
    ),
    'consignee': (
        [
            re.compile('^\\s*consignee[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
            re.compile('^\\s*to[^\\S\\n]*the[^\\S\\n]*order[^\\S\\n]*of[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
        ],
        [
            re.compile('^\\s*consignee[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
            re.compile('^\\s*to[^\\S\\n]*the[^\\S\\n]*order[^\\S\\n]*of[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
        ],
    ),
    'notify_party': (
        [
            re.compile('^\\s*notify[^\\S\\n]*part(?:y|ies)?(?:[^\\S\\n]*/[^\\S\\n]*[^:\\n]+)?[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
            re.compile('^\\s*notify[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
        ],
        [
            re.compile('^\\s*notify[^\\S\\n]*part(?:y|ies)?(?:[^\\S\\n]*/[^\\S\\n]*[^:\\n]+)?[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
            re.compile('^\\s*notify[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
        ],
    ),
    'port_of_loading': (
        [
            re.compile('^\\s*port[^\\S\\n]*of[^\\S\\n]*loading[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
            re.compile('^\\s*(?:load[^\\S\\n]*port|pol)[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
        ],
        [
            re.compile('^\\s*port[^\\S\\n]*of[^\\S\\n]*loading[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
            re.compile('^\\s*(?:load[^\\S\\n]*port|pol)[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
        ],
    ),
    'port_of_discharge': (
        [
            re.compile('^\\s*(?:port[^\\S\\n]*of[^\\S\\n]*discharge|discharge[^\\S\\n]*port|pod)[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
        ],
        [
            re.compile('^\\s*(?:port[^\\S\\n]*of[^\\S\\n]*discharge|discharge[^\\S\\n]*port|pod)[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
        ],
    ),
    'container_count': (
        [
            re.compile('^\\s*no\\.?[^\\S\\n]*of[^\\S\\n]*containers?(?:[^\\S\\n]*or[^\\S\\n]*packages?)?[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
            re.compile('^\\s*total[^\\S\\n]+containers?[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
            re.compile('^\\s*total[^\\S\\n]+container[^\\S\\n]*count[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
            re.compile('^\\s*container[^\\S\\n]*count[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:[^\\S\\n]*(.+)$', re.I | re.M),
            re.compile('^\\s*containers?[^\\S\\n]*:[^\\S\\n]*(.+)$', re.I | re.M),
        ],
        [
            re.compile('^\\s*(?:no\\.?[^\\S\\n]*of[^\\S\\n]*containers?|total[^\\S\\n]+containers?|total[^\\S\\n]+container[^\\S\\n]*count|container[^\\S\\n]*count)(?:[^\\S\\n]*or[^\\S\\n]*packages?)?[^\\S\\n]*(?:\\([^)]*\\)[^\\S\\n]*)*:?\\s*$', re.I | re.M),
        ],
    ),
    'gross_weight_kg': (
        [
            re.compile('^\\s*(?:total[^\\S\\n]+)?gross[^\\S\\n]*(?:weight|wt\\.?)[^:\\n]*:[^\\S\\n]*(.+)$', re.I | re.M),
        ],
        [
            re.compile('^\\s*gross[^\\S\\n]*(?:weight|wt\\.?)[^:\\n]*:?\\s*$', re.I | re.M),
        ],
    ),
}

# Lines that look like another document label (used to stop the next-line scan)
_LABEL_LIKE = re.compile(
    r"^\s*(?:shipper|consignee|notify|to\s*the\s*order|port\s*of|load\s*port|pol|pod|discharge\s*port|"
    r"no\.?\s*of\s*containers|total\s+containers?|total\s+container\s*count|container\s*count|containers?|"
    r"gross\s*weight|gross\s*wt|net\s*weight|vessel|ocean\s*vessel|voyage|kinds\s*of|commodity|description|"
    r"bill\s*of\s*lading|b/l\s*number|b/l\s*no|booking|freight|hs\s*code|oc\s*no|order\s*no|"
    r"export\s*carrier|container\s*no)",
    re.I,
)

# After a "GROSS WEIGHT (KG)" table header: stop summing at these lines
_STOP_AFTER_WEIGHT = re.compile(
    r"^\s*(?:total\s+containers?|total\s+container\s*count|total\s+gross|no\.?\s*of\s*containers|"
    r"container\s*count|gross\s*weight|gross\s*wt|hs\s*code|freight|oc\s*no|vessel|ocean\s*vessel|voyage|"
    r"description|booking|b/l|bill\s*of\s*lading|kinds\s*of|commodity|export\s*carrier|order\s*no)",
    re.I,
)
_NUMERIC_ONLY = re.compile(r"^\d[\d,]*$")
_CONTAINER_CODE = re.compile(r"^[A-Z]{4}\d{7}$")

_MISSING_MARKERS = {
    "", "—", "-", "--", "n/a", "na", "missing", "nil", "none", "tbd", "tba", "tbc",
    "unknown", "- -", "to be advised", "to be confirmed", "to follow", "nill", "open",
}
_UNIT_ONLY_MISSING = re.compile(r"^[\s?_.\-–—]*(?:mts?|kgs?|kilograms?|tons?|t)?[\s?_.\-–—]*$")
_PUNCT_ONLY_MISSING = re.compile(r"^[\s?_.\-–—]+$")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ComparisonField:
    name: str
    label: str
    si: str
    bl: str
    status: str  # match | mismatch | review

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "label": self.label,
            "si": self.si,
            "bl": self.bl,
            "status": self.status,
        }


@dataclass
class ComparisonResult:
    email_id: str
    sender: str
    subject: str
    si_file: str
    bl_file: str
    status: str  # OK | MISMATCH | NEEDS_REVIEW
    has_defect: bool
    defect_fields: list[str]
    review_reason: str | None
    fields: list[ComparisonField] = field(default_factory=list)
    error: str | None = None

    def to_case_dict(self) -> dict[str, object]:
        """Shape persisted to the ``comparison_cases`` table."""
        return {
            "email_id": self.email_id,
            "sender": self.sender,
            "subject": self.subject,
            "si_file": self.si_file,
            "bl_file": self.bl_file,
            "status": self.status,
            "has_defect": self.has_defect,
            "defect_fields": self.defect_fields,
            "review_reason": self.review_reason,
            "fields": [entry.to_dict() for entry in self.fields],
        }


# ---------------------------------------------------------------------------
# Normalisation & extraction
# ---------------------------------------------------------------------------

def normalize_value(value: str) -> str:
    """Canonical form used for the equality check.

    Punctuation, units and whitespace are collapsed so that e.g.
    ``21,577 KG``, ``21577 kgs`` and ``21,577`` compare equal, ``1 x 40'HC``
    equals ``1 X 40HC``, and the `` | ``/``#`` separators that xlsx cell
    extraction introduces are ignored.
    """
    text = (value or "").strip().casefold()
    text = re.sub(r"[\s\u00a0]+", " ", text)
    text = re.sub(r"[\u2013\u2014\-\u2018\u2019'\u201c\u201d\"`]", "", text)
    text = re.sub(r"[.,;:()\[\]{}|#]", "", text)
    text = re.sub(r"\b(?:kgs?|kilograms?)\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_missing(value: str) -> bool:
    """True when a field value is blank / placeholder / TBA-style uncertainty."""
    normalized = normalize_value(value)
    if not normalized or normalized in _MISSING_MARKERS:
        return True
    if _PUNCT_ONLY_MISSING.match(normalized):
        return True
    return bool(_UNIT_ONLY_MISSING.match(normalized))


def extract_fields(text: str) -> dict[str, str]:
    """Return {field_key: raw_value} for every compared field.

    Handles ``Label: value`` (single line) and table-style documents where the
    label sits on its own line and the value follows on the next non-empty,
    non-label line.
    """
    lines = text.splitlines()
    extracted: dict[str, str] = {}
    for key in FIELD_KEYS:
        same_line, next_line = _FIELD_PATTERNS[key]
        value = ""
        for pattern in same_line:
            match = pattern.search(text)
            if match:
                candidate = match.group(1).strip()
                if candidate:
                    value = candidate
                    break
        if not value and key == "gross_weight_kg":
            value = _extract_gross_weight(text, lines, next_line)
        elif not value and key == "container_count":
            value = _extract_next_line_value(lines, next_line)
            if not value:
                value = _count_containers(lines)
        elif not value and next_line:
            value = _extract_next_line_value(lines, next_line)
        extracted[key] = value
    return extracted


_PREFIX_CACHE: dict[tuple[str, ...], list[re.Pattern[str]]] = {}


def _prefix_patterns(label_patterns: list[re.Pattern[str]]) -> list[re.Pattern[str]]:
    """Label-prefix regexes (label + annotations + optional colon, no line end).

    Used to recognise a label line that ALSO carries the start of its value on
    the same line, e.g. ``Consignee (Non-Negotiable) TOPKOPY MIDDLE EAST FZE``
    where the full value continues on the following lines.
    """
    key = tuple(p.pattern for p in label_patterns)
    cached = _PREFIX_CACHE.get(key)
    if cached is not None:
        return cached
    out: list[re.Pattern[str]] = []
    for pattern in label_patterns:
        text = pattern.pattern
        if text.endswith(r":?\s*$"):
            text = text[: -len(r":?\s*$")] + r":?"
        elif text.endswith(r"\s*$"):
            text = text[: -len(r"\s*$")]
        out.append(re.compile(text, pattern.flags))
    _PREFIX_CACHE[key] = out
    return out


def _extract_next_line_value(lines: list[str], label_patterns: list[re.Pattern[str]]) -> str:
    """Find a standalone label line, then join the following value lines.

    Multi-line addresses are joined with a space so the same address renders
    identically whether the source kept it on one line (xlsx `` | `` cells) or
    across several lines (docx line breaks). Lines that look like the next
    document label terminate the value. When the label line itself carries the
    start of the value (``Consignee (Non-Negotiable) TOPKOPY MIDDLE EAST FZE``),
    that remainder is used as the first value token.
    """
    prefixes = _prefix_patterns(label_patterns)
    for index, line in enumerate(lines):
        remainder = ""
        prefix_hit = False
        for prefix in prefixes:
            match = prefix.match(line)
            if match:
                prefix_hit = True
                remainder = line[match.end():].strip()
                break
        if not prefix_hit:
            continue
        value_parts: list[str] = [remainder] if remainder else []
        for candidate in lines[index + 1:]:
            stripped = candidate.strip()
            if not stripped:
                continue
            if _LABEL_LIKE.match(stripped):
                break
            value_parts.append(stripped)
        if value_parts:
            return " ".join(value_parts)
    return ""


def _extract_gross_weight(
    text: str,
    lines: list[str],
    label_patterns: list[re.Pattern[str]],
) -> str:
    """Gross weight, tolerating three layouts:

    * ``Gross Weight (KG): 21,577``  (single line, any junk between label and ':')
    * ``Gross Weight毛重(KGS)`` followed by ``41,124`` (label line + value line)
    * a container table headed ``GROSS WEIGHT (KG)`` — sum the numeric rows
    """
    for pattern in _FIELD_PATTERNS["gross_weight_kg"][0]:
        match = pattern.search(text)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                return candidate
    # Table / value-on-next-line layout
    for index, line in enumerate(lines):
        if not any(pattern.search(line) for pattern in label_patterns):
            continue
        values: list[int] = []
        for candidate in lines[index + 1:]:
            stripped = candidate.strip()
            if not stripped:
                continue
            if _STOP_AFTER_WEIGHT.match(stripped):
                break
            if _NUMERIC_ONLY.match(stripped):
                try:
                    values.append(int(stripped.replace(",", "")))
                except ValueError:
                    pass
        if values:
            return str(sum(values))
    return ""


def _count_containers(lines: list[str]) -> str:
    """Fallback for container_count: count ISO container codes in the text."""
    count = sum(1 for line in lines if _CONTAINER_CODE.match(line.strip()))
    return str(count) if count else ""


def _doc_kind(text: str) -> str | None:
    head = text[:400].casefold()
    # Shipping Instructions sometimes carry the title "BILL OF LADING INSTRUCTION"
    # (or the compact xlsx form "BL INSTRUCTION"); check the SI markers first so
    # those are not mistaken for a Bill of Lading.
    if any(marker in head for marker in ("shipping instruction", "bill of lading instruction", "bl instruction")):
        return "SI"
    if "bill of lading" in head:
        return "BL"
    return None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_values(si_value: str, bl_value: str) -> str:
    """Per-field verdict: ``match``, ``mismatch`` or ``review`` (missing data)."""
    if is_missing(si_value) or is_missing(bl_value):
        return "review"
    return "match" if normalize_value(si_value) == normalize_value(bl_value) else "mismatch"


def compare_documents(si_text: str, bl_text: str) -> ComparisonResult:
    """Compare extracted SI and BL text and produce the verification result.

    NEEDS_REVIEW (a field could not be read on either side) takes precedence
    over MISMATCH: a blank value is uncertainty, not a discrepancy.
    """
    si_fields = extract_fields(si_text)
    bl_fields = extract_fields(bl_text)

    field_rows: list[ComparisonField] = []
    mismatch_fields: list[str] = []
    has_missing = False
    for key, label in FIELD_LABELS:
        verdict = compare_values(si_fields[key], bl_fields[key])
        if verdict == "mismatch":
            mismatch_fields.append(key)
        elif verdict == "review":
            has_missing = True
        field_rows.append(
            ComparisonField(
                name=key,
                label=label,
                si=si_fields[key] or "—",
                bl=bl_fields[key] or "—",
                status=verdict,
            )
        )

    if has_missing:
        return ComparisonResult(
            email_id="",
            sender="",
            subject="",
            si_file="",
            bl_file="",
            status="NEEDS_REVIEW",
            has_defect=False,
            defect_fields=[],
            review_reason="missing_value",
            fields=field_rows,
        )
    if mismatch_fields:
        return ComparisonResult(
            email_id="",
            sender="",
            subject="",
            si_file="",
            bl_file="",
            status="MISMATCH",
            has_defect=True,
            defect_fields=mismatch_fields,
            review_reason=None,
            fields=field_rows,
        )
    return ComparisonResult(
        email_id="",
        sender="",
        subject="",
        si_file="",
        bl_file="",
        status="OK",
        has_defect=False,
        defect_fields=[],
        review_reason=None,
        fields=field_rows,
    )


def _pick_attachment(attachment_paths: list[str], marker: str) -> str | None:
    """Pick the attachment whose filename marks it as the SI or the BL.

    Accepts both the corpus' ``*_SI`` / ``*_BL`` suffix convention and natural
    names (``shipping_instruction.pdf``, ``bill_of_lading.xlsx``).
    """
    for path in attachment_paths:
        if attachment_kind(str(path)) == marker:
            return path
    return None


def _explicitly_asks_for_comparison(subject: str, body: str) -> bool:
    """True when the email clearly asked to compare an SI against a BL.

    Used to tell a genuine "please compare SI + BL, the attachments dropped"
    edge case (escalate) apart from a routine "please send me the draft BL"
    follow-up with no pair to compare (treat as clean).
    """
    text = f"{subject or ''} {body or ''}".casefold()
    return "compare" in text and (
        "si" in text or "draft bl" in text or "bill of lading" in text
    )


def analyze_email(
    email_id: str,
    sender: str,
    subject: str,
    attachment_paths: list[str],
    base_dir: Path,
    body: str = "",
) -> ComparisonResult:
    """Full analysis pipeline for one email: locate docs, read them, compare.

    Never raises for per-email problems: extraction failures become
    ``NEEDS_REVIEW`` results so the rest of the corpus keeps processing.
    """
    base_result = ComparisonResult(
        email_id=email_id,
        sender=sender,
        subject=subject,
        si_file="",
        bl_file="",
        status="NEEDS_REVIEW",
        has_defect=False,
        defect_fields=[],
        review_reason="missing_attachment",
        fields=[],
    )

    si_att = _pick_attachment(attachment_paths, "SI")
    bl_att = _pick_attachment(attachment_paths, "BL")
    if not si_att or not bl_att:
        base_result.si_file = si_att or ""
        base_result.bl_file = bl_att or ""
        # A missing-attachment escalation is a genuine edge case only when the
        # email actually asked to compare an SI and a BL (e.g. "Please compare
        # the SI and draft BL ... attachments dropped"). A routine "please send
        # the draft BL" follow-up with no docs is clean (OK), not a defect.
        if _explicitly_asks_for_comparison(subject, body):
            base_result.review_reason = "missing_attachment"
            base_result.error = "Could not locate both SI and BL attachments."
        else:
            base_result.status = "OK"
            base_result.review_reason = None
            base_result.error = None
        return base_result

    base_result.si_file = si_att
    base_result.bl_file = bl_att

    try:
        si_text = extract_attachment_text((base_dir / si_att).resolve())
    except UnreadableAttachmentError as exc:
        base_result.review_reason = "unreadable"
        base_result.error = f"SI unreadable: {exc}"
        return base_result
    except Exception as exc:  # pragma: no cover - defensive
        base_result.review_reason = "unreadable"
        base_result.error = f"SI extraction failed: {exc}"
        return base_result

    try:
        bl_text = extract_attachment_text((base_dir / bl_att).resolve())
    except UnreadableAttachmentError as exc:
        base_result.review_reason = "unreadable"
        base_result.error = f"BL unreadable: {exc}"
        return base_result
    except Exception as exc:  # pragma: no cover - defensive
        base_result.review_reason = "unreadable"
        base_result.error = f"BL extraction failed: {exc}"
        return base_result

    # Wrong-document check: the file named *_SI must look like a shipping
    # instruction and *_BL must look like a bill of lading. A file that cannot
    # be recognised (e.g. a Commercial Invoice passed off as a BL) is also a
    # wrong-document case rather than a clean comparison.
    si_kind = _doc_kind(si_text)
    bl_kind = _doc_kind(bl_text)
    if si_kind != "SI" or bl_kind != "BL":
        base_result.review_reason = "wrong_doc_type"
        base_result.error = f"Attachments do not match their expected document types (SI kind={si_kind}, BL kind={bl_kind})."
        return base_result

    result = compare_documents(si_text, bl_text)
    result.email_id = email_id
    result.sender = sender
    result.subject = subject
    result.si_file = si_att
    result.bl_file = bl_att
    return result

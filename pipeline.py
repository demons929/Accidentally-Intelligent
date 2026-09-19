import json
import re
from loader import Inbox
import io
from pathlib import Path

# ─── Field Aliases & Patterns ──────────────────────────────────────
FIELD_ALIASES = {
    "shipper": ["shipper", "exporter", "consignor", "sender"],
    "consignee": ["consignee", "receiver", "to the order of", "non-negotiable"],
    "notify_party": ["notify party", "notify", "notification"],
    "port_of_loading": ["port of loading", "load port", "loading port", "pol"],
    "port_of_discharge": ["port of discharge", "discharge port", "pod", "destination"],
    "container_count": ["no. of containers", "container count", "total containers", "packages"],
    "gross_weight_kg": ["gross weight", "gross wt", "gw", "total weight"],
}

REQUIRED_FIELDS = list(FIELD_ALIASES.keys())

def extract_text_from_attachment(inbox, att_path):
    try:
        if att_path.endswith(".txt"):
            return inbox.read_text(att_path)
        
        raw_bytes = inbox.read_bytes(att_path)
        
        # Check if file is too small to be valid (common for corrupted PDFs)
        if len(raw_bytes) < 100 and (att_path.endswith(".pdf") or att_path.endswith(".xlsx")):
            print(f"️ Skipping suspiciously small file: {att_path}")
            return ""

        if att_path.endswith(".xlsx"):
            from openpyxl import load_workbook
            wb = load_workbook(filename=io.BytesIO(raw_bytes), data_only=True)
            text_parts = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    line = " ".join([str(c) for c in row if c is not None])
                    if line.strip(): text_parts.append(line)
            return "\n".join(text_parts)

        elif att_path.endswith(".docx"):
            from docx import Document
            doc = Document(io.BytesIO(raw_bytes))
            return "\n".join([p.text for p in doc.paragraphs])

        elif att_path.endswith(".pdf"):
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                # Check if pages actually exist and have content
                texts = [page.extract_text() for page in pdf.pages]
                valid_texts = [t for t in texts if t and t.strip()]
                if not valid_texts:
                    print(f"⚠️ PDF has no readable text: {att_path}")
                    return ""
                return "\n".join(valid_texts)
                
        return ""
    except Exception as e:
        # Be specific about the error type for debugging
        err_msg = str(e)
        if "No /Root object" in err_msg or "Unexpected EOF" in err_msg:
            print(f"️ CORRUPT FILE SKIPPED: {att_path}")
        else:
            print(f"⚠️ Error reading {att_path}: {e}")
        return ""
    
def normalize_value(field, value):
    """Clean up extracted values for better comparison."""
    if not value: return ""
    value = str(value).strip().upper()
    
    # Remove common units or noise
    if field == "gross_weight_kg":
        value = re.sub(r'[^\d.]', '', value)
        try: return float(value)
        except: return value
    if field == "container_count":
        nums = re.findall(r'\d+', value)
        return int(nums[0]) if nums else value
    
    # Normalize port names (remove codes in parentheses for comparison)
    if "port" in field:
        value = re.sub(r'\s*\(.*?\)', '', value).strip()
        
    return value

def parse_document(text):
    """Heuristic parser for SI/BL text files."""
    result = {}
    lines = text.split('\n')
    
    for line in lines:
        if ':' not in line: continue
        key, _, val = line.partition(':')
        key_clean = key.strip().lower()
        val_clean = val.strip()
        
        if not val_clean: continue
        
        for canonical, aliases in FIELD_ALIASES.items():
            if any(alias in key_clean for alias in aliases):
                result[canonical] = normalize_value(canonical, val_clean)
                break
                
    return result

def classify_email(email):
    """Classify based on subject/body keywords."""
    text = f"{email.get('subject', '')} {email.get('body', '')}".lower()
    
    if "spam" in text or "verify your account" in text or "weird trick" in text:
        return "SPAM"
    if "invoice" in text and ("query" in text or "breakdown" in text or "charge" in text):
        return "INVOICE_QUERY"
    if "shipping instruction" in text and ("attached" not in text and "find attached" not in text) and "draft bl" not in text:
        # If it's just asking for an SI or providing one without BL comparison
        return "SI_REQUEST"
    if "bl" in text and ("compare" in text or "check" in text or "confirm" in text or "match" in text):
        return "BL_COMPARISON"
    
    # Default logic for emails with both SI and BL attachments
    atts = email.get("attachments", [])
    has_si = any("si" in a.lower() for a in atts)
    has_bl = any("bl" in a.lower() for a in atts)
    if has_si and has_bl:
        return "BL_COMPARISON"
        
    return "GENERAL"

def has_minimal_structure(text):
    """Only reject if text is truly empty/garbage. Be VERY permissive."""
    if not text or len(text.strip()) < 30:
        return False
    # If it has ANY colon-separated lines, it's probably structured data
    lines_with_colons = sum(1 for line in text.split('\n') if ':' in line)
    return lines_with_colons >= 3

def is_valid_bl(text):
    """Check if text actually contains BL content."""
    if not text or len(text.strip()) < 50: 
        return False
    keywords = ["bill of lading", "vessel", "voyage", "bl no", "booking"]
    matches = sum(1 for kw in keywords if kw in text.lower())
    return matches >= 2

def validate_parsed_data(data):
    """Return True only if critical fields are actually present."""
    critical = ["shipper", "consignee", "port_of_loading", "port_of_discharge"]
    missing = [f for f in critical if f not in data or not str(data[f]).strip()]
    # If 3+ critical fields are missing, document is truly incomplete
    return len(missing) < 3, missing

def compare_si_bl(si_text, bl_text):
    # ✅ FIX 1: Validate content BEFORE parsing (catches wrong_doc_type)
    # Only reject if BOTH are completely unstructured
    si_structured = has_minimal_structure(si_text)
    bl_structured = has_minimal_structure(bl_text)

    if not si_structured and not bl_structured:
        return {"status": "NEEDS_REVIEW", "review_reason": "unreadable", 
                "has_defect": False, "defect_fields": []}
# If ONE is structured, proceed with comparison instead of rejecting

    si_data = parse_document(si_text)
    bl_data = parse_document(bl_text)
    
    # ✅ FIX 2: Check for missing critical values (catches missing_value)
    si_complete, si_missing = validate_parsed_data(si_data)
    bl_complete, bl_missing = validate_parsed_data(bl_data)
    
    if not si_complete or not bl_complete:
        all_missing = list(set(si_missing + bl_missing))
        return {"status": "NEEDS_REVIEW", "review_reason": "missing_value", 
                "has_defect": False, "defect_fields": all_missing}

    # ✅ FIX 3: Only flag NEEDS_REVIEW if BOTH fail to parse
    if not si_data and not bl_data:
        return {"status": "NEEDS_REVIEW", "review_reason": "unreadable", 
                "has_defect": False, "defect_fields": []}
    
    # If ONE parsed successfully, proceed with comparison instead of giving up
    defect_fields = []
    for field in REQUIRED_FIELDS:
        si_val = si_data.get(field)
        bl_val = bl_data.get(field)
        
        # Skip if both missing; flag if only one missing
        if si_val is None and bl_val is None: 
            continue
        if si_val is None or bl_val is None:
            defect_fields.append(field)
            continue
            
        if si_val != bl_val:
            defect_fields.append(field)
            
    if defect_fields:
        return {"status": "MISMATCH", "review_reason": None, 
                "has_defect": True, "defect_fields": defect_fields}
    
    return {"status": "OK", "review_reason": None, 
            "has_defect": False, "defect_fields": []}

def clean_text(text):
    """Remove forwarded email chains and excessive whitespace."""
    if not text: 
        return ""
    # Stop at common forwarded message markers
    for marker in ["______________________", "From:", "Sent:", "Original Message"]:
        if marker in text:
            text = text.split(marker)[0]
    return text.strip()

def run_pipeline():
    print(f"🔍 Connecting to server...")
    inbox = Inbox("http://localhost:8080")
    
    # ✅ GET THE LIST OF EMAILS THE SERVER ACTUALLY WANTS
    try:
        sample = inbox.sample_submission()
        required_ids = set(sample.keys())
        print(f"🎯 Server expects {len(required_ids)} specific emails.")
    except Exception as e:
        print(f"⚠️ Could not fetch sample submission: {e}")
        required_ids = None
    
    emails = inbox.emails()
    print(f"✅ Found {len(emails)} total emails on server.")

    submission = {}
    
    for i, email in enumerate(emails):
        eid = email["email_id"]
        
        # ✅ SKIP EMAILS NOT IN THE REQUIRED LIST
        if required_ids and eid not in required_ids:
            continue
            
        print(f"⚙️ Processing {i+1}/{len(emails)}: {eid}")
        
        category = classify_email(email)
        
        entry = {
            "category": category,
            "status": None,
            "review_reason": None,
            "has_defect": False,
            "defect_fields": [],
        }
        
        if category == "BL_COMPARISON":
            si_text, bl_text = "", ""
            si_att_found, bl_att_found = False, False
            
            for att in email.get("attachments", []):
                content = extract_text_from_attachment(inbox, att)
                att_lower = att.lower()
                
                if "si" in att_lower and not si_att_found:
                    si_text = content
                    si_att_found = True
                elif "bl" in att_lower and not bl_att_found:
                    bl_text = content
                    bl_att_found = True

            # Fallback to body ONLY if no SI attachment was found at all
            if not si_att_found and "shipper" in clean_text(email.get("body", "")).lower():
                si_text = clean_text(email["body"])

            # ✅ STRICTER: Only mark NEEDS_REVIEW if truly missing/unreadable
            if not si_text.strip() and not bl_text.strip():
                entry.update({"status": "NEEDS_REVIEW", "review_reason": "missing_attachment"})
            elif not si_text.strip():
                entry.update({"status": "NEEDS_REVIEW", "review_reason": "missing_attachment"})
            elif not bl_text.strip():
                entry.update({"status": "NEEDS_REVIEW", "review_reason": "missing_attachment"})
            else:
                cmp = compare_si_bl(si_text, bl_text)
                entry.update(cmp)

        submission[eid] = entry
        
    if submission:
        with open("submission.json", "w") as f:
            json.dump(submission, f, indent=2)
        print(f"🚀 Successfully wrote {len(submission)} entries to submission.json")
    else:
        print("⚠️ Submission dictionary is still empty!")
    # ... after writing submission.json ...
    
    print("\n📤 Submitting to server for scoring...")
    try:
        result = inbox.submit(submission)  # Capture the response!
        
        # Print the full scoreboard
        print(f"\n🏆 FINAL SCORE: {result.get('final_score', 'N/A')}")
        print(f"📊 Stage-1 (Classification): {result.get('stage1_f1', result.get('classification_score', 'N/A'))}")
        print(f"📊 Stage-3 (Defects): {result.get('stage3_f1', result.get('defect_f1', 'N/A'))}")
        print(f"📊 Reliability: {result.get('reliability', 'N/A')}")
        
        # Debug: Print raw response if scores are still N/A
        if 'final_score' not in result:
            print(f"\n⚠️ Raw server response: {result}")
            
    except Exception as e:
        print(f"❌ Submission failed: {e}")
        import traceback
        traceback.print_exc()    

if __name__ == "__main__":
    run_pipeline()
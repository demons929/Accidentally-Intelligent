"""End-to-end API smoke test for the HarryPort backend."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"
TOKEN = "harryport-demo-token"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            content_type = resp.headers.get("Content-Type", "")
            try:
                payload = json.loads(raw) if "json" in content_type else raw
            except json.JSONDecodeError:
                payload = raw
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except json.JSONDecodeError:
            return exc.code, exc.read().decode("utf-8", errors="replace")


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {name}  {detail}")
    return condition


ok = True

# --- pages ---------------------------------------------------------------
status, body = call("GET", "/")
ok &= check("GET / serves login page", status == 200 and "HarryPort" in body and "Sign In" in body, f"status={status}")
for page in ["login.html", "frontpage.html", "Comparison.html", "inbox.html", "humanreview.html"]:
    status, _ = call("GET", f"/{page}")
    ok &= check(f"GET /{page}", status == 200, f"status={status}")
for asset in ["/static/js/app.js", "/static/js/inbox.js", "/static/js/human_review.js", "/static/css/style.css", "/resources/image/logo.png"]:
    status, _ = call("GET", asset)
    ok &= check(f"GET {asset}", status == 200, f"status={status}")

# --- auth ----------------------------------------------------------------
status, body = call("POST", "/api/auth/login", {"username": "captain@harryport.com", "password": "pure_magic_2026"})
ok &= check("login ok", status == 200 and body["token"] == TOKEN, f"status={status}")
status, _ = call("POST", "/api/auth/login", {"username": "x", "password": "y"})
ok &= check("login rejects bad creds", status == 401, f"status={status}")
status, _ = call("GET", "/api/auth/session", token=TOKEN)
ok &= check("session ok", status == 200, f"status={status}")
status, _ = call("GET", "/api/auth/session")
ok &= check("session rejects no token", status == 401, f"status={status}")

# --- emails --------------------------------------------------------------
status, body = call("GET", "/api/emails?page_size=5")
ok &= check("emails paginated", status == 200 and body["total"] == 520 and len(body["items"]) == 5, f"total={body.get('total')}")
status, body = call("GET", "/api/emails?category=Comparison%20requests&page_size=200")
ok &= check("emails filter category", status == 200 and body["total"] == 220, f"total={body.get('total')}")
status, body = call("GET", "/api/emails?search=maersk&page_size=200")
ok &= check("emails search", status == 200, f"total={body.get('total')}")
status, body = call("GET", "/api/emails/stats")
ok &= check("emails stats", status == 200 and sum(body["categories"].values()) + body["human_review"]["unreadable"] + body["human_review"]["corrupted"] == 520, f"cats={body.get('categories')}")

# --- human review --------------------------------------------------------
status, body = call("GET", "/api/human-review/unreadable")
ok &= check("hr unreadable", status == 200 and isinstance(body, list) and len(body) == 5, f"n={len(body) if isinstance(body, list) else body}")
status, body = call("GET", "/api/human-review/corrupted")
ok &= check("hr corrupted", status == 200 and isinstance(body, list), f"n={len(body) if isinstance(body, list) else body}")
status, body = call("GET", "/api/human-review/resolved")
ok &= check("hr resolved", status == 200 and isinstance(body, list), f"n={len(body) if isinstance(body, list) else body}")

# --- comparison ----------------------------------------------------------
status, body = call("GET", "/api/comparison?include_resolved=true")
ok &= check("comparison list", status == 200 and body["total"] == 220, f"total={body.get('total')}")
status, body = call("GET", "/api/comparison/stats")
ok &= check("comparison stats", status == 200, f"stats={body}")
status, body = call("GET", "/api/comparison/email_004")
ok &= check("comparison detail", status == 200 and body["status"] == "MISMATCH" and "consignee" in body["defect_fields"], f"defects={body.get('defect_fields')}")
status, body = call("GET", "/api/comparison/email_001")
ok &= check("comparison detail OK", status == 200 and body["status"] == "OK", f"status={body.get('status')}")

# --- writes (use throwaway email for move; revert after) -------------------
status, body = call("GET", "/api/emails?category=General%20mail&page_size=1")
target = body["items"][0]["email_id"] if body["items"] else None
if target:
    status, _ = call("POST", f"/api/emails/{target}/move", {"category": "Spam"}, token=TOKEN)
    ok &= check("move email", status == 200, f"status={status}")
    status, _ = call("POST", f"/api/emails/{target}/move", {"category": "General mail"}, token=TOKEN)
    ok &= check("revert move", status == 200, f"status={status}")

# resolve a NEEDS_REVIEW comparison case
status, body = call("GET", "/api/comparison?status=NEEDS_REVIEW&include_resolved=true")
review_case = body["items"][0] if body["items"] else None
if review_case:
    email_id = review_case["email_id"]
    status, body = call("POST", f"/api/comparison/{email_id}/resolve", {"fields": {"shipper": "CORRECTED CO LTD"}, "remark": "smoke test"}, token=TOKEN)
    ok &= check("resolve comparison case", status == 200 and body["is_resolved"] is True, f"status={status} body={body.get('status')}")
    status, _ = call("POST", f"/api/comparison/{email_id}/resolve", {"remark": "re-open for demo"}, token=TOKEN)
    # revert by resolving again is not needed for smoke test

# resolve a human review case (re-seed keeps them resolvable; use first unreadable)
status, body = call("GET", "/api/human-review/unreadable")
if isinstance(body, list) and body:
    hr_id = body[0]["email_id"]
    status, _ = call("POST", f"/api/human-review/{hr_id}/resolve", {"remark": "smoke test"}, token=TOKEN)
    ok &= check("resolve human review", status == 200, f"status={status}")

print()
print("ALL PASS" if ok else "SOME CHECKS FAILED")

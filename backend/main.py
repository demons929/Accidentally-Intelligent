"""FastAPI application entry point.

Serves the HarryPort dashboard and its API from a single process:

    GET  /                          -> login page
    GET  /<page>.html               -> any page under frontend/static
    /static/*, /resources/*         -> static assets
    /api/emails..., /api/human-review..., /api/comparison..., /api/auth...
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.database import SessionLocal, init_db
from backend.routes.auth import router as auth_router
from backend.routes.comparison import router as comparison_router
from backend.routes.human_review import router as human_review_router
from backend.routes.inbox import router as inbox_router
from backend.seed import seed_comparison_cases, seed_emails_from_pipeline
from config import PROJECT_ROOT, get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)

# Always serve fresh HTML so dashboard/HR UI updates never show a stale cached page.
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    with SessionLocal() as db:
        seed_emails_from_pipeline(db)
        seed_comparison_cases(db)


# --- API routers --------------------------------------------------------
app.include_router(inbox_router)
app.include_router(human_review_router)
app.include_router(comparison_router)
app.include_router(auth_router)


# --- static mounts ------------------------------------------------------
# frontend/static holds every HTML/CSS/JS asset; resources/ holds the data
# bundle plus brand images.
frontend_static = PROJECT_ROOT / "frontend" / "static"
resources_root = PROJECT_ROOT / "resources"
app.mount("/static", StaticFiles(directory=frontend_static), name="static")
app.mount("/resources", StaticFiles(directory=resources_root), name="resources")


@app.get("/")
def root() -> FileResponse:
    login_page = frontend_static / "login.html"
    return FileResponse(login_page, headers=NO_CACHE_HEADERS)


@app.get("/{page_name}.html")
def html_page(page_name: str) -> FileResponse:
    """Serve pages from frontend/static, e.g. /login.html, /frontpage.html."""
    path = frontend_static / f"{page_name}.html"
    if path.exists():
        return FileResponse(path, headers=NO_CACHE_HEADERS)
    return FileResponse(frontend_static / "login.html", headers=NO_CACHE_HEADERS)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

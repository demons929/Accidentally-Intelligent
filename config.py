"""Central configuration for the HarryPort email classifier.

Values can be overridden with environment variables prefixed with ``HARRYPORT_``
(e.g. ``HARRYPORT_DEMO_PASSWORD=secret``) or a local ``.env`` file.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - very old pydantic fallback
    try:
        from pydantic import BaseSettings
    except Exception:
        from pydantic import BaseModel as BaseSettings

    class SettingsConfigDict(dict):
        pass


PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    app_name: str = "HarryPort Email Classifier"

    # --- paths -----------------------------------------------------------
    database_url: str = Field(default=f"sqlite:///{PROJECT_ROOT / 'harryport.db'}")
    data_dir: Path = Field(default=PROJECT_ROOT / "resources" / "sdoc-hackathon-bundle")
    test_dir: Path = Field(default=PROJECT_ROOT / "data" / "test")
    train_dir: Path = Field(default=PROJECT_ROOT / "data" / "train")
    model_dir: Path = Field(default=PROJECT_ROOT / "models" / "best_model")
    submission_path: Path = Field(default=PROJECT_ROOT / "submission.json")
    static_dir: Path = Field(default=PROJECT_ROOT / "frontend" / "static")

    # --- classification --------------------------------------------------
    azure_form_recognizer_endpoint: str | None = None
    azure_form_recognizer_key: str | None = None
    confidence_threshold: float = 0.35
    max_sequence_length: int = 512
    default_page_size: int = 50

    # --- submission format ------------------------------------------------
    # "standard_list" -> [{"email_id": "...", "category": "New SI requests"}, ...]
    # "organizer"     -> {email_id: {"category","status","review_reason",
    #                    "defect_fields","has_defect"}}  (SDOC bundle format)
    # "legacy_mapping" -> {email_id: {"email_id":..., "category":...}}
    submission_format: str = "standard_list"
    # "frontend" -> human-readable category names used by the dashboard;
    # "organizer" -> competition codes (BL_COMPARISON / SI_REQUEST / INVOICE_QUERY / GENERAL / SPAM)
    submission_category_style: str = "frontend"
    submission_include_review_metadata: bool = True

    # --- demo auth ---------------------------------------------------------
    demo_username: str = "captain@harryport.com"
    demo_password: str = "pure_magic_2026"
    demo_user_name: str = "Captain"
    demo_user_role: str = "Port Administrator"
    session_token: str = "harryport-demo-token"

    # --- demo profile (dummy data for the dashboard's user profile) --------
    demo_job_title: str = "Senior Port Administrator"
    demo_department: str = "Port Operations & Documentation"
    demo_employee_id: str = "HP-2019-0427"
    demo_phone: str = "+60 3-2711 8899"
    demo_location: str = "Port Klang, Selangor, Malaysia"
    demo_joined: str = "2019-11-04"
    demo_timezone: str = "Asia/Kuala_Lumpur (UTC+8)"
    demo_last_login: str = "2026-09-21 08:42"

    # --- SI / BL comparison -----------------------------------------------
    # Comparison requests are flagged for human review when either side is
    # unreadable; a per-field value counts as "missing" when blank/"—".
    comparison_review_reasons: tuple[str, ...] = (
        "wrong_doc_type",
        "missing_attachment",
        "unreadable",
        "missing_value",
    )

    model_config = SettingsConfigDict(env_file=".env", env_prefix="HARRYPORT_")


@lru_cache
def get_settings() -> Settings:
    return Settings()

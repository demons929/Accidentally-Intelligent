"""Pydantic models for API request/response payloads."""

from pydantic import BaseModel, Field


class EmailOut(BaseModel):
    id: int
    email_id: str
    sender: str
    subject: str
    preview: str
    body: str = ""
    category: str | None
    status: str
    received_time: str
    is_human_review: bool
    review_type: str | None
    is_resolved: bool
    confidence: float
    attachments: list[str]


class HumanReviewOut(EmailOut):
    error: str | None
    review_remark: str | None = None


class SummaryOut(BaseModel):
    total: int
    categories: dict[str, int]
    human_review: dict[str, int]


class PaginatedEmailsOut(BaseModel):
    items: list[EmailOut]
    total: int
    page: int
    page_size: int


class MoveEmailIn(BaseModel):
    category: str


# --- auth ---------------------------------------------------------------

class LoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    """Demo user profile rendered in the dashboard header + profile modal."""

    name: str
    role: str
    email: str
    job_title: str = ""
    department: str = ""
    employee_id: str = ""
    phone: str = ""
    location: str = ""
    joined: str = ""
    timezone: str = ""
    last_login: str = ""


class LoginOut(BaseModel):
    token: str
    user: UserOut


# --- comparison ---------------------------------------------------------

class ComparisonFieldOut(BaseModel):
    name: str
    label: str
    si: str
    bl: str
    status: str  # match | mismatch | review


class ComparisonCaseOut(BaseModel):
    email_id: str
    sender: str
    subject: str
    si_file: str
    bl_file: str
    status: str  # OK | MISMATCH | NEEDS_REVIEW
    has_defect: bool
    defect_fields: list[str]
    review_reason: str | None
    fields: list[ComparisonFieldOut]
    is_resolved: bool
    body: str = ""
    error: str | None = None


class ComparisonListOut(BaseModel):
    items: list[ComparisonCaseOut]
    total: int


class ComparisonResolveIn(BaseModel):
    """Optional corrected field values applied during human review."""

    fields: dict[str, str] | None = None
    remark: str | None = None


class HumanReviewResolveIn(BaseModel):
    remark: str | None = None

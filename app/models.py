from typing import Literal

from pydantic import BaseModel, Field

FieldStatus = Literal["pass", "mismatch", "missing", "needs_review", "unreadable"]
OverallStatus = Literal["pass", "needs_review", "unreadable"]


class ExpectedFields(BaseModel):
    brand_name: str
    class_type: str
    alcohol_content: str
    net_contents: str
    bottler_address: str
    country_of_origin: str = ""
    government_warning: str


class FieldResult(BaseModel):
    field: str
    label: str
    expected: str
    extracted: str
    status: FieldStatus
    message: str


class VerificationReport(BaseModel):
    overall_status: OverallStatus
    field_results: dict[str, FieldResult]
    raw_text: str
    processing_ms: int


class FieldCandidateModel(BaseModel):
    field: str
    value: str
    source: str
    confidence: float
    raw_text: str


class VerifyResponse(VerificationReport):
    extraction_ms: int
    field_guesses: dict[str, str]
    field_candidates: dict[str, list[FieldCandidateModel]] = Field(default_factory=dict)

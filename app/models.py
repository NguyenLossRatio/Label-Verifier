from typing import Literal

from pydantic import BaseModel, field_validator

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

    @field_validator(
        "brand_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "bottler_address",
        "government_warning",
    )
    @classmethod
    def required_fields_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field is required and cannot be blank")
        return value


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


class VerifyResponse(VerificationReport):
    extraction_ms: int
    field_guesses: dict[str, str]

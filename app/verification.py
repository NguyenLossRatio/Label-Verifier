import re
import string
import time

from app.models import ExpectedFields, FieldResult, VerificationReport


FIELD_LABELS = {
    "brand_name": "Brand name",
    "class_type": "Class/type",
    "alcohol_content": "Alcohol content",
    "net_contents": "Net contents",
    "bottler_address": "Bottler/producer address",
    "country_of_origin": "Country of origin",
    "government_warning": "Government warning",
}


def normalize_text(value: str) -> str:
    lowered = value.lower()
    no_punctuation = lowered.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", no_punctuation).strip()


def _contains_tolerant(raw_text: str, expected: str) -> bool:
    if not expected.strip():
        return True
    return normalize_text(expected) in normalize_text(raw_text)


def _contains_strictish(raw_text: str, expected: str) -> bool:
    if not expected.strip():
        return True
    return normalize_text(expected) in normalize_text(raw_text)


def _result(field: str, expected: str, extracted: str, status: str, message: str) -> FieldResult:
    return FieldResult(
        field=field,
        label=FIELD_LABELS[field],
        expected=expected,
        extracted=extracted,
        status=status,
        message=message,
    )


def verify_label_text(expected: ExpectedFields, raw_text: str) -> VerificationReport:
    started = time.perf_counter()
    field_results: dict[str, FieldResult] = {}

    field_results["brand_name"] = _result(
        "brand_name",
        expected.brand_name,
        expected.brand_name if _contains_tolerant(raw_text, expected.brand_name) else "",
        "pass" if _contains_tolerant(raw_text, expected.brand_name) else "mismatch",
        "Brand name matched with tolerant comparison."
        if _contains_tolerant(raw_text, expected.brand_name)
        else "Expected brand name was not found.",
    )

    for field, value in {
        "class_type": expected.class_type,
        "alcohol_content": expected.alcohol_content,
        "net_contents": expected.net_contents,
        "bottler_address": expected.bottler_address,
        "country_of_origin": expected.country_of_origin,
    }.items():
        matched = _contains_strictish(raw_text, value)
        field_results[field] = _result(
            field,
            value,
            value if matched else "",
            "pass" if matched else "mismatch",
            f"{FIELD_LABELS[field]} matched." if matched else f"Expected {FIELD_LABELS[field].lower()} was not found.",
        )

    warning_matched = _contains_strictish(raw_text, expected.government_warning)
    field_results["government_warning"] = _result(
        "government_warning",
        expected.government_warning,
        expected.government_warning if warning_matched else "",
        "pass" if warning_matched else "mismatch",
        "Government warning matched." if warning_matched else "Expected government warning was not found.",
    )

    overall_status = "pass"
    if any(result.status != "pass" for result in field_results.values()):
        overall_status = "needs_review"

    return VerificationReport(
        overall_status=overall_status,
        field_results=field_results,
        raw_text=raw_text,
        processing_ms=round((time.perf_counter() - started) * 1000),
    )

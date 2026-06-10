import re
import string
import time

from app.models import ExpectedFields, FieldResult, FieldStatus, VerificationReport


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


def _has_boundary_match(normalized_text: str, normalized_expected: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_expected)}(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def _find_phrase_match(raw_text: str, expected: str) -> str | None:
    if not expected.strip():
        return ""

    normalized_expected = normalize_text(expected)
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped and _has_boundary_match(normalize_text(stripped), normalized_expected):
            return stripped

    if _has_boundary_match(normalize_text(raw_text), normalized_expected):
        return raw_text.strip()

    return None


def _find_value_match(raw_text: str, expected: str) -> str | None:
    return _find_phrase_match(raw_text, expected)


def _find_warning_like_segment(raw_text: str, expected_warning: str) -> str | None:
    normalized_warning_label = "government warning"
    normalized_expected = normalize_text(expected_warning)
    lines = raw_text.splitlines()
    candidates = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not _has_boundary_match(normalize_text(stripped), normalized_warning_label):
            continue

        candidate_lines = [stripped]
        candidate = " ".join(candidate_lines)
        if normalize_text(candidate) == normalized_expected:
            return candidate

        for next_line in lines[index + 1 :]:
            next_stripped = next_line.strip()
            if not next_stripped:
                break
            if _has_boundary_match(normalize_text(next_stripped), normalized_warning_label):
                break
            candidate_lines.append(next_stripped)
            candidate = " ".join(candidate_lines)
            if normalize_text(candidate) == normalized_expected:
                return candidate

        candidates.append(candidate)

    if candidates:
        return max(
            candidates,
            key=lambda candidate: (
                normalize_text(candidate) == normalized_expected,
                _has_boundary_match(normalize_text(candidate), normalized_expected),
                len(normalize_text(candidate)),
            ),
        )

    if _has_boundary_match(normalize_text(raw_text), normalized_warning_label):
        return raw_text.strip()

    return None


def _result(field: str, expected: str, extracted: str, status: FieldStatus, message: str) -> FieldResult:
    return FieldResult(
        field=field,
        label=FIELD_LABELS[field],
        expected=expected,
        extracted=extracted,
        status=status,
        message=message,
    )


def _verify_expected_phrase(field: str, expected: str, raw_text: str) -> FieldResult:
    match = _find_phrase_match(raw_text, expected)
    return _result(
        field,
        expected,
        match or "",
        "pass" if match is not None else "mismatch",
        f"{FIELD_LABELS[field]} matched." if match is not None else f"Expected {FIELD_LABELS[field].lower()} was not found.",
    )


def _verify_expected_value(field: str, expected: str, raw_text: str) -> FieldResult:
    match = _find_value_match(raw_text, expected)
    return _result(
        field,
        expected,
        match or "",
        "pass" if match is not None else "mismatch",
        f"{FIELD_LABELS[field]} matched." if match is not None else f"Expected {FIELD_LABELS[field].lower()} was not found.",
    )


def _verify_optional_country(expected: str, raw_text: str) -> FieldResult:
    if not expected.strip():
        return _result(
            "country_of_origin",
            expected,
            "",
            "pass",
            "Country of origin not required for this review.",
        )

    return _verify_expected_value("country_of_origin", expected, raw_text)


def _verify_government_warning(expected_warning: str, raw_text: str) -> FieldResult:
    normalized_expected = normalize_text(expected_warning)
    warning_segment = _find_warning_like_segment(raw_text, expected_warning)

    if warning_segment is None:
        return _result(
            "government_warning",
            expected_warning,
            "",
            "missing",
            "Government warning statement was not found.",
        )

    if not warning_segment.startswith("GOVERNMENT WARNING:"):
        return _result(
            "government_warning",
            expected_warning,
            "Government warning",
            "mismatch",
            "Government warning must use uppercase GOVERNMENT WARNING: prefix.",
        )

    if normalize_text(warning_segment) == normalized_expected:
        return _result(
            "government_warning",
            expected_warning,
            warning_segment,
            "pass",
            "Government warning matched.",
        )

    return _result(
        "government_warning",
        expected_warning,
        warning_segment,
        "mismatch",
        "Government warning wording did not match the expected statement.",
    )


def verify_label_text(expected: ExpectedFields, raw_text: str) -> VerificationReport:
    started = time.perf_counter()
    field_results: dict[str, FieldResult] = {}

    brand_match = _find_phrase_match(raw_text, expected.brand_name)
    field_results["brand_name"] = _result(
        "brand_name",
        expected.brand_name,
        brand_match or "",
        "pass" if brand_match is not None else "mismatch",
        "Brand name matched with tolerant comparison."
        if brand_match is not None
        else "Expected brand name was not found.",
    )

    field_results["class_type"] = _verify_expected_phrase("class_type", expected.class_type, raw_text)
    field_results["alcohol_content"] = _verify_expected_value("alcohol_content", expected.alcohol_content, raw_text)
    field_results["net_contents"] = _verify_expected_value("net_contents", expected.net_contents, raw_text)
    field_results["bottler_address"] = _verify_expected_phrase("bottler_address", expected.bottler_address, raw_text)
    field_results["country_of_origin"] = _verify_optional_country(expected.country_of_origin, raw_text)
    field_results["government_warning"] = _verify_government_warning(expected.government_warning, raw_text)

    overall_status = "pass"
    if any(result.status != "pass" for result in field_results.values()):
        overall_status = "needs_review"

    return VerificationReport(
        overall_status=overall_status,
        field_results=field_results,
        raw_text=raw_text,
        processing_ms=round((time.perf_counter() - started) * 1000),
    )

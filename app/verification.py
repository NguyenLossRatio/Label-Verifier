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


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


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
    strict_expected = _collapse_whitespace(expected_warning)
    strict_pattern = r"\s+".join(re.escape(part) for part in strict_expected.split())
    strict_match = re.search(strict_pattern, raw_text)
    if strict_match is not None:
        return _collapse_whitespace(strict_match.group(0))

    lines = raw_text.splitlines()
    candidates = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not _has_boundary_match(normalize_text(stripped), normalized_warning_label):
            continue

        candidate_lines = [stripped]
        candidate = " ".join(candidate_lines)
        if _collapse_whitespace(candidate) == strict_expected:
            return candidate

        for next_line in lines[index + 1 :]:
            next_stripped = next_line.strip()
            if not next_stripped:
                break
            if _has_boundary_match(normalize_text(next_stripped), normalized_warning_label):
                break
            candidate_lines.append(next_stripped)
            candidate = " ".join(candidate_lines)
            if _collapse_whitespace(candidate) == strict_expected:
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


def _blank_expected_result(field: str, expected: str, extracted_guess: str = "") -> FieldResult:
    return _result(
        field,
        expected,
        extracted_guess,
        "needs_review",
        f"Expected {FIELD_LABELS[field].lower()} was left blank for testing.",
    )


def _verify_expected_phrase(field: str, expected: str, raw_text: str, extracted_guess: str = "") -> FieldResult:
    if not expected.strip():
        return _blank_expected_result(field, expected, extracted_guess)

    match = _find_phrase_match(raw_text, expected)
    return _result(
        field,
        expected,
        extracted_guess or match or "",
        "pass" if match is not None else "mismatch",
        f"{FIELD_LABELS[field]} matched." if match is not None else f"Expected {FIELD_LABELS[field].lower()} was not found.",
    )


def _verify_expected_value(field: str, expected: str, raw_text: str, extracted_guess: str = "") -> FieldResult:
    if not expected.strip():
        return _blank_expected_result(field, expected, extracted_guess)

    match = _find_value_match(raw_text, expected)
    return _result(
        field,
        expected,
        extracted_guess or match or "",
        "pass" if match is not None else "mismatch",
        f"{FIELD_LABELS[field]} matched." if match is not None else f"Expected {FIELD_LABELS[field].lower()} was not found.",
    )


def _verify_optional_country(expected: str, raw_text: str, extracted_guess: str = "") -> FieldResult:
    if not expected.strip():
        if extracted_guess:
            return _blank_expected_result("country_of_origin", expected, extracted_guess)

        return _result(
            "country_of_origin",
            expected,
            "",
            "pass",
            "Country of origin not required for this review.",
        )

    return _verify_expected_value("country_of_origin", expected, raw_text, extracted_guess)


def _verify_government_warning(expected_warning: str, raw_text: str, extracted_guess: str = "") -> FieldResult:
    if not expected_warning.strip():
        return _blank_expected_result("government_warning", expected_warning, extracted_guess)

    extracted_display = extracted_guess or ""

    if extracted_guess and _collapse_whitespace(extracted_guess) == _collapse_whitespace(expected_warning):
        return _result(
            "government_warning",
            expected_warning,
            extracted_guess,
            "pass",
            "Government warning matched.",
        )

    if expected_warning in raw_text:
        return _result(
            "government_warning",
            expected_warning,
            extracted_display or expected_warning,
            "pass",
            "Government warning matched.",
        )

    warning_segment = _find_warning_like_segment(raw_text, expected_warning)

    if warning_segment is None:
        if extracted_guess:
            return _result(
                "government_warning",
                expected_warning,
                extracted_guess,
                "mismatch",
                "Government warning was detected, but must exactly match the expected statement, including case.",
            )

        return _result(
            "government_warning",
            expected_warning,
            extracted_guess,
            "missing",
            "Government warning statement was not found.",
        )

    if _collapse_whitespace(warning_segment) == _collapse_whitespace(expected_warning):
        return _result(
            "government_warning",
            expected_warning,
            extracted_display or warning_segment,
            "pass",
            "Government warning matched.",
        )

    if not warning_segment.startswith("GOVERNMENT WARNING:"):
        return _result(
            "government_warning",
            expected_warning,
            extracted_display or "Government warning",
            "mismatch",
            "Government warning must use uppercase GOVERNMENT WARNING: prefix.",
        )

    return _result(
        "government_warning",
        expected_warning,
        extracted_display or warning_segment,
        "mismatch",
        "Government warning must exactly match the expected statement, including case.",
    )


def verify_label_text(
    expected: ExpectedFields,
    raw_text: str,
    field_guesses: dict[str, str] | None = None,
) -> VerificationReport:
    started = time.perf_counter()
    field_guesses = field_guesses or {}
    field_results: dict[str, FieldResult] = {}

    brand_match = None if not expected.brand_name.strip() else _find_phrase_match(raw_text, expected.brand_name)
    field_results["brand_name"] = _result(
        "brand_name",
        expected.brand_name,
        field_guesses.get("brand_name", "") or brand_match or "",
        "pass" if brand_match is not None else ("needs_review" if not expected.brand_name.strip() else "mismatch"),
        "Brand name matched with tolerant comparison."
        if brand_match is not None
        else (
            "Expected brand name was left blank for testing."
            if not expected.brand_name.strip()
            else "Expected brand name was not found."
        ),
    )

    field_results["class_type"] = _verify_expected_phrase(
        "class_type", expected.class_type, raw_text, field_guesses.get("class_type", "")
    )
    field_results["alcohol_content"] = _verify_expected_value(
        "alcohol_content", expected.alcohol_content, raw_text, field_guesses.get("alcohol_content", "")
    )
    field_results["net_contents"] = _verify_expected_value(
        "net_contents", expected.net_contents, raw_text, field_guesses.get("net_contents", "")
    )
    field_results["bottler_address"] = _verify_expected_phrase(
        "bottler_address", expected.bottler_address, raw_text, field_guesses.get("bottler_address", "")
    )
    field_results["country_of_origin"] = _verify_optional_country(
        expected.country_of_origin, raw_text, field_guesses.get("country_of_origin", "")
    )
    field_results["government_warning"] = _verify_government_warning(
        expected.government_warning, raw_text, field_guesses.get("government_warning", "")
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

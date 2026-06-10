import pytest
from pydantic import ValidationError

from app.models import ExpectedFields
from app.verification import normalize_text, verify_label_text


STANDARD_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women "
    "should not drink alcoholic beverages during pregnancy because of the "
    "risk of birth defects. (2) Consumption of alcoholic beverages impairs "
    "your ability to drive a car or operate machinery, and may cause health problems."
)


def expected_fields(**overrides):
    values = {
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "bottler_address": "Old Tom Distillery, Louisville, KY",
        "country_of_origin": "",
        "government_warning": STANDARD_WARNING,
    }
    values.update(overrides)
    return ExpectedFields(**values)


def test_normalize_text_removes_case_and_punctuation_noise():
    assert normalize_text("STONE'S THROW") == normalize_text("Stones Throw")


def test_brand_name_allows_capitalization_and_punctuation_differences():
    report = verify_label_text(
        expected_fields(brand_name="STONE'S THROW"),
        "Brand: Stones Throw\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)\n750 ml\nOld Tom Distillery, Louisville, KY\n" + STANDARD_WARNING,
    )

    brand = report.field_results["brand_name"]
    assert brand.status == "pass"
    assert "Stones Throw" in brand.extracted
    assert report.overall_status == "pass"


@pytest.mark.parametrize(
    "field",
    [
        "brand_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "bottler_address",
        "government_warning",
    ],
)
def test_required_expected_fields_must_be_nonblank(field):
    with pytest.raises(ValidationError):
        expected_fields(**{field: "   "})


def test_blank_country_of_origin_is_optional_and_does_not_fail_verification():
    report = verify_label_text(
        expected_fields(country_of_origin=""),
        "OLD TOM DISTILLERY\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)\n750 mL\nOld Tom Distillery, Louisville, KY\n"
        + STANDARD_WARNING,
    )

    country = report.field_results["country_of_origin"]
    assert country.status == "pass"
    assert country.extracted == ""
    assert country.message == "Country of origin not required for this review."
    assert report.overall_status == "pass"


def test_brand_does_not_match_inside_another_word():
    report = verify_label_text(
        expected_fields(brand_name="RUM"),
        "CRUMBLES\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)\n750 mL\nOld Tom Distillery, Louisville, KY\n"
        + STANDARD_WARNING,
    )

    brand = report.field_results["brand_name"]
    assert brand.status == "mismatch"
    assert report.overall_status == "needs_review"


def test_net_contents_does_not_match_larger_number():
    report = verify_label_text(
        expected_fields(net_contents="750 mL"),
        "OLD TOM DISTILLERY\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)\n1750 mL\nOld Tom Distillery, Louisville, KY\n"
        + STANDARD_WARNING,
    )

    net_contents = report.field_results["net_contents"]
    assert net_contents.status == "mismatch"
    assert report.overall_status == "needs_review"


def test_abv_mismatch_is_flagged():
    report = verify_label_text(
        expected_fields(alcohol_content="45% Alc./Vol. (90 Proof)"),
        "OLD TOM DISTILLERY\n40% Alc./Vol. (80 Proof)\n750 mL\n" + STANDARD_WARNING,
    )

    alcohol = report.field_results["alcohol_content"]
    assert alcohol.status == "mismatch"
    assert "Expected alcohol content was not found" in alcohol.message
    assert report.overall_status == "needs_review"


def test_government_warning_requires_uppercase_prefix():
    bad_warning = STANDARD_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")

    report = verify_label_text(expected_fields(), "OLD TOM DISTILLERY\n" + bad_warning)

    warning = report.field_results["government_warning"]
    assert warning.status == "mismatch"
    assert "must use uppercase GOVERNMENT WARNING:" in warning.message
    assert report.overall_status == "needs_review"


def test_government_warning_prefix_must_belong_to_warning_statement():
    bad_warning = STANDARD_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    raw_text = "GOVERNMENT WARNING:\nOLD TOM DISTILLERY\n" + bad_warning

    report = verify_label_text(expected_fields(), raw_text)

    warning = report.field_results["government_warning"]
    assert warning.status == "mismatch"
    assert "must use uppercase GOVERNMENT WARNING:" in warning.message
    assert report.overall_status == "needs_review"


def test_government_warning_can_match_wrapped_text():
    wrapped_warning = STANDARD_WARNING.replace("women should not", "women\nshould not")
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "Kentucky Straight Bourbon Whiskey\n"
        "45% Alc./Vol. (90 Proof)\n"
        "750 mL\n"
        "Old Tom Distillery, Louisville, KY\n"
        + wrapped_warning
    )
    report = verify_label_text(expected_fields(), raw_text)

    warning = report.field_results["government_warning"]
    assert warning.status == "pass"
    assert warning.message == "Government warning matched."
    assert "GOVERNMENT WARNING:" in warning.extracted
    assert report.overall_status == "pass"


def test_missing_government_warning_is_missing():
    report = verify_label_text(expected_fields(), "OLD TOM DISTILLERY\n750 mL\n45% Alc./Vol. (90 Proof)")

    warning = report.field_results["government_warning"]
    assert warning.status == "missing"
    assert warning.message == "Government warning statement was not found."
    assert report.overall_status == "needs_review"


def test_government_warning_wording_mismatch_is_flagged():
    altered_warning = STANDARD_WARNING.replace("may cause health problems", "can cause health problems")
    report = verify_label_text(expected_fields(), "OLD TOM DISTILLERY\n" + altered_warning)

    warning = report.field_results["government_warning"]
    assert warning.status == "mismatch"
    assert "wording did not match" in warning.message
    assert report.overall_status == "needs_review"

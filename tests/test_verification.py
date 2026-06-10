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
    assert report.overall_status == "pass"


def test_abv_mismatch_is_flagged():
    report = verify_label_text(
        expected_fields(alcohol_content="45% Alc./Vol. (90 Proof)"),
        "OLD TOM DISTILLERY\n40% Alc./Vol. (80 Proof)\n750 mL\n" + STANDARD_WARNING,
    )

    alcohol = report.field_results["alcohol_content"]
    assert alcohol.status == "mismatch"
    assert "Expected alcohol content was not found" in alcohol.message
    assert report.overall_status == "needs_review"

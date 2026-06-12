import pytest

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


def test_brand_name_treats_ampersand_as_and():
    report = verify_label_text(
        expected_fields(brand_name="Malt and Hop Brewery"),
        "Malt & Hop Brewery\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)\n750 ml\nOld Tom Distillery, Louisville, KY\n" + STANDARD_WARNING,
    )

    brand = report.field_results["brand_name"]
    assert brand.status == "pass"
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
def test_expected_fields_may_be_blank_for_testing(field):
    fields = expected_fields(**{field: "   "})

    assert getattr(fields, field) == "   "


def test_blank_expected_field_reports_detected_guess_for_testing():
    report = verify_label_text(
        expected_fields(alcohol_content=""),
        "OLD TOM DISTILLERY\n45% Alc./Vol. (90 Proof)\n750 mL\n" + STANDARD_WARNING,
        field_guesses={"alcohol_content": "45% Alc./Vol. (90 Proof)"},
    )

    alcohol = report.field_results["alcohol_content"]
    assert alcohol.status == "needs_review"
    assert alcohol.expected == ""
    assert alcohol.extracted == "45% Alc./Vol. (90 Proof)"
    assert "left blank" in alcohol.message
    assert report.overall_status == "needs_review"


def test_filled_expected_field_preserves_detected_guess_for_display():
    extracted_guess = "45% Alc./Vol.\n(90 Proof)"

    blank_report = verify_label_text(
        expected_fields(alcohol_content=""),
        "OLD TOM DISTILLERY\n45% Alc./Vol. (90 Proof)\n750 mL\n" + STANDARD_WARNING,
        field_guesses={"alcohol_content": extracted_guess},
    )
    filled_report = verify_label_text(
        expected_fields(alcohol_content="45% Alc./Vol. (90 Proof)"),
        "OLD TOM DISTILLERY\n45% Alc./Vol. (90 Proof)\n750 mL\n" + STANDARD_WARNING,
        field_guesses={"alcohol_content": extracted_guess},
    )

    assert blank_report.field_results["alcohol_content"].extracted == extracted_guess
    assert filled_report.field_results["alcohol_content"].status == "pass"
    assert filled_report.field_results["alcohol_content"].extracted == extracted_guess


def test_filled_brand_preserves_detected_guess_for_display():
    extracted_guess = "OLD\nTOM DISTILLERY"

    blank_report = verify_label_text(
        expected_fields(brand_name=""),
        "OLD TOM DISTILLERY\n750 mL\n" + STANDARD_WARNING,
        field_guesses={"brand_name": extracted_guess},
    )
    filled_report = verify_label_text(
        expected_fields(brand_name="OLD TOM DISTILLERY"),
        "OLD TOM DISTILLERY\n750 mL\n" + STANDARD_WARNING,
        field_guesses={"brand_name": extracted_guess},
    )

    assert blank_report.field_results["brand_name"].extracted == extracted_guess
    assert filled_report.field_results["brand_name"].status == "pass"
    assert filled_report.field_results["brand_name"].extracted == extracted_guess


def test_mismatched_expected_field_reports_detected_guess_when_available():
    report = verify_label_text(
        expected_fields(net_contents="750 mL"),
        "OLD TOM DISTILLERY\n1 PINT\n" + STANDARD_WARNING,
        field_guesses={"net_contents": "1 PINT"},
    )

    net_contents = report.field_results["net_contents"]
    assert net_contents.status == "mismatch"
    assert net_contents.extracted == "1 PINT"


def test_bottler_address_can_match_structured_extracted_guess_when_raw_ocr_is_noisy():
    extracted_guess = "BELTLINE BREWING, LLC. 1440 Dutch Valley PI NE, Atlanta, GA 30324"
    raw_text = (
        "ORPHEUS BREWING\n"
        "OREW Ele =m: BELTLINE BREWING, LLC.\n"
        "snnS = 1440 Dutch Valley PI NE, Atlanta, GA 30324\n"
        + STANDARD_WARNING
    )

    report = verify_label_text(
        expected_fields(bottler_address=extracted_guess),
        raw_text,
        field_guesses={"bottler_address": extracted_guess},
    )

    bottler_address = report.field_results["bottler_address"]
    assert bottler_address.status == "pass"
    assert bottler_address.extracted == extracted_guess


def test_blank_country_reports_detected_guess_for_testing():
    report = verify_label_text(
        expected_fields(country_of_origin=""),
        "OLD TOM DISTILLERY\nImported from France\n" + STANDARD_WARNING,
        field_guesses={"country_of_origin": "France"},
    )

    country = report.field_results["country_of_origin"]
    assert country.status == "needs_review"
    assert country.extracted == "France"
    assert "left blank" in country.message


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


@pytest.mark.parametrize(
    "raw_net_contents",
    ["12FL.OZ.", "12fl.oz.", "12 FL\nOZ", "12  FL.  OZ.", "12FLOZ. 4% ALC/VOL"],
)
def test_net_contents_ignores_spacing_punctuation_and_line_breaks(raw_net_contents):
    report = verify_label_text(
        expected_fields(net_contents="12 FL OZ"),
        "OLD TOM DISTILLERY\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)\n"
        + raw_net_contents
        + "\nOld Tom Distillery, Louisville, KY\n"
        + STANDARD_WARNING,
    )

    net_contents = report.field_results["net_contents"]
    assert net_contents.status == "pass"


def test_net_contents_tolerates_leading_ocr_noise_for_fluid_ounces():
    report = verify_label_text(
        expected_fields(net_contents="12 FL OZ"),
        "LIZZIE TWISTER BLACKBERRY\n712 FL. OZ.\nALC. 5.6%\n" + STANDARD_WARNING,
    )

    net_contents = report.field_results["net_contents"]
    assert net_contents.status == "pass"
    assert net_contents.extracted == "12 FL. OZ."


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


def test_government_warning_allows_wrapped_text_with_exact_case_and_words():
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
    assert report.overall_status == "pass"


def test_government_warning_allows_wrapped_uppercase_prefix():
    wrapped_warning = STANDARD_WARNING.replace("GOVERNMENT WARNING:", "GOVERNMENT\nWARNING:")
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
    assert report.overall_status == "pass"


def test_government_warning_ignores_following_unrelated_label_text():
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "Kentucky Straight Bourbon Whiskey\n"
        "45% Alc./Vol. (90 Proof)\n"
        "750 mL\n"
        "Old Tom Distillery, Louisville, KY\n"
        + STANDARD_WARNING
        + "\n750 mL"
    )

    report = verify_label_text(expected_fields(), raw_text)

    warning = report.field_results["government_warning"]
    assert warning.status == "pass"
    assert warning.message == "Government warning matched."
    assert warning.extracted == STANDARD_WARNING
    assert report.overall_status == "pass"


def test_government_warning_pass_preserves_ocr_guess_for_extracted_display():
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "Kentucky Straight Bourbon Whiskey\n"
        "45% Alc./Vol. (90 Proof)\n"
        "750 mL\n"
        "Old Tom Distillery, Louisville, KY\n"
        + STANDARD_WARNING
    )
    warning_guess = (
        "GOVERNMENT WARNING:\n"
        "(1) According to the Surgeon General, women should not drink alcoholic beverages\n"
        "during pregnancy because of the risk of birth defects."
    )

    report = verify_label_text(
        expected_fields(),
        raw_text,
        field_guesses={"government_warning": warning_guess},
    )

    warning = report.field_results["government_warning"]
    assert warning.status == "pass"
    assert warning.extracted == warning_guess


def test_government_warning_ignores_same_line_trailing_label_text():
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "Kentucky Straight Bourbon Whiskey\n"
        "45% Alc./Vol. (90 Proof)\n"
        "750 mL\n"
        "Old Tom Distillery, Louisville, KY\n"
        + STANDARD_WARNING
        + " 750 mL"
    )

    report = verify_label_text(expected_fields(), raw_text)

    warning = report.field_results["government_warning"]
    assert warning.status == "pass"
    assert warning.message == "Government warning matched."
    assert warning.extracted == STANDARD_WARNING
    assert report.overall_status == "pass"


def test_missing_government_warning_is_missing():
    report = verify_label_text(expected_fields(), "OLD TOM DISTILLERY\n750 mL\n45% Alc./Vol. (90 Proof)")

    warning = report.field_results["government_warning"]
    assert warning.status == "missing"
    assert warning.message == "Government warning statement was not found."
    assert report.overall_status == "needs_review"


def test_government_warning_guess_is_mismatch_instead_of_missing():
    warning_guess = (
        "RNMENT WARNING:\n"
        "Neate SURGEON GENERA\n"
        "(1) WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES"
    )

    report = verify_label_text(
        expected_fields(),
        "OLD TOM DISTILLERY\n750 mL\n45% Alc./Vol. (90 Proof)",
        field_guesses={"government_warning": warning_guess},
    )

    warning = report.field_results["government_warning"]
    assert warning.status == "mismatch"
    assert warning.extracted == warning_guess
    assert warning.message == "Government warning was detected, but must exactly match the expected statement, including case."
    assert report.overall_status == "needs_review"


def test_government_warning_mismatch_preserves_ocr_guess_for_extracted_display():
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "GOVERNMENT WARNING:\n"
        "(1) According to the Surgeon General, women should not drink alcoholic beverages\n"
        "(2) Consumption of alcoholic beverages impairs your ability to drive a car"
    )
    warning_guess = (
        "GOVERNMENT WARNING:\n"
        "(1) According to the Surgeon General, women should not drink alcoholic beverages\n"
        "(2) Consumption of alcoholic beverages impairs your ability to drive a car"
    )

    report = verify_label_text(
        expected_fields(),
        raw_text,
        field_guesses={"government_warning": warning_guess},
    )

    warning = report.field_results["government_warning"]
    assert warning.status == "mismatch"
    assert warning.extracted == warning_guess
    assert report.overall_status == "needs_review"


def test_government_warning_exact_ocr_guess_passes_even_when_raw_text_is_noisy():
    warning_guess = STANDARD_WARNING.replace("women should not", "women\nshould not")
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "GOVERNMENT WARNING:\n"
        "(1) According to the Surgeon General, women\n"
        "LOGO NOISE\n"
        "should not drink alcoholic beverages during pregnancy because of the risk of birth defects.\n"
        "(2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems."
    )

    report = verify_label_text(
        expected_fields(),
        raw_text,
        field_guesses={"government_warning": warning_guess},
    )

    warning = report.field_results["government_warning"]
    assert warning.status == "pass"
    assert warning.extracted == warning_guess


def test_government_warning_wording_mismatch_is_flagged():
    altered_warning = STANDARD_WARNING.replace("may cause health problems", "can cause health problems")
    report = verify_label_text(expected_fields(), "OLD TOM DISTILLERY\n" + altered_warning)

    warning = report.field_results["government_warning"]
    assert warning.status == "mismatch"
    assert warning.message == "Government warning must exactly match the expected statement, including case."
    assert report.overall_status == "needs_review"


def test_government_warning_body_case_change_is_mismatch():
    altered_warning = STANDARD_WARNING.replace("According", "according")
    report = verify_label_text(expected_fields(), "OLD TOM DISTILLERY\n" + altered_warning)

    warning = report.field_results["government_warning"]
    assert warning.status == "mismatch"
    assert warning.message == "Government warning must exactly match the expected statement, including case."
    assert report.overall_status == "needs_review"


def test_government_warning_punctuation_change_is_mismatch():
    altered_warning = STANDARD_WARNING.replace("problems.", "problems")
    report = verify_label_text(expected_fields(), "OLD TOM DISTILLERY\n" + altered_warning)

    warning = report.field_results["government_warning"]
    assert warning.status == "mismatch"
    assert warning.message == "Government warning must exactly match the expected statement, including case."
    assert report.overall_status == "needs_review"

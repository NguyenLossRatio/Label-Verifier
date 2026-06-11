import io

import pytest
import pytesseract
from PIL import Image

from app.extraction import ExtractionError, extract_field_guesses, extract_text_from_image


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def patterned_png_bytes() -> bytes:
    image = Image.new("RGB", (20, 20), "white")
    for x in range(5, 15):
        for y in range(5, 15):
            image.putpixel((x, y), (120, 120, 120))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def sized_png_bytes(size: tuple[int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_extract_field_guesses_finds_common_label_values():
    raw_text = """
    OLD TOM DISTILLERY
    Kentucky Straight Bourbon Whiskey
    45% Alc./Vol. (90 Proof)
    750 mL
    Bottled by Old Tom Distillery, Louisville, KY
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["brand_name"] == "OLD TOM DISTILLERY"
    assert guesses["class_type"] == "Whiskey"
    assert guesses["alcohol_content"] == "45% Alc./Vol. (90 Proof)"
    assert guesses["net_contents"] == "750 mL"
    assert guesses["bottler_address"] == "Bottled by Old Tom Distillery, Louisville, KY"


def test_extract_field_guesses_returns_empty_strings_when_unknown():
    guesses = extract_field_guesses("Decorative label text only")

    assert guesses["alcohol_content"] == ""
    assert guesses["net_contents"] == ""
    assert guesses["bottler_address"] == ""


def test_extract_text_from_image_rejects_unreadable_bytes():
    with pytest.raises(
        ExtractionError, match="Unsupported or unreadable image file."
    ):
        extract_text_from_image(b"not an image")


def test_extract_text_from_image_rejects_empty_ocr_output(monkeypatch):
    monkeypatch.setattr(pytesseract, "image_to_string", lambda image, **kwargs: " \n\t ")

    with pytest.raises(
        ExtractionError, match="No readable text was found in the image."
    ):
        extract_text_from_image(png_bytes())


def test_extract_text_from_image_translates_missing_tesseract(monkeypatch):
    def raise_missing_tesseract(image, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", raise_missing_tesseract)

    with pytest.raises(
        ExtractionError,
        match="OCR engine is not installed. Install Tesseract or use raw text override.",
    ):
        extract_text_from_image(png_bytes())


def test_extract_text_from_image_translates_ocr_error(monkeypatch):
    def raise_ocr_error(image, **kwargs):
        raise pytesseract.TesseractError(1, "bad data")

    monkeypatch.setattr(pytesseract, "image_to_string", raise_ocr_error)

    with pytest.raises(ExtractionError, match="OCR failed while reading the image."):
        extract_text_from_image(png_bytes())


def test_extract_text_from_image_preprocesses_and_caps_large_images(monkeypatch):
    calls = []

    def capture_image(image, **kwargs):
        calls.append((image.mode, image.size, kwargs))
        return "OLD TOM DISTILLERY"

    monkeypatch.setattr(pytesseract, "image_to_string", capture_image)

    text, _ = extract_text_from_image(sized_png_bytes((4000, 2000)))

    assert text == "OLD TOM DISTILLERY"
    assert calls
    assert {mode for mode, _size, _kwargs in calls} == {"L"}
    assert all(max(size) <= 2200 for _mode, size, _kwargs in calls)


def test_extract_text_from_image_upscales_small_images_for_ocr(monkeypatch):
    calls = []

    def capture_image(image, **kwargs):
        calls.append(image.size)
        return "GOVERNMENT WARNING:"

    monkeypatch.setattr(pytesseract, "image_to_string", capture_image)

    extract_text_from_image(sized_png_bytes((645, 431)))

    assert calls
    assert all(max(size) >= 1400 for size in calls)
    assert all(max(size) <= 2200 for size in calls)


def test_extract_text_from_image_tries_bounded_page_segmentation_modes_across_preprocessing_variants(monkeypatch):
    configs = []
    image_variants = []

    def capture_config(image, **kwargs):
        image_variants.append(image.tobytes())
        configs.append(kwargs["config"])
        return "OLD TOM DISTILLERY"

    monkeypatch.setattr(pytesseract, "image_to_string", capture_config)

    extract_text_from_image(patterned_png_bytes())

    assert configs == [
        "--psm 6",
        "--psm 11",
        "--psm 6",
        "--psm 6",
        "--psm 6",
        "--psm 6",
        "--psm 11",
        "--psm 6",
        "--psm 11",
    ]
    assert len(set(image_variants)) >= 3


def test_extract_text_from_image_merges_text_from_later_preprocessing_variant(monkeypatch):
    calls = []

    def return_by_variant_and_config(image, **kwargs):
        calls.append(kwargs["config"])
        if len(calls) == 5:
            return "Script Brand\nPINEAPPLE SOUR ALE"
        return "750 mL"

    monkeypatch.setattr(pytesseract, "image_to_string", return_by_variant_and_config)

    text, _ = extract_text_from_image(png_bytes())

    assert "750 mL" in text
    assert "Script Brand" in text
    assert "PINEAPPLE SOUR ALE" in text


def test_extract_text_from_image_returns_best_ocr_pass(monkeypatch):
    responses = {
        "--psm 6": "OLD TOM\n750 mL",
        "--psm 11": "OLD TOM DISTILLERY\n45% Alc./Vol. (90 Proof)\n750 mL",
    }

    def return_by_config(image, **kwargs):
        return responses[kwargs["config"]]

    monkeypatch.setattr(pytesseract, "image_to_string", return_by_config)

    text, _ = extract_text_from_image(png_bytes())

    assert text == "OLD TOM DISTILLERY\n45% Alc./Vol. (90 Proof)\n750 mL"


def test_extract_text_from_image_keeps_complementary_ocr_lines(monkeypatch):
    responses = {
        "--psm 6": "Bottled by Old Tom Distillery, Louisville, KY\n750 mL",
        "--psm 11": "GOVERNMENT WARNING:\nOLD TOM DISTILLERY\n45% Alc./Vol. (90 Proof)",
    }

    def return_by_config(image, **kwargs):
        return responses[kwargs["config"]]

    monkeypatch.setattr(pytesseract, "image_to_string", return_by_config)

    text, _ = extract_text_from_image(png_bytes())

    assert "Bottled by Old Tom Distillery, Louisville, KY" in text
    assert "GOVERNMENT WARNING:" in text
    assert "45% Alc./Vol. (90 Proof)" in text
    assert "750 mL" in text


def test_extract_text_from_image_keeps_longer_line_with_extra_field_data(monkeypatch):
    responses = {
        "--psm 6": "OVER AND OVER 12 FL OZ",
        "--psm 11": "ORPHEUS BREWING\nThe label has a long story with many words\nOVER AND OVER",
    }

    def return_by_config(image, **kwargs):
        return responses[kwargs["config"]]

    monkeypatch.setattr(pytesseract, "image_to_string", return_by_config)

    text, _ = extract_text_from_image(png_bytes())

    assert "OVER AND OVER 12 FL OZ" in text


def test_extract_text_from_image_tries_rotated_warning_pass_when_warning_is_missing(monkeypatch):
    calls = []

    def return_warning_on_rotated_pass(image, **kwargs):
        calls.append((image.size, kwargs["config"]))
        if image.size[0] > image.size[1]:
            return "GOVERNMENT WARNING:\n(1) ACCORDING TO THE SURGEON GENERAL"
        return "ORPHEUS BREWING\n12 FL. OZ\nPINEAPPLE SOUR ALE"

    monkeypatch.setattr(pytesseract, "image_to_string", return_warning_on_rotated_pass)

    text, _ = extract_text_from_image(sized_png_bytes((400, 800)))

    assert "ORPHEUS BREWING" in text
    assert "GOVERNMENT WARNING:" in text
    first_rotated_call = next(index for index, (size, _config) in enumerate(calls) if size[0] > size[1])
    assert first_rotated_call == 2


def test_extract_text_from_image_ignores_rotated_warning_timeout_when_normal_text_exists(monkeypatch):
    calls = []

    def timeout_on_rotated_pass(image, **kwargs):
        calls.append(kwargs["config"])
        if len(calls) <= 6:
            return "ORPHEUS BREWING\n12 FL. OZ\nPINEAPPLE SOUR ALE"
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(pytesseract, "image_to_string", timeout_on_rotated_pass)

    text, _ = extract_text_from_image(png_bytes())

    assert "ORPHEUS BREWING" in text
    assert "PINEAPPLE SOUR ALE" in text


def test_extract_field_guesses_handles_uppercase_net_contents_unit():
    guesses = extract_field_guesses("Kentucky Straight Bourbon Whiskey\n750 ML")

    assert guesses["net_contents"] == "750 ML"


@pytest.mark.parametrize("net_contents", ["1 PINT", "16 FL. OZ", "12FL.OZ."])
def test_extract_field_guesses_handles_common_us_net_contents_units(net_contents):
    guesses = extract_field_guesses(f"Kentucky Straight Bourbon Whiskey\n{net_contents}")

    assert guesses["net_contents"] == net_contents


@pytest.mark.parametrize("alcohol_content", ["13.68% Alcohol/Vol", "13.68% Alcohol Volume"])
def test_extract_field_guesses_handles_alcohol_volume_wording(alcohol_content):
    guesses = extract_field_guesses(f"Orange Muscat\n{alcohol_content}")

    assert guesses["alcohol_content"] == alcohol_content


def test_extract_field_guesses_detects_government_warning_block():
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "GOVERNMENT WARNING:\n"
        "(1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES\n"
        "(2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR"
    )

    guesses = extract_field_guesses(raw_text)

    assert guesses["government_warning"].startswith("GOVERNMENT WARNING:")
    assert "SURGEON GENERAL" in guesses["government_warning"]


def test_extract_field_guesses_detects_split_government_warning_label():
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "GOVERNMENT\n"
        "WARNING:\n"
        "(1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES\n"
        "(2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR"
    )

    guesses = extract_field_guesses(raw_text)

    assert guesses["government_warning"].startswith("GOVERNMENT\nWARNING:")
    assert "SURGEON GENERAL" in guesses["government_warning"]


def test_extract_field_guesses_detects_truncated_ocr_government_warning_label():
    raw_text = (
        "Hawk's Shadow Estate\n"
        "RNMENT WARNING:\n"
        "Neate SURGEON GENERA\n"
        "(1) WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES\n"
        "DURING PREGNANCY BECAUSE OF THE RISK OF BIRTH DEFECTS.\n"
        "13.68% Alcohol/Vol"
    )

    guesses = extract_field_guesses(raw_text)

    assert guesses["government_warning"].startswith("RNMENT WARNING:")
    assert "SURGEON GENERA" in guesses["government_warning"]
    assert "13.68% Alcohol/Vol" not in guesses["government_warning"]


def test_extract_field_guesses_keeps_warning_after_interleaved_ocr_noise():
    raw_text = (
        "GOVERNMENT WARNING:\n"
        "(1) ACCORDING TO THE SURGEON GENERAL,\n"
        "WOMEN SHOULD NOT DRINK ALCOHOLIC\n"
        "BREWERY\n"
        "Be\n"
        "BEVERAGES DURING PREGNANCY BECAUSE OF\n"
        "THE RISK OF BIRTH DEFECTS.\n"
        "1 PINT"
    )

    guesses = extract_field_guesses(raw_text)

    assert "BEVERAGES DURING PREGNANCY" in guesses["government_warning"]
    assert "THE RISK OF BIRTH DEFECTS" in guesses["government_warning"]
    assert "BREWERY" not in guesses["government_warning"]
    assert "1 PINT" not in guesses["government_warning"]


def test_extract_field_guesses_does_not_cut_off_long_noisy_warning_block():
    raw_text = (
        "GOVERNMENT WARNING:\n"
        "Malt & Hop\n"
        "(1) ACCORDING TO THE SURGEON GENERAL,\n"
        "WOMEN SHOULD NOT DRINK ALCOHOLIC\n"
        "BREWERY\n"
        "Be\n"
        "BEVERAGES DURING PREGNANCY BECAUSE OF\n"
        "THE RISK OF BIRTH DEFECTS.\n"
        "Bad\n"
        "(2) CONSUMPTION OF ALCOHOLIC BEVERAGES\n"
        "IMPAIRS YOUR ABILITY TO DRIVE A CAR OR\n"
        "OPERATE MACHINERY, AND MAY CAUSE\n"
        "jr\n"
        "label noise\n"
        "more speckles\n"
        "HEALTH PROBLEMS.\n"
        "CONTAINS: SULFITES\n"
        "1 PINT"
    )

    guesses = extract_field_guesses(raw_text)

    assert "OPERATE MACHINERY, AND MAY CAUSE" in guesses["government_warning"]
    assert "HEALTH PROBLEMS." in guesses["government_warning"]
    assert "CONTAINS: SULFITES" not in guesses["government_warning"]
    assert "1 PINT" not in guesses["government_warning"]


def test_extract_field_guesses_does_not_treat_numeric_noise_as_warning_line():
    raw_text = (
        "GOVERNMENT WARNING:\n"
        "(1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES\n"
        "(2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR\n"
        "AND MAY CAUSE HEALTH PROBLEMS.\n"
        "2 B5ou8be"
    )

    guesses = extract_field_guesses(raw_text)

    assert "HEALTH PROBLEMS." in guesses["government_warning"]
    assert "2 B5ou8be" not in guesses["government_warning"]


def test_extract_field_guesses_detects_brand_after_producer_line():
    raw_text = """
    Produced and Bottled by Example Producer
    Hawk's Shadow Estate
    2011 Orange Muscat
    13.68% Alcohol/Vol
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["brand_name"] == "Hawk's Shadow Estate"


def test_extract_field_guesses_ignores_generic_brand_labels():
    raw_text = """
    Hawk's Shadow Estate
    Estate Winery
    2011 Orange Muscat
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["brand_name"] == "Hawk's Shadow Estate"


def test_extract_field_guesses_ignores_short_noise_before_brand():
    raw_text = """
    eee
    ORPHEUS BREWING
    PINEAPPLE SOUR ALE
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["brand_name"] == "ORPHEUS BREWING"


def test_extract_field_guesses_infers_brand_from_brewed_by_line():
    raw_text = """
    GOVERNMENT WARNING:
    OPERATE MACHINERY, AND MAY CAUSE
    | BREWED & BOTTLED BY MALT & HOP BREWERY | HYATTSVILLE, MD
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["brand_name"] == "MALT & HOP BREWERY"


def test_extract_field_guesses_prefers_shorter_brand_candidate():
    raw_text = """
    ORPHEUS BREWING
    ORPHEUS BREWING DON'T LOOK BACK
    PINEAPPLE SOUR ALE
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["brand_name"] == "ORPHEUS BREWING"


@pytest.mark.parametrize(
    ("raw_text", "class_type"),
    [
        ("ORPHEUS BREWING\nPINEAPPLE SOUR ALE\n12 FL. OZ", "Ale"),
        ("Hawk's Shadow Estate\n2011 Orange Muscat\n13.68% Alcohol/Vol", "Wine"),
        ("OLD TOM DISTILLERY\nKentucky Straight Bourbon Whiskey\n750 mL", "Whiskey"),
    ],
)
def test_extract_field_guesses_detects_common_class_type_lines(raw_text, class_type):
    guesses = extract_field_guesses(raw_text)

    assert guesses["class_type"] == class_type


def test_extract_field_guesses_prefers_specific_class_line_over_descriptive_sentence():
    raw_text = """
    ORPHEUS BREWING
    could into this small, tart beer, for
    PINEAPPLE SOUR ALE
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["class_type"] == "Ale"


def test_extract_field_guesses_extracts_type_phrase_not_full_sentence():
    raw_text = "The grievous cycle mentions a small, tart beer, for a label story"

    guesses = extract_field_guesses(raw_text)

    assert guesses["class_type"] == ""


def test_extract_field_guesses_strips_vintage_from_wine_varietal():
    guesses = extract_field_guesses("Hawk's Shadow Estate\n2011 Orange Muscat")

    assert guesses["class_type"] == "Wine"


def test_extract_field_guesses_restricts_varietals_to_wine_type():
    guesses = extract_field_guesses("Hawk's Shadow Estate\nCabernet Sauvignon")

    assert guesses["class_type"] == "Wine"


def test_extract_field_guesses_infers_beer_class_from_brewery_context():
    raw_text = """
    MALT & HOP BREWERY
    BREWED & BOTTLED BY MALT & HOP BREWERY
    16 FL. OZ
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["class_type"] == "Beer"


def test_extract_field_guesses_ignores_warning_fragment_as_class_type():
    raw_text = """
    GREAT TASTE
    Ale HEALTH PROBLEMS. CONTAINS: SULFITES
    BREWED & BOTTLED BY MALT & HOP BREWERY
    16 FL. OZ
    """

    guesses = extract_field_guesses(raw_text)

    assert guesses["brand_name"] == "MALT & HOP BREWERY"
    assert guesses["class_type"] == "Beer"


@pytest.mark.parametrize(
    ("raw_text", "country"),
    [
        ("Imported from France\n750 mL", "France"),
        ("Product of Mexico\n40% Alc./Vol.", "Mexico"),
        ("Country of Origin: Italy", "Italy"),
    ],
)
def test_extract_field_guesses_detects_country_of_origin(raw_text, country):
    guesses = extract_field_guesses(raw_text)

    assert guesses["country_of_origin"] == country

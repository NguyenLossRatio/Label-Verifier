import io

import pytest
import pytesseract
from PIL import Image

from app.extraction import ExtractionError, extract_field_guesses, extract_text_from_image


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
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
    monkeypatch.setattr(pytesseract, "image_to_string", lambda image: " \n\t ")

    with pytest.raises(
        ExtractionError, match="No readable text was found in the image."
    ):
        extract_text_from_image(png_bytes())


def test_extract_text_from_image_translates_missing_tesseract(monkeypatch):
    def raise_missing_tesseract(image):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", raise_missing_tesseract)

    with pytest.raises(
        ExtractionError,
        match="OCR engine is not installed. Install Tesseract or use raw text override.",
    ):
        extract_text_from_image(png_bytes())


def test_extract_text_from_image_translates_ocr_error(monkeypatch):
    def raise_ocr_error(image):
        raise pytesseract.TesseractError(1, "bad data")

    monkeypatch.setattr(pytesseract, "image_to_string", raise_ocr_error)

    with pytest.raises(ExtractionError, match="OCR failed while reading the image."):
        extract_text_from_image(png_bytes())


def test_extract_field_guesses_handles_uppercase_net_contents_unit():
    guesses = extract_field_guesses("Kentucky Straight Bourbon Whiskey\n750 ML")

    assert guesses["net_contents"] == "750 ML"

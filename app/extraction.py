import io
import re
import time

from PIL import Image, UnidentifiedImageError
import pytesseract


class ExtractionError(Exception):
    pass


def extract_text_from_image(image_bytes: bytes) -> tuple[str, int]:
    started = time.perf_counter()
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except UnidentifiedImageError as exc:
        raise ExtractionError("Unsupported or unreadable image file.") from exc

    try:
        raw_text = pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError as exc:
        raise ExtractionError(
            "OCR engine is not installed. Install Tesseract or use raw text override."
        ) from exc

    cleaned = raw_text.strip()
    if not cleaned:
        raise ExtractionError("No readable text was found in the image.")

    return cleaned, round((time.perf_counter() - started) * 1000)


def extract_field_guesses(raw_text: str) -> dict[str, str]:
    alcohol_match = re.search(
        r"\b\d{1,2}(?:\.\d+)?\s*%\s*Alc\.?\s*/\s*Vol\.?(?:\s*\(\d{1,3}\s*Proof\))?",
        raw_text,
        re.IGNORECASE,
    )
    net_match = re.search(r"\b\d+(?:\.\d+)?\s*(?:mL|ml|L|l)\b", raw_text)
    bottler_match = re.search(
        r"^.*\b(?:Bottled by|Produced by|Distilled by)\b.*$",
        raw_text,
        re.IGNORECASE | re.MULTILINE,
    )

    return {
        "alcohol_content": alcohol_match.group(0).strip() if alcohol_match else "",
        "net_contents": net_match.group(0).strip() if net_match else "",
        "bottler_address": bottler_match.group(0).strip() if bottler_match else "",
    }

import io
import re
import time

from PIL import Image, UnidentifiedImageError
import pytesseract


class ExtractionError(Exception):
    pass


ALCOHOL_CONTENT_PATTERN = re.compile(
    r"\b\d{1,2}(?:\.\d+)?\s*%\s*Alc\.?\s*/\s*Vol\.?(?:\s*\(\d{1,3}\s*Proof\))?",
    re.IGNORECASE,
)
NET_CONTENTS_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mL|L)\b", re.IGNORECASE)
BOTTLER_ADDRESS_PATTERN = re.compile(
    r"^.*\b(?:Bottled by|Produced by|Distilled by)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_text_from_image(image_bytes: bytes) -> tuple[str, int]:
    started = time.perf_counter()
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            try:
                raw_text = pytesseract.image_to_string(image)
            except pytesseract.TesseractNotFoundError as exc:
                raise ExtractionError(
                    "OCR engine is not installed. Install Tesseract or use raw text override."
                ) from exc
            except pytesseract.TesseractError as exc:
                raise ExtractionError("OCR failed while reading the image.") from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise ExtractionError("Unsupported or unreadable image file.") from exc

    cleaned = raw_text.strip()
    if not cleaned:
        raise ExtractionError("No readable text was found in the image.")

    return cleaned, round((time.perf_counter() - started) * 1000)


def extract_field_guesses(raw_text: str) -> dict[str, str]:
    alcohol_match = ALCOHOL_CONTENT_PATTERN.search(raw_text)
    net_match = NET_CONTENTS_PATTERN.search(raw_text)
    bottler_match = BOTTLER_ADDRESS_PATTERN.search(raw_text)

    return {
        "alcohol_content": alcohol_match.group(0).strip() if alcohol_match else "",
        "net_contents": net_match.group(0).strip() if net_match else "",
        "bottler_address": bottler_match.group(0).strip() if bottler_match else "",
    }

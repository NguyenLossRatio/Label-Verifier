import io
import os
import re
import time
from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
import pytesseract


class ExtractionError(Exception):
    pass


@dataclass(frozen=True)
class FieldCandidate:
    field: str
    value: str
    source: str
    confidence: float
    raw_text: str


EXTRACTED_FIELDS = (
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_address",
    "country_of_origin",
    "government_warning",
)
ALCOHOL_CONTENT_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,2}(?:\.\d+)?\s*%\s*(?:(?:Alc|Alcohol)\.?\s*/\s*Vol\.?|Alcohol\s+Volume)(?:\s*\(\d{1,3}\s*Proof\))?"
    r"|(?:Alc|Alcohol)\.?\s*\d{1,2}(?:\.\d+)?\s*%(?:\s*(?:By\s+Vol(?:ume)?\.?|/\s*Vol\.?))?"
    r")",
    re.IGNORECASE,
)
NET_CONTENTS_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mL|fl\.?\s*oz\.?|L|pints?)\.?(?=\s|$|[),;])",
    re.IGNORECASE,
)
NET_CONTENTS_VALUE_PATTERN = re.compile(
    r"\b(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>mL|fl\.?\s*oz\.?|L|pints?)\.?(?=\s|$|[),;])",
    re.IGNORECASE,
)
BOTTLER_ADDRESS_PATTERN = re.compile(
    r"^.*\b(?:Bottled by|Produced by|Distilled by)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
BREWED_CANNED_ADDRESS_PATTERN = re.compile(
    r"\b(BREWED\s*(?:&|AND)\s*CANNED\s+IN\s+.+?,\s*[A-Z]{2}\s+BY\s+.+?\b"
    r"(?:BREWING|BREWERY|DISTILLERY|WINERY|VINEYARDS?)\b(?:,?\s*(?:LLC|INC|CO\.?|COMPANY))?\.?)",
    re.IGNORECASE | re.DOTALL,
)
PRODUCER_COMPANY_PATTERN = re.compile(
    r"\b([A-Z][A-Z0-9 &'.,-]*?\b(?:BREWING|BREWERY|DISTILLERY|WINERY|VINEYARDS?)\b(?:,?\s*(?:LLC|INC|CO\.?|COMPANY))?\.?)",
    re.IGNORECASE,
)
POSTAL_ADDRESS_PATTERN = re.compile(
    r"\b(\d{2,6}\s+.+?\b[A-Z]{2}\s+\d{5}(?:-\d{4})?)\b",
    re.IGNORECASE,
)
CITY_STATE_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z .'-]{1,50},\s*[A-Z]{2})\b",
    re.IGNORECASE,
)
FULL_STATE_CITY_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z .'-]{1,50},\s*(?:Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia))\b",
    re.IGNORECASE,
)
GOVERNMENT_WARNING_LABEL_PATTERN = re.compile(r"\bgovernment\s+warning\b", re.IGNORECASE)
OCR_WARNING_LABEL_PATTERN = re.compile(
    r"\b(?:gov(?:ern|em)ment|rnment)\b.*\bwarn(?:ing)?\b|\bwarn(?:ing)?\b.*\b(?:gov(?:ern|em)ment|rnment)\b",
    re.IGNORECASE,
)
WARNING_BODY_PATTERN = re.compile(
    r"\b(?:government|rnment|warning|according|surgeon|genera[lı]?|women|drink|alcoholic|beverages?|pregnancy|risk|birth|defects?|consumption|impairs?|drive|operate|machinery|health|problems?)\b",
    re.IGNORECASE,
)
CLASS_TYPE_PATTERN = re.compile(
    r"\b(?:bourbon|whiskey|whisky|vodka|gin|rum|tequila|brandy|liqueur|wine|ale|beer|lager|stout|porter|cider|mead|muscat|chardonnay|cabernet|merlot|pinot|riesling|sauvignon)\b",
    re.IGNORECASE,
)
ALCOHOL_TYPE_PATTERNS = (
    (re.compile(r"\b(?:kentucky\s+)?(?:straight\s+)?bourbon\s+whisk(?:ey|y)\b", re.IGNORECASE), "Whiskey"),
    (re.compile(r"\b(?:straight\s+)?rye\s+whisk(?:ey|y)\b", re.IGNORECASE), "Whiskey"),
    (re.compile(r"\bwhisk(?:ey|y)\b", re.IGNORECASE), "Whiskey"),
    (re.compile(r"\bbourbon\b", re.IGNORECASE), "Whiskey"),
    (re.compile(r"\b(?:pineapple\s+)?sour\s+ale\b", re.IGNORECASE), "Ale"),
    (re.compile(r"\bindia\s+pale\s+ale\b", re.IGNORECASE), "Ale"),
    (re.compile(r"\bpale\s+ale\b", re.IGNORECASE), "Ale"),
    (re.compile(r"\bipa\b", re.IGNORECASE), "Ale"),
    (re.compile(r"\bale\b", re.IGNORECASE), "Ale"),
    (re.compile(r"\blager\b", re.IGNORECASE), "Lager"),
    (re.compile(r"\bstout\b", re.IGNORECASE), "Stout"),
    (re.compile(r"\bporter\b", re.IGNORECASE), "Porter"),
    (re.compile(r"\bcider\b", re.IGNORECASE), "Cider"),
    (re.compile(r"\bmead\b", re.IGNORECASE), "Mead"),
    (re.compile(r"\bmalt\s+beverage\b", re.IGNORECASE), "Malt beverage"),
    (re.compile(r"\bbeer\b", re.IGNORECASE), "Beer"),
    (re.compile(r"\borange\s+muscat\b", re.IGNORECASE), "Wine"),
    (re.compile(r"\bcabernet\s+sauvignon\b", re.IGNORECASE), "Wine"),
    (re.compile(r"\bsauvignon\s+blanc\b", re.IGNORECASE), "Wine"),
    (re.compile(r"\bpinot\s+(?:noir|grigio|gris)\b", re.IGNORECASE), "Wine"),
    (re.compile(r"\b(?:chardonnay|merlot|riesling|muscat|wine)\b", re.IGNORECASE), "Wine"),
    (re.compile(r"\bvodka\b", re.IGNORECASE), "Vodka"),
    (re.compile(r"\bgin\b", re.IGNORECASE), "Gin"),
    (re.compile(r"\brum\b", re.IGNORECASE), "Rum"),
    (re.compile(r"\btequila\b", re.IGNORECASE), "Tequila"),
    (re.compile(r"\bbrandy\b", re.IGNORECASE), "Brandy"),
    (re.compile(r"\bliqueur\b", re.IGNORECASE), "Liqueur"),
)
COUNTRY_OF_ORIGIN_PATTERNS = (
    re.compile(r"\bimported\s+from\s+([A-Z][A-Za-z .'-]+)", re.IGNORECASE),
    re.compile(r"\bproduct\s+of\s+([A-Z][A-Za-z .'-]+)", re.IGNORECASE),
    re.compile(r"\bcountry\s+of\s+origin\s*:?\s*([A-Z][A-Za-z .'-]+)", re.IGNORECASE),
)
BRAND_EXCLUSION_PATTERN = re.compile(
    r"\b(?:government|warning|surgeon|pregnancy|contains|sulfites|bottled|produced|distilled|imported|product of|alc|alcohol|proof|fl\.?\s*oz|ml|pint|class|type|according|women|drink|beverages|risk|defects|consume|consumption|impairs|operate|machinery|health|problems|cause)\b",
    re.IGNORECASE,
)
SERVING_INSTRUCTION_PATTERN = re.compile(
    r"\b(?:enjoy|serve|served)\b.*\b(?:chilled|cold|ice|neat|responsibly)\b|\b(?:chill|refrigerate)\b",
    re.IGNORECASE,
)
CLASS_SENTENCE_NOISE_PATTERN = re.compile(
    r"\b(?:this|that|with|into|from|their|there|because|during|after|before|your|great|small|tart|for|and|or|health|problems|contains|sulfites|warning|surgeon|pregnancy|risk|defects|impairs|operate|machinery)\b",
    re.IGNORECASE,
)
BRAND_SUFFIX_PATTERN = re.compile(r"\b(?:brewing|brewery|distillery|estate|winery|vineyards?)\b", re.IGNORECASE)
BRAND_MINIMUM_SCORE = 8
COMPANY_CANDIDATE_PATTERN = re.compile(
    r"\b((?:(?:[A-Z][A-Za-z0-9'.,-]*|&)\s+){0,8}"
    r"(?:BREWING|BREWERY|DISTILLERY|WINERY|VINEYARDS?)"
    r"(?:,?\s*(?:LLC|INC|CO[.e0]?|COMPANY))?\.?)",
    re.IGNORECASE,
)
GENERIC_BRAND_LABELS = {
    "brewing",
    "brewing co",
    "brewing co.",
    "brewery",
    "distillery",
    "estate winery",
    "winery",
}
COMPANY_LEADING_NOISE_WORDS = {
    "AQY",
    "AY",
    "CANNED",
    "ERE",
    "FRESH",
    "LOCAL",
    "ON",
    "QNEY",
    "RIVEE",
    "RIVEK",
    "RIYEE",
    "SOE",
}
COMMON_FLUID_OUNCE_AMOUNTS = (
    "1.5",
    "5",
    "7",
    "8",
    "8.4",
    "10",
    "11",
    "11.2",
    "12",
    "12.7",
    "13",
    "14.9",
    "16",
    "19.2",
    "22",
    "24",
    "25.4",
    "32",
    "40",
    "64",
)
US_STATE_CODES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
}
US_STATE_NAMES = {
    "ALABAMA",
    "ALASKA",
    "ARIZONA",
    "ARKANSAS",
    "CALIFORNIA",
    "COLORADO",
    "CONNECTICUT",
    "DELAWARE",
    "FLORIDA",
    "GEORGIA",
    "HAWAII",
    "IDAHO",
    "ILLINOIS",
    "INDIANA",
    "IOWA",
    "KANSAS",
    "KENTUCKY",
    "LOUISIANA",
    "MAINE",
    "MARYLAND",
    "MASSACHUSETTS",
    "MICHIGAN",
    "MINNESOTA",
    "MISSISSIPPI",
    "MISSOURI",
    "MONTANA",
    "NEBRASKA",
    "NEVADA",
    "NEW HAMPSHIRE",
    "NEW JERSEY",
    "NEW MEXICO",
    "NEW YORK",
    "NORTH CAROLINA",
    "NORTH DAKOTA",
    "OHIO",
    "OKLAHOMA",
    "OREGON",
    "PENNSYLVANIA",
    "RHODE ISLAND",
    "SOUTH CAROLINA",
    "SOUTH DAKOTA",
    "TENNESSEE",
    "TEXAS",
    "UTAH",
    "VERMONT",
    "VIRGINIA",
    "WASHINGTON",
    "WEST VIRGINIA",
    "WISCONSIN",
    "WYOMING",
    "DISTRICT OF COLUMBIA",
}
MAX_OCR_IMAGE_DIMENSION = 1600
MIN_OCR_IMAGE_DIMENSION = 1400
MAX_OCR_UPSCALE_FACTOR = 3
OCR_TIME_BUDGET_SECONDS = 4.5
OCR_CONFIGS = ("--psm 6", "--psm 11")
ROTATED_WARNING_CONFIGS = ("--psm 6",)
ROTATED_WARNING_ANGLES = (90, 180, 270)
WARNING_REGION_RELATIVE_BOXES = (
    (0.0, 0.0, 0.26, 0.78),
    (0.0, 0.0, 0.34, 0.9),
)
FIELD_REGION_CONFIGS = ("--psm 6",)
FIELD_REGION_RELATIVE_BOXES = (
    ("center_address", (0.49, 0.12, 0.60, 0.64), 270),
    ("bottom_center", (0.42, 0.84, 0.78, 1.0), 0),
    ("bottom_right", (0.80, 0.84, 1.0, 1.0), 0),
    ("left_warning", (0.03, 0.18, 0.19, 0.86), 270),
)
FIELD_REGION_TRIGGER_FIELDS = (
    "alcohol_content",
    "net_contents",
    "bottler_address",
    "government_warning",
)
EASYOCR_MIN_REMAINING_SECONDS = 0.75
EASYOCR_MIN_CONFIDENCE = 0.15
EASYOCR_TRIGGER_FIELDS = (
    "brand_name",
    "class_type",
    "alcohol_content",
    "bottler_address",
    "government_warning",
)
MAX_WARNING_SCAN_LINES = 24
DEFAULT_OCR_MODE = "tesseract"
_EASYOCR_READER = None
_EASYOCR_UNAVAILABLE = False


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() not in {"0", "false", "no", "off"}


def _ocr_mode() -> str:
    mode = os.getenv("LABEL_VERIFIER_OCR_MODE", DEFAULT_OCR_MODE).strip().lower()
    if mode in {"strong", "easyocr", "strong-first"}:
        return "strong"
    if mode in {"fallback", "tesseract-first"}:
        return "fallback"
    if mode in {"tesseract", "tesseract-only"}:
        return "tesseract"

    return DEFAULT_OCR_MODE


def _load_easyocr_reader():
    global _EASYOCR_READER, _EASYOCR_UNAVAILABLE

    if (
        not _env_flag("LABEL_VERIFIER_USE_EASYOCR", True)
        or _ocr_mode() == "tesseract"
        or _EASYOCR_UNAVAILABLE
    ):
        return None

    if _EASYOCR_READER is not None:
        return _EASYOCR_READER

    try:
        import easyocr
    except ImportError:
        _EASYOCR_UNAVAILABLE = True
        return None

    try:
        _EASYOCR_READER = easyocr.Reader(
            ["en"],
            gpu=False,
            verbose=False,
            download_enabled=_env_flag("LABEL_VERIFIER_EASYOCR_DOWNLOAD", False),
        )
    except Exception:
        _EASYOCR_UNAVAILABLE = True
        return None

    return _EASYOCR_READER


def _resize_for_ocr(image: Image.Image) -> Image.Image:
    prepared = ImageOps.grayscale(image)
    width, height = prepared.size
    longest_side = max(width, height)

    scale = 1
    if longest_side > MAX_OCR_IMAGE_DIMENSION:
        scale = MAX_OCR_IMAGE_DIMENSION / longest_side
    elif longest_side < MIN_OCR_IMAGE_DIMENSION:
        scale = min(
            MIN_OCR_IMAGE_DIMENSION / longest_side,
            MAX_OCR_IMAGE_DIMENSION / longest_side,
            MAX_OCR_UPSCALE_FACTOR,
        )

    if scale != 1:
        prepared = prepared.resize(
            (round(width * scale), round(height * scale)),
            Image.Resampling.LANCZOS,
        )

    return prepared


def _prepare_image_for_ocr(image: Image.Image) -> Image.Image:
    prepared = _resize_for_ocr(image)
    prepared = ImageOps.autocontrast(prepared)
    prepared = ImageEnhance.Contrast(prepared).enhance(1.4)
    return prepared.filter(ImageFilter.SHARPEN)


def _prepare_image_variants_for_ocr(image: Image.Image) -> list[Image.Image]:
    base = _resize_for_ocr(image)

    standard = ImageOps.autocontrast(base)
    standard = ImageEnhance.Contrast(standard).enhance(1.4).filter(ImageFilter.SHARPEN)

    soft = ImageOps.autocontrast(base)
    soft = ImageEnhance.Contrast(soft).enhance(1.15).filter(ImageFilter.SMOOTH_MORE)

    threshold = ImageOps.autocontrast(base)
    threshold = ImageEnhance.Contrast(threshold).enhance(1.7)
    threshold = threshold.point(lambda pixel: 255 if pixel > 165 else 0)

    return [standard, soft, threshold]


def _prepare_rotated_warning_images_for_ocr(image: Image.Image) -> list[Image.Image]:
    prepared = _prepare_image_for_ocr(image)
    warning_images = []

    for relative_box in WARNING_REGION_RELATIVE_BOXES:
        prepared_crop = _prepare_image_for_ocr(_relative_crop(image, relative_box))
        warning_images.append(prepared_crop.rotate(270, expand=True))

    warning_images.extend(prepared.rotate(angle, expand=True) for angle in ROTATED_WARNING_ANGLES)
    return warning_images


def _is_wide_label(image: Image.Image) -> bool:
    width, height = image.size
    return width >= 1000 and height >= 500 and width / height >= 1.6


def _relative_crop(image: Image.Image, relative_box: tuple[float, float, float, float]) -> Image.Image:
    width, height = image.size
    left, top, right, bottom = relative_box
    return image.crop(
        (
            round(width * left),
            round(height * top),
            round(width * right),
            round(height * bottom),
        )
    )


def _prepare_field_region_images_for_ocr(image: Image.Image) -> list[Image.Image]:
    prepared_images = []
    for _name, relative_box, rotation in FIELD_REGION_RELATIVE_BOXES:
        prepared = _prepare_image_for_ocr(_relative_crop(image, relative_box))
        if rotation:
            prepared = prepared.rotate(rotation, expand=True)
        prepared_images.append(prepared)

    return prepared_images


def _format_easyocr_results(ocr_results) -> str:
    entries = []

    for index, result in enumerate(ocr_results):
        if isinstance(result, str):
            text = result.strip()
            if text:
                entries.append((float(index), 0.0, 1.0, text))
            continue

        if not isinstance(result, (list, tuple)) or len(result) < 2:
            continue

        bbox = result[0]
        text = str(result[1]).strip()
        confidence = result[2] if len(result) >= 3 else 1
        if not text:
            continue
        if confidence is not None and confidence < EASYOCR_MIN_CONFIDENCE:
            continue

        try:
            xs = [float(point[0]) for point in bbox]
            ys = [float(point[1]) for point in bbox]
        except (TypeError, ValueError, IndexError):
            entries.append((float(index), 0.0, 1.0, text))
            continue

        height = max(ys) - min(ys)
        entries.append((sum(ys) / len(ys), min(xs), max(height, 1.0), text))

    if not entries:
        return ""

    line_groups: list[dict[str, object]] = []
    for y_center, x_start, height, text in sorted(entries, key=lambda entry: (entry[0], entry[1])):
        if line_groups:
            previous_group = line_groups[-1]
            tolerance = max(10.0, float(previous_group["height"]), height) * 0.7
            if abs(y_center - float(previous_group["y"])) <= tolerance:
                previous_group["items"].append((x_start, text))
                previous_group["y"] = (float(previous_group["y"]) + y_center) / 2
                previous_group["height"] = max(float(previous_group["height"]), height)
                continue

        line_groups.append({"y": y_center, "height": height, "items": [(x_start, text)]})

    lines = []
    for group in line_groups:
        words = [text for _x_start, text in sorted(group["items"])]
        lines.append(" ".join(words))

    return "\n".join(lines)


def _extract_text_with_easyocr(image: Image.Image) -> str:
    reader = _load_easyocr_reader()
    if reader is None:
        return ""

    prepared = _resize_for_ocr(image).convert("RGB")
    try:
        import numpy as np
    except ImportError:
        image_input = prepared
    else:
        image_input = np.array(prepared)

    try:
        ocr_results = reader.readtext(
            image_input,
            detail=1,
            paragraph=False,
            decoder="greedy",
            batch_size=1,
        )
    except Exception:
        return ""

    return _format_easyocr_results(ocr_results)


def _score_ocr_text(raw_text: str) -> tuple[int, int, int]:
    cleaned = raw_text.strip()
    guesses = extract_field_guesses(cleaned)
    guessed_fields = sum(1 for value in guesses.values() if value)
    alphanumeric_chars = sum(1 for char in cleaned if char.isalnum())
    return guessed_fields, alphanumeric_chars, len(cleaned)


def _normalize_ocr_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _has_useful_text(value: str) -> bool:
    return any(char.isalnum() for char in value)


def _merge_ocr_results(results: list[str]) -> str:
    ordered_results = sorted(results, key=_score_ocr_text, reverse=True)
    merged_lines: list[str] = []

    for result in ordered_results:
        for line in result.splitlines():
            stripped = line.strip()
            if not stripped or not _has_useful_text(stripped):
                continue

            normalized = _normalize_ocr_line(stripped)
            existing_text = "\n".join(_normalize_ocr_line(line) for line in merged_lines)
            if normalized in existing_text:
                continue

            merged_lines.append(stripped)

    return "\n".join(merged_lines)


def _has_government_warning_guess(results: list[str]) -> bool:
    if not results:
        return False

    return bool(_guess_government_warning(_merge_ocr_results(results)))


def _should_try_field_region_ocr(image: Image.Image, results: list[str], started: float) -> bool:
    if not _is_wide_label(image):
        return False

    remaining_seconds = OCR_TIME_BUDGET_SECONDS - (time.perf_counter() - started)
    if remaining_seconds <= 0:
        return False

    if not results:
        return True

    guesses = extract_field_guesses(_merge_ocr_results(results))
    return any(not guesses.get(field) for field in FIELD_REGION_TRIGGER_FIELDS)


def _should_try_easyocr_fallback(results: list[str], started: float) -> bool:
    if _ocr_mode() != "fallback":
        return False

    remaining_seconds = OCR_TIME_BUDGET_SECONDS - (time.perf_counter() - started)
    if remaining_seconds < EASYOCR_MIN_REMAINING_SECONDS:
        return False

    if not results:
        return True

    guesses = extract_field_guesses(_merge_ocr_results(results))
    return any(not guesses.get(field) for field in EASYOCR_TRIGGER_FIELDS)


def _should_try_easyocr_first(started: float) -> bool:
    if _ocr_mode() != "strong":
        return False

    remaining_seconds = OCR_TIME_BUDGET_SECONDS - (time.perf_counter() - started)
    return remaining_seconds >= EASYOCR_MIN_REMAINING_SECONDS


def _guess_government_warning(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines()]

    for index, line in enumerate(lines):
        if not _is_warning_start(lines, index):
            continue

        warning_lines = []
        skipped_noise = 0
        for next_line in lines[index : index + MAX_WARNING_SCAN_LINES]:
            if not next_line:
                break

            if warning_lines and _is_likely_after_warning_field(next_line):
                break

            if _is_warning_line(next_line):
                cleaned_warning_line = _clean_warning_line(next_line)
                if cleaned_warning_line:
                    warning_lines.append(cleaned_warning_line)
                skipped_noise = 0
                continue

            if warning_lines:
                skipped_noise += 1
                if len(warning_lines) >= 3 and skipped_noise >= 4:
                    break

        if warning_lines:
            return "\n".join(warning_lines)

    return ""


def _is_warning_start(lines: list[str], index: int) -> bool:
    line = lines[index]
    if GOVERNMENT_WARNING_LABEL_PATTERN.search(line) or OCR_WARNING_LABEL_PATTERN.search(line):
        return True

    next_line = lines[index + 1] if index + 1 < len(lines) else ""
    combined = f"{line} {next_line}"
    return bool(GOVERNMENT_WARNING_LABEL_PATTERN.search(combined) or OCR_WARNING_LABEL_PATTERN.search(combined))


def _is_warning_line(line: str) -> bool:
    if WARNING_BODY_PATTERN.search(line):
        return True

    return re.search(r"^(?:\([12]\)|[12][).])\s*", line.strip()) is not None


def _clean_warning_line(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", line.strip())
    cleaned = re.sub(r"^[^A-Za-z0-9]*\(?F\s+(ALCOHOLIC\b)", r"OF \1", cleaned, flags=re.IGNORECASE)

    warning_phrase_match = re.search(
        r"\b(?:GOVERNMENT\s+WARNING|WOMEN\s+SHOULD|PREGNANCY\s*BECAUSE|OF\s+ALCOHOLIC\s+BEVERAGES|OR\s+OPERATE\s+MACHINERY|OPERATE\s+MACHINERY|MAY\s+CAUSE\s+HEALTH\s+PROBLEMS)\b",
        cleaned,
        re.IGNORECASE,
    )
    if warning_phrase_match is not None and warning_phrase_match.start() > 0:
        prefix = cleaned[: warning_phrase_match.start()]
        phrase = warning_phrase_match.group(0)
        if re.search(r"\bGOVERNMENT\s+WARNING\b", phrase, re.IGNORECASE) or not re.search(
            r"\b(?:SURGEON|GENERAL|ALCOHOLIC|BEVERAGES|DURING|CONSUMPTION|DRIVE|CAR|OPERATE|MACHINERY)\b",
            prefix,
            re.IGNORECASE,
        ):
            cleaned = cleaned[warning_phrase_match.start() :]
            if re.match(r"\bOPERATE\s+MACHINERY\b", cleaned, re.IGNORECASE):
                cleaned = f"OR {cleaned}"

    may_cause_match = re.search(r"\bMAY\s+CAUSE\s+HEALTH\s+PROBLEMS\.?", cleaned, re.IGNORECASE)
    prefix_before_may_cause = cleaned[: may_cause_match.start()] if may_cause_match is not None else ""
    if (
        may_cause_match is not None
        and may_cause_match.start() > 0
        and not re.search(r"\b(?:OR|OPERATE|MACHINERY)\b", prefix_before_may_cause, re.IGNORECASE)
    ):
        cleaned = cleaned[may_cause_match.start() :]

    cleaned = re.sub(r"\bPREGNANCY\s*BECAUSE\b", "PREGNANCY BECAUSE", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bDEFECTS\.\s*\(?2\)", "DEFECTS. (2)", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(\bACCORDING TO)\s+\d+\b$", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(\bDURING)\s+[=~_\-\\/|\s]+[A-Za-z]?$", r"\1", cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def _is_likely_after_warning_field(line: str) -> bool:
    return bool(
        ALCOHOL_CONTENT_PATTERN.search(line)
        or NET_CONTENTS_PATTERN.search(line)
        or BOTTLER_ADDRESS_PATTERN.search(line)
    )


def _clean_guess_line(line: str) -> str:
    return re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9.)]+$", "", line.strip())


def _clean_multiline_guess(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _clean_address_guess(value: str) -> str:
    cleaned = re.sub(r"\s*\|\s*", ", ", value.strip())
    cleaned = _clean_multiline_guess(cleaned)
    cleaned = re.sub(r"\s*,\s*,\s*", ", ", cleaned)
    return cleaned.strip(" ,:;-\"“”")


def _normalize_number_text(value: str) -> str:
    if "." not in value:
        return str(int(value))

    return value.rstrip("0").rstrip(".")


def _clean_net_contents_match(match: re.Match[str]) -> str:
    amount = match.group("amount")
    unit = re.sub(r"\s+", " ", match.group("unit").strip())

    if re.fullmatch(r"fl\.?\s*oz\.?", unit, flags=re.IGNORECASE):
        normalized_amount = _normalize_number_text(amount)
        if "." not in amount and len(amount) > 2:
            for common_amount in sorted(COMMON_FLUID_OUNCE_AMOUNTS, key=len, reverse=True):
                if amount.endswith(common_amount.replace(".", "")):
                    normalized_amount = common_amount
                    break
            if normalized_amount != _normalize_number_text(amount):
                return f"{normalized_amount} {unit}"

    return match.group(0).strip()


def _guess_net_contents(raw_text: str) -> str:
    net_match = NET_CONTENTS_VALUE_PATTERN.search(raw_text)
    if net_match is None:
        return ""

    return _clean_net_contents_match(net_match)


def _clean_company_candidate(candidate: str) -> str:
    cleaned = _clean_multiline_guess(candidate)
    cleaned = re.sub(r"\bCO[.e0]?\b\.?", "CO.", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" ,:;-\"“”")
    cleaned = re.sub(r"(\bCO\.)\s*,?\s+[A-Za-z]$", r"\1", cleaned, flags=re.IGNORECASE)

    words = cleaned.split()
    while words:
        leading_word = re.sub(r"[^A-Za-z0-9]", "", words[0]).upper()
        if leading_word not in COMPANY_LEADING_NOISE_WORDS:
            break
        words.pop(0)

    return " ".join(words).strip(" ,:;-\"“”")


def _extract_producer_company(value: str) -> str:
    candidates = []
    for match in COMPANY_CANDIDATE_PATTERN.finditer(value):
        candidate = _clean_company_candidate(match.group(1))
        if _is_weak_company_suffix_fragment(candidate):
            continue
        if candidate and BRAND_SUFFIX_PATTERN.search(candidate):
            candidates.append(candidate)

    return candidates[-1] if candidates else ""


def _is_weak_company_suffix_fragment(candidate: str) -> bool:
    cleaned = _clean_guess_line(candidate)
    words = re.findall(r"[A-Za-z0-9]+", cleaned)
    if not words:
        return True

    suffixes = {"BREWING", "BREWERY", "DISTILLERY", "WINERY", "VINEYARD", "VINEYARDS"}
    if len(words) == 1 and words[0].upper() in suffixes:
        return True

    if len(words) != 2 or words[1].upper() not in suffixes:
        return False

    prefix = words[0]
    alpha_count = sum(1 for char in prefix if char.isalpha())
    if alpha_count > 0 and len(prefix) <= 3 and (prefix.isupper() or prefix.islower()):
        return True

    return False


def _producer_from_brewed_canned_address(address: str) -> str:
    match = re.search(r"\bBY\s+(.+)$", address, re.IGNORECASE)
    if match is None:
        return ""

    return _extract_producer_company(match.group(1))


def _meaningful_lines(raw_text: str) -> list[str]:
    return [
        cleaned
        for line in raw_text.splitlines()
        if (cleaned := _clean_guess_line(line)) and any(char.isalpha() for char in cleaned)
    ]


def _guess_class_type(raw_text: str) -> str:
    candidates: list[tuple[int, str]] = []

    for line in _meaningful_lines(raw_text):
        if len(line) > 80:
            continue
        if ALCOHOL_CONTENT_PATTERN.search(line) or NET_CONTENTS_PATTERN.search(line):
            continue
        if CLASS_SENTENCE_NOISE_PATTERN.search(line):
            continue
        if not CLASS_TYPE_PATTERN.search(line):
            continue
        type_phrase = _extract_alcohol_type_phrase(line)
        if not type_phrase:
            continue

        words = re.findall(r"[A-Za-z0-9']+", type_phrase)
        letters = [char for char in type_phrase if char.isalpha()]
        uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters) if letters else 0
        score = 0
        if len(words) <= 5:
            score += 4
        if uppercase_ratio >= 0.65:
            score += 4
        if all(word[:1].isupper() or word.isdigit() for word in words):
            score += 2
        if "," in line:
            score -= 4
        candidates.append((score, type_phrase))

    explicit_guess = max(candidates, default=(0, ""))[1]
    if explicit_guess:
        return explicit_guess

    normalized_text = _normalize_ocr_line(raw_text)
    if re.search(r"\b(?:brewed|brewery|brewing)\b", normalized_text):
        return "Beer"
    if re.search(r"\b(?:winery|vineyard|vineyards|grape|grapes)\b", normalized_text):
        return "Wine"
    if re.search(r"\b(?:distillery|distilled)\b", normalized_text):
        return "Distilled spirits"

    return ""


def _extract_alcohol_type_phrase(line: str) -> str:
    cleaned = re.sub(r"^\d{4}\s+", "", line.strip())
    for pattern, canonical_type in ALCOHOL_TYPE_PATTERNS:
        match = pattern.search(cleaned)
        if match is not None:
            return canonical_type

    return ""


def _brand_from_bottler_line(raw_text: str) -> str:
    for line in _meaningful_lines(raw_text):
        if not re.search(r"\b(?:brewed|bottled|produced|distilled)\b", line, re.IGNORECASE):
            continue
        match = re.search(r"\bby\s+(.+?)(?:\s*\||,|\s{2,}|$)", line, re.IGNORECASE)
        if match is None:
            continue
        candidate = _extract_producer_company(match.group(1)) or _clean_guess_line(match.group(1))
        if _is_weak_company_suffix_fragment(candidate):
            continue
        if BRAND_SUFFIX_PATTERN.search(candidate):
            return candidate.upper() if candidate.isupper() else candidate

    return ""


def _guess_brand_name(raw_text: str, class_type_guess: str = "") -> str:
    bottler_brand = _brand_from_bottler_line(raw_text)
    brewed_canned_brand = _producer_from_brewed_canned_address(_guess_brewed_canned_address(raw_text))
    candidates: list[tuple[int, str]] = []

    if brewed_canned_brand:
        candidates.append((24, brewed_canned_brand))

    if bottler_brand:
        candidates.append((12, bottler_brand))

    for line in _meaningful_lines(raw_text):
        company_candidate = _extract_producer_company(line)
        if company_candidate:
            line = company_candidate

        if len(line) > 80:
            continue
        if _is_weak_company_suffix_fragment(line):
            continue
        if line == class_type_guess:
            continue
        if _normalize_ocr_line(line) in GENERIC_BRAND_LABELS:
            continue
        if BRAND_EXCLUSION_PATTERN.search(line):
            continue
        if SERVING_INSTRUCTION_PATTERN.search(line):
            continue
        if CITY_STATE_PATTERN.search(line) or FULL_STATE_CITY_PATTERN.search(line) or POSTAL_ADDRESS_PATTERN.search(line):
            continue
        if CLASS_TYPE_PATTERN.search(line):
            continue

        letters = [char for char in line if char.isalpha()]
        if len(letters) < 4:
            continue
        uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
        words = re.findall(r"[A-Za-z0-9']+", line)
        score = 0
        if BRAND_SUFFIX_PATTERN.search(line):
            score += 6
        if uppercase_ratio >= 0.65:
            score += 3
        if len(words) <= 5:
            score += 2
        score += max(0, 6 - len(words))
        if all(word[:1].isupper() or word.isdigit() for word in words):
            score += 2
        if len(words) == 1:
            score -= 2

        candidates.append((score, line))

    best_score, best_value = max(candidates, default=(0, ""))
    return best_value if best_score >= BRAND_MINIMUM_SCORE else ""


def _guess_country_of_origin(raw_text: str) -> str:
    for pattern in COUNTRY_OF_ORIGIN_PATTERNS:
        match = pattern.search(raw_text)
        if match is not None:
            return match.group(1).strip(" .,:;-")

    return ""


def _is_potential_name_component(line: str) -> bool:
    if len(line) > 80:
        return False
    if _is_weak_company_suffix_fragment(line):
        return False
    if _normalize_ocr_line(line) in GENERIC_BRAND_LABELS:
        return False
    if BRAND_EXCLUSION_PATTERN.search(line):
        return False
    if SERVING_INSTRUCTION_PATTERN.search(line):
        return False
    if CLASS_TYPE_PATTERN.search(line):
        return False
    if ALCOHOL_CONTENT_PATTERN.search(line) or NET_CONTENTS_PATTERN.search(line):
        return False
    if CITY_STATE_PATTERN.search(line) or FULL_STATE_CITY_PATTERN.search(line) or POSTAL_ADDRESS_PATTERN.search(line):
        return False

    letters = [char for char in line if char.isalpha()]
    if len(letters) < 4:
        return False

    words = re.findall(r"[A-Za-z0-9']+", line)
    return 1 <= len(words) <= 6


def _extract_city_state(line: str) -> str:
    full_state_match = FULL_STATE_CITY_PATTERN.search(line)
    if full_state_match is not None:
        state = full_state_match.group(1).rsplit(",", 1)[1].strip().upper()
        if state in US_STATE_NAMES:
            return _clean_address_guess(full_state_match.group(1))

    match = CITY_STATE_PATTERN.search(line)
    if match is None:
        return ""

    state = match.group(1).rsplit(",", 1)[1].strip().upper()
    if state not in US_STATE_CODES:
        return ""

    return _clean_address_guess(match.group(1))


def _producer_name_component(line: str) -> str:
    company = _extract_producer_company(line)
    if company:
        return company

    cleaned = _clean_guess_line(line)
    return cleaned if _is_potential_name_component(cleaned) else ""


def _dedupe_address_candidates(
    candidates: list[tuple[str, str, float]],
) -> list[tuple[str, str, float]]:
    deduped = []
    seen = set()
    for value, source, confidence in candidates:
        normalized = _normalize_ocr_line(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append((value, source, confidence))

    return deduped


def _address_name_location_separator(company: str, has_postal_address: bool) -> str:
    if has_postal_address:
        return " "

    if re.search(r"\b(?:CO\.|LLC\.?|INC\.?|COMPANY)\.?$", company, re.IGNORECASE):
        return " "

    return ", "


def _guess_brewed_canned_address(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        match = re.search(
            r"\b(BREWED\s*(?:&|AND)\s*CANNED\s+IN\s+.+?,\s*[A-Z]{2})\s+BY\b(.*)",
            line,
            re.IGNORECASE,
        )
        if match is None:
            continue

        producer = _extract_producer_company(match.group(2))
        if not producer:
            for next_line in lines[index + 1 : index + 4]:
                producer = _extract_producer_company(next_line)
                if producer:
                    break

        if producer:
            location = _clean_multiline_guess(match.group(1))
            return f"{location} BY {producer}"

    brewed_canned_match = BREWED_CANNED_ADDRESS_PATTERN.search(raw_text)
    if brewed_canned_match is not None:
        address = _clean_multiline_guess(brewed_canned_match.group(1))
        producer = _extract_producer_company(address)
        if producer:
            prefix_match = re.search(
                r"\b(BREWED\s*(?:&|AND)\s*CANNED\s+IN\s+.+?,\s*[A-Z]{2})\s+BY\b",
                address,
                re.IGNORECASE,
            )
            if prefix_match is not None:
                return f"{_clean_multiline_guess(prefix_match.group(1))} BY {producer}"
        return address

    return ""


def _bottler_address_candidates(raw_text: str) -> list[tuple[str, str, float]]:
    candidates: list[tuple[str, str, float]] = []

    bottler_match = BOTTLER_ADDRESS_PATTERN.search(raw_text)
    if bottler_match is not None:
        candidates.append(
            (
                _clean_address_guess(bottler_match.group(0)),
                "bottler_address_pattern",
                0.9,
            )
        )

    brewed_canned_address = _guess_brewed_canned_address(raw_text)
    if brewed_canned_address:
        candidates.append((brewed_canned_address, "brewed_canned_address", 0.88))

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        address_match = POSTAL_ADDRESS_PATTERN.search(line)
        city_state = _extract_city_state(line)
        if address_match is None and not city_state:
            continue

        address = _clean_address_guess(address_match.group(1) if address_match is not None else city_state)
        for previous_line in reversed(lines[max(0, index - 3) : index]):
            company = _producer_name_component(previous_line)
            if not company:
                continue

            separator = _address_name_location_separator(company, address_match is not None)
            source = "nearby_name_postal_address" if address_match is not None else "nearby_name_city_state"
            confidence = 0.84 if address_match is not None else 0.74
            candidates.append((f"{company}{separator}{address}", source, confidence))
            break

    return _dedupe_address_candidates(candidates)


def _guess_bottler_address(raw_text: str) -> str:
    candidates = _bottler_address_candidates(raw_text)
    return max(candidates, key=lambda candidate: candidate[2])[0] if candidates else ""

    return ""


def extract_text_from_image(image_bytes: bytes) -> tuple[str, int]:
    started = time.perf_counter()
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            results = []
            last_ocr_error: Exception | None = None
            rotated_warning_attempted = False
            field_region_attempted = False

            if _should_try_easyocr_first(started):
                easyocr_text = _extract_text_with_easyocr(image)
                if easyocr_text.strip():
                    results.append(easyocr_text)

            prepared_images = _prepare_image_variants_for_ocr(image)

            try:
                for variant_index, prepared_image in enumerate(prepared_images):
                    for config in OCR_CONFIGS:
                        remaining_seconds = OCR_TIME_BUDGET_SECONDS - (time.perf_counter() - started)
                        if remaining_seconds <= 0:
                            break

                        try:
                            raw_text = pytesseract.image_to_string(
                                prepared_image,
                                config=config,
                                timeout=max(0.5, remaining_seconds),
                            )
                        except (pytesseract.TesseractError, RuntimeError) as exc:
                            last_ocr_error = exc
                            continue

                        if raw_text.strip():
                            results.append(raw_text)

                    if OCR_TIME_BUDGET_SECONDS - (time.perf_counter() - started) <= 0:
                        break

                    if (
                        variant_index == 0
                        and not field_region_attempted
                        and _should_try_field_region_ocr(image, results, started)
                    ):
                        field_region_attempted = True
                        for prepared_image in _prepare_field_region_images_for_ocr(image):
                            for config in FIELD_REGION_CONFIGS:
                                remaining_seconds = OCR_TIME_BUDGET_SECONDS - (time.perf_counter() - started)
                                if remaining_seconds <= 0:
                                    break

                                try:
                                    raw_text = pytesseract.image_to_string(
                                        prepared_image,
                                        config=config,
                                        timeout=max(0.5, remaining_seconds),
                                    )
                                except (pytesseract.TesseractError, RuntimeError) as exc:
                                    last_ocr_error = exc
                                    continue

                                if raw_text.strip():
                                    results.append(raw_text)

                    if (
                        variant_index == 0
                        and not rotated_warning_attempted
                        and not _has_government_warning_guess(results)
                    ):
                        rotated_warning_attempted = True
                        for prepared_image in _prepare_rotated_warning_images_for_ocr(image):
                            for config in ROTATED_WARNING_CONFIGS:
                                remaining_seconds = OCR_TIME_BUDGET_SECONDS - (time.perf_counter() - started)
                                if remaining_seconds <= 0:
                                    break

                                try:
                                    raw_text = pytesseract.image_to_string(
                                        prepared_image,
                                        config=config,
                                        timeout=max(0.5, remaining_seconds),
                                    )
                                except (pytesseract.TesseractError, RuntimeError) as exc:
                                    last_ocr_error = exc
                                    continue

                                if raw_text.strip():
                                    results.append(raw_text)
                                    if _guess_government_warning(raw_text):
                                        break

                            if _has_government_warning_guess(results):
                                break
            except pytesseract.TesseractNotFoundError as exc:
                raise ExtractionError(
                    "OCR engine is not installed. Install Tesseract or use raw text override."
                ) from exc

            if _should_try_easyocr_fallback(results, started):
                easyocr_text = _extract_text_with_easyocr(image)
                if easyocr_text.strip():
                    results.append(easyocr_text)

            if not results and last_ocr_error is not None:
                raise ExtractionError("OCR failed while reading the image.") from last_ocr_error
    except (UnidentifiedImageError, OSError) as exc:
        raise ExtractionError("Unsupported or unreadable image file.") from exc

    cleaned = _merge_ocr_results(results).strip() if results else ""
    if not cleaned:
        raise ExtractionError("No readable text was found in the image.")

    return cleaned, round((time.perf_counter() - started) * 1000)


def _field_candidate(
    field: str,
    value: str,
    source: str,
    confidence: float,
    raw_text: str = "",
) -> FieldCandidate | None:
    cleaned_value = value.strip()
    if not cleaned_value:
        return None

    return FieldCandidate(
        field=field,
        value=cleaned_value,
        source=source,
        confidence=max(0.0, min(confidence, 1.0)),
        raw_text=raw_text.strip() or cleaned_value,
    )


def _append_candidate(
    candidates: dict[str, list[FieldCandidate]],
    field: str,
    value: str,
    source: str,
    confidence: float,
    raw_text: str = "",
) -> None:
    candidate = _field_candidate(field, value, source, confidence, raw_text)
    if candidate is not None:
        candidates[field].append(candidate)


def _alcohol_content_confidence(value: str) -> float:
    if re.search(r"\b(?:proof|by\s+vol(?:ume)?|/\s*vol|alcohol\s+volume)\b", value, re.IGNORECASE):
        return 0.92

    return 0.84


def _net_contents_confidence(value: str, raw_value: str) -> float:
    if value != raw_value.strip():
        return 0.72

    if re.fullmatch(r"\d+(?:\.\d+)?\s*(?:mL|fl\.?\s*oz\.?|L|pints?)\.?", value, re.IGNORECASE):
        return 0.9

    return 0.8


def _class_type_confidence(raw_text: str, value: str) -> float:
    if any(pattern.search(raw_text) and canonical_type == value for pattern, canonical_type in ALCOHOL_TYPE_PATTERNS):
        return 0.88

    return 0.66


def extract_field_candidates(raw_text: str) -> dict[str, list[FieldCandidate]]:
    class_type_guess = _guess_class_type(raw_text)
    candidates: dict[str, list[FieldCandidate]] = {field: [] for field in EXTRACTED_FIELDS}

    _append_candidate(
        candidates,
        "brand_name",
        _guess_brand_name(raw_text, class_type_guess),
        "brand_name_heuristic",
        0.78,
    )
    _append_candidate(
        candidates,
        "class_type",
        class_type_guess,
        "class_type_pattern",
        _class_type_confidence(raw_text, class_type_guess) if class_type_guess else 0,
    )

    for match in ALCOHOL_CONTENT_PATTERN.finditer(raw_text):
        value = match.group(0).strip()
        _append_candidate(
            candidates,
            "alcohol_content",
            value,
            "alcohol_content_pattern",
            _alcohol_content_confidence(value),
            value,
        )

    for match in NET_CONTENTS_VALUE_PATTERN.finditer(raw_text):
        raw_value = match.group(0).strip()
        value = _clean_net_contents_match(match)
        _append_candidate(
            candidates,
            "net_contents",
            value,
            "net_contents_pattern",
            _net_contents_confidence(value, raw_value),
            raw_value,
        )

    for value, source, confidence in _bottler_address_candidates(raw_text):
        _append_candidate(
            candidates,
            "bottler_address",
            value,
            source,
            confidence,
            value,
        )
    _append_candidate(
        candidates,
        "country_of_origin",
        _guess_country_of_origin(raw_text),
        "country_of_origin_pattern",
        0.86,
    )
    _append_candidate(
        candidates,
        "government_warning",
        _guess_government_warning(raw_text),
        "government_warning_block",
        0.84,
    )

    return candidates


def select_field_guesses(candidates: dict[str, list[FieldCandidate]]) -> dict[str, str]:
    guesses = {field: "" for field in EXTRACTED_FIELDS}

    for field in guesses:
        field_candidates = candidates.get(field, [])
        if not field_candidates:
            continue

        _index, selected = max(
            enumerate(field_candidates),
            key=lambda item: (item[1].confidence, -item[0]),
        )
        guesses[field] = selected.value

    return guesses


def extract_field_guesses(raw_text: str) -> dict[str, str]:
    return select_field_guesses(extract_field_candidates(raw_text))

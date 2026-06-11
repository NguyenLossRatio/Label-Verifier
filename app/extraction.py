import io
import re
import time

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
import pytesseract


class ExtractionError(Exception):
    pass


ALCOHOL_CONTENT_PATTERN = re.compile(
    r"\b\d{1,2}(?:\.\d+)?\s*%\s*(?:(?:Alc|Alcohol)\.?\s*/\s*Vol\.?|Alcohol\s+Volume)(?:\s*\(\d{1,3}\s*Proof\))?",
    re.IGNORECASE,
)
NET_CONTENTS_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mL|fl\.?\s*oz\.?|L|pints?)\.?(?=\s|$|[),;])",
    re.IGNORECASE,
)
BOTTLER_ADDRESS_PATTERN = re.compile(
    r"^.*\b(?:Bottled by|Produced by|Distilled by)\b.*$",
    re.IGNORECASE | re.MULTILINE,
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
CLASS_SENTENCE_NOISE_PATTERN = re.compile(
    r"\b(?:this|that|with|into|from|their|there|because|during|after|before|your|great|small|tart|for|and|or|health|problems|contains|sulfites|warning|surgeon|pregnancy|risk|defects|impairs|operate|machinery)\b",
    re.IGNORECASE,
)
BRAND_SUFFIX_PATTERN = re.compile(r"\b(?:brewing|brewery|distillery|estate|winery|vineyards?)\b", re.IGNORECASE)
GENERIC_BRAND_LABELS = {
    "brewery",
    "distillery",
    "estate winery",
    "winery",
}
MAX_OCR_IMAGE_DIMENSION = 2200
MIN_OCR_IMAGE_DIMENSION = 1400
MAX_OCR_UPSCALE_FACTOR = 3
OCR_TIME_BUDGET_SECONDS = 4.5
OCR_CONFIGS = ("--psm 6", "--psm 11")
ROTATED_WARNING_CONFIGS = ("--psm 6",)
ROTATED_WARNING_ANGLES = (90, 180, 270)
MAX_WARNING_SCAN_LINES = 24


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
    return [prepared.rotate(angle, expand=True) for angle in ROTATED_WARNING_ANGLES]


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
                warning_lines.append(next_line)
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


def _is_likely_after_warning_field(line: str) -> bool:
    return bool(
        ALCOHOL_CONTENT_PATTERN.search(line)
        or NET_CONTENTS_PATTERN.search(line)
        or BOTTLER_ADDRESS_PATTERN.search(line)
    )


def _clean_guess_line(line: str) -> str:
    return re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9.)]+$", "", line.strip())


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
        candidate = _clean_guess_line(match.group(1))
        if BRAND_SUFFIX_PATTERN.search(candidate):
            return candidate.upper() if candidate.isupper() else candidate

    return ""


def _guess_brand_name(raw_text: str, class_type_guess: str = "") -> str:
    bottler_brand = _brand_from_bottler_line(raw_text)
    candidates: list[tuple[int, str]] = []

    if bottler_brand:
        candidates.append((12, bottler_brand))

    for line in _meaningful_lines(raw_text):
        if len(line) > 80:
            continue
        if line == class_type_guess:
            continue
        if _normalize_ocr_line(line) in GENERIC_BRAND_LABELS:
            continue
        if BRAND_EXCLUSION_PATTERN.search(line):
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

    return max(candidates, default=(0, ""))[1]


def _guess_country_of_origin(raw_text: str) -> str:
    for pattern in COUNTRY_OF_ORIGIN_PATTERNS:
        match = pattern.search(raw_text)
        if match is not None:
            return match.group(1).strip(" .,:;-")

    return ""


def extract_text_from_image(image_bytes: bytes) -> tuple[str, int]:
    started = time.perf_counter()
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            prepared_images = _prepare_image_variants_for_ocr(image)
            results = []
            last_ocr_error: Exception | None = None
            rotated_warning_attempted = False

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

            if not results and last_ocr_error is not None:
                raise ExtractionError("OCR failed while reading the image.") from last_ocr_error
    except (UnidentifiedImageError, OSError) as exc:
        raise ExtractionError("Unsupported or unreadable image file.") from exc

    cleaned = _merge_ocr_results(results).strip() if results else ""
    if not cleaned:
        raise ExtractionError("No readable text was found in the image.")

    return cleaned, round((time.perf_counter() - started) * 1000)


def extract_field_guesses(raw_text: str) -> dict[str, str]:
    alcohol_match = ALCOHOL_CONTENT_PATTERN.search(raw_text)
    net_match = NET_CONTENTS_PATTERN.search(raw_text)
    bottler_match = BOTTLER_ADDRESS_PATTERN.search(raw_text)
    class_type_guess = _guess_class_type(raw_text)

    return {
        "brand_name": _guess_brand_name(raw_text, class_type_guess),
        "class_type": class_type_guess,
        "alcohol_content": alcohol_match.group(0).strip() if alcohol_match else "",
        "net_contents": net_match.group(0).strip() if net_match else "",
        "bottler_address": bottler_match.group(0).strip() if bottler_match else "",
        "country_of_origin": _guess_country_of_origin(raw_text),
        "government_warning": _guess_government_warning(raw_text),
    }

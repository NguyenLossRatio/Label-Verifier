# Label Verifier

Label Verifier is a FastAPI prototype for reviewing alcohol label text against standardized liquor application data. It accepts one uploaded JSON application file containing expected application fields and a base64-encoded label attachment, extracts likely field values from the label with OCR, and reports pass, mismatch, missing, or needs-review results.

## What It Checks

- Brand name
- Class/type
- Alcohol content
- Net contents
- Bottler/producer address
- Country of origin, when provided
- Government warning, using the fixed required warning text in `app/constants.py`

The government warning is not entered by the user. The app always compares extracted text against the hardcoded required warning.

## Review Disclaimer

This is a prototype review aid, not an official compliance determination. Results should be treated as prompts for human review, especially when a field is marked `mismatch`, `missing`, or `needs_review`.

Formatting and text-matching rules are intentionally conservative and still need policy validation. The correct level of strictness may vary by field: some values may allow harmless differences in capitalization, punctuation, line breaks, abbreviations, or spacing, while other required statements may need exact wording and capitalization. Until those rules are confirmed, the app may flag labels that a reviewer would accept, and it may miss issues that depend on regulatory context outside the current prototype schema.

## Architecture

- `app/main.py` defines the FastAPI app, serves the static UI, exposes `/api/health`, and handles `POST /api/verify`.
- `app/application_upload.py` parses and validates the liquor application JSON, required text fields, and embedded label attachment.
- `app/extraction.py` decodes the label image with Tesseract OCR and produces field candidates/guesses.
- `app/verification.py` compares expected application fields against OCR text and structured guesses.
- `app/static/` contains the browser UI for uploading a single JSON application file and displaying verification results.
- `requirements.txt`, `railpack.json`, and `nixpacks.toml` define the Railway/runtime deployment setup, including Tesseract.

Request flow:

1. User uploads one `.json` liquor application file.
2. Backend validates required fields and `label_attachment`.
3. Backend decodes the embedded label image and runs OCR.
4. Extracted text and field guesses are compared with the JSON application values.
5. API returns per-field results, OCR candidates, guesses, and overall status.

## Example Labels

Example assets are in `examplelabels/`.

- Raw label images are stored as `.jpg`, `.png`, or `.webp` files.
- Upload-ready JSON application fixtures are stored beside them as `*.application.json`.
- Each `.application.json` includes the standardized expected fields and an embedded base64 copy of its matching label image.

Current example application files:

```text
examplelabels/alcohol-content-new1.application.json
examplelabels/brand-label-new2.application.json
examplelabels/hws2.application.json
examplelabels/limerence.application.json
examplelabels/orpheus_seal_main.application.json
examplelabels/prbc-lizzie-twister-blackberry-trade-entire-label-mar2022.application.json
examplelabels/prop.application.json
examplelabels/winelabel-example.application.json
```

## Requirements

- Python 3.11 or newer
- Tesseract OCR, available on your shell path

On macOS:

```bash
brew install tesseract
```

On Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

Confirm Tesseract is available:

```bash
tesseract --version
```

## Setup

From the repository root, create a virtual environment, upgrade `pip`, and install the app with development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If you only need the runtime dependencies, install from `requirements.txt` instead:

```bash
python -m pip install -r requirements.txt
```

## Run Locally

Start the FastAPI development server:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000
```

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok"}
```

You can also verify the API with a bundled example application:

```bash
curl -X POST http://127.0.0.1:8000/api/verify \
  -F 'application_file=@examplelabels/orpheus_seal_main.application.json;type=application/json'
```

## Use The App

1. Upload one liquor application `.json` file.
2. Confirm the application fields and embedded label preview load.
3. Select `Verify Label`.
4. Review extracted values, expected application values, confidence/source candidates, and field status messages.

## Input Fields

`POST /api/verify` accepts multipart form data with one file field:

- `application_file`: required JSON upload, using content type `application/json` or `text/json`

The JSON application must include these required nonblank strings:

- `brand_name`
- `class_type`
- `alcohol_content`
- `net_contents`
- `bottler_address`

Optional field:

- `country_of_origin`: optional string, defaults to blank

Required attachment object:

- `label_attachment.filename`: original label image filename
- `label_attachment.content_type`: image content type such as `image/jpeg`, `image/png`, or `image/webp`
- `label_attachment.data`: base64-encoded label image bytes

Limits:

- Application JSON: 10 MB maximum
- Decoded label image: 6 MB maximum
- Label image dimensions: 16,000,000 pixels maximum

`government_warning` is intentionally not an application input field. The app always compares extracted text against the hardcoded required warning.

Example JSON shape:

```json
{
  "brand_name": "OLD TOM DISTILLERY",
  "class_type": "Kentucky Straight Bourbon Whiskey",
  "alcohol_content": "45% Alc./Vol. (90 Proof)",
  "net_contents": "750 mL",
  "bottler_address": "Old Tom Distillery, Louisville, KY",
  "country_of_origin": "",
  "label_attachment": {
    "filename": "label.png",
    "content_type": "image/png",
    "data": "base64-encoded-image-bytes"
  }
}
```

Example API request:

```bash
curl -X POST http://127.0.0.1:8000/api/verify \
  -F 'application_file=@examplelabels/orpheus_seal_main.application.json;type=application/json'
```

## Test

```bash
.venv/bin/python -m pytest
```

## OCR Defaults

The default local OCR path is Tesseract-only. Decoded label attachment images are resized before OCR so the longest side is at most `1600px`, which keeps local runs faster while preserving enough detail for typical label text.

## Optional Strong OCR

Optional EasyOCR support exists behind environment flags and the `strong-ocr` extra, but it is not required for normal local use.

```bash
.venv/bin/python -m pip install -e ".[dev,strong-ocr]"
```

Useful environment variables:

- `LABEL_VERIFIER_USE_EASYOCR=0` disables EasyOCR.
- `LABEL_VERIFIER_OCR_MODE=tesseract` uses Tesseract-only OCR. This is the default.
- `LABEL_VERIFIER_OCR_MODE=fallback` uses Tesseract first with optional EasyOCR fallback.
- `LABEL_VERIFIER_OCR_MODE=strong` tries EasyOCR first when installed.

## Deployment Notes

Railway deployment config is included:

- `railpack.json`
- `nixpacks.toml`
- `requirements.txt`

The deployment installs `tesseract-ocr` and starts Uvicorn with:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Production is deployed on Railway at:

```text
https://ttb-label-reader-production.up.railway.app
```

## Current Limitations

- OCR accuracy depends on image quality, orientation, contrast, and font legibility.
- The extractor uses field-specific heuristics, not a trained label-understanding model.
- Alcohol type detection is limited to the currently encoded type patterns and may miss less common classes, specialty products, or nuanced TTB class/type distinctions.
- Field matching strictness is not final. The prototype currently mixes tolerant matching for some fields with strict government warning text comparison, but the exact formatting and wording rules need compliance review.
- Testing data is limited to a small local set of example labels and synthetic cases, not a broad validated corpus of real TTB applications and labels.
- The exact format of a standardized TTB application input is not yet known; the current JSON structure is a prototype schema for this app.
- The JSON application schema only includes the core fields currently verified by the app; it does not yet model optional TTB application fields or conditional fields that may appear on full applications.
- Embedded label attachments are processed for the current request and are not stored by the app.
- Accounts, COLA integration, and long-term storage are out of scope.

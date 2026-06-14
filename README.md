# Label Verifier

Label Verifier is a local FastAPI prototype for reviewing alcohol label text against expected TTB-style label fields. It accepts an uploaded label image, extracts likely field values with OCR, and reports pass, mismatch, missing, or needs-review results.

## What It Checks

- Brand name
- Class/type
- Alcohol content
- Net contents
- Bottler/producer address
- Country of origin, when provided
- Government warning, using the fixed required warning text in `app/constants.py`

The government warning is not entered by the user. The app always compares extracted text against the hardcoded required warning.

## Requirements

- Python 3.11 or newer
- Tesseract OCR

On macOS:

```bash
brew install tesseract
```

## Setup

Create a virtual environment and install the app with development dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

For deployment-style installs, the pinned runtime dependency list is also available in `requirements.txt`:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

## Run Locally

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
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

## Use The App

1. Upload a label image.
2. Fill in the expected fields you want to compare.
3. Leave expected fields blank when you are testing extraction only.
4. Select `Verify Label`.
5. Review extracted values, expected values, confidence/source candidates, and field status messages.

## API

`POST /api/verify` accepts multipart form data:

- `label_image`: required image upload
- `brand_name`
- `class_type`
- `alcohol_content`
- `net_contents`
- `bottler_address`
- `country_of_origin`

`label_image` is required. `government_warning` is intentionally not an input field.

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/verify \
  -F brand_name="ORPHEUS BREWING" \
  -F class_type="Ale" \
  -F alcohol_content="" \
  -F net_contents="12 FL. OZ." \
  -F bottler_address="" \
  -F country_of_origin="" \
  -F label_image=@examplelabels/orpheus_seal_main.jpg
```

## Test

```bash
.venv/bin/python -m pytest
```

## OCR Defaults

The default local OCR path is Tesseract-only. Uploaded images are resized before OCR so the longest side is at most `1600px`, which keeps local runs faster while preserving enough detail for typical label text.

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

## Current Limitations

- OCR accuracy depends on image quality, orientation, contrast, and font legibility.
- The extractor uses field-specific heuristics, not a trained label-understanding model.
- Uploaded labels are processed for the current request and are not stored by the app.
- Blank expected fields are treated as extraction-only testing fields and return `needs_review`.
- Batch review, accounts, COLA integration, and long-term storage are out of scope.

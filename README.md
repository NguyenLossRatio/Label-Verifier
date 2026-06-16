# Label Verifier

Label Verifier is a local FastAPI prototype for reviewing alcohol label text against standardized liquor application data. It accepts one uploaded JSON application file containing expected application fields and a base64-encoded label attachment, extracts likely field values from the label with OCR, and reports pass, mismatch, missing, or needs-review results.

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

1. Upload one liquor application `.json` file.
2. Confirm the application fields and embedded label preview load.
3. Select `Verify Label`.
4. Review extracted values, expected application values, confidence/source candidates, and field status messages.

## API

`POST /api/verify` accepts multipart form data:

- `application_file`: required JSON upload

The JSON application must include standardized expected fields and a base64 image attachment. `brand_name`, `class_type`, `alcohol_content`, `net_contents`, and `bottler_address` are required nonblank strings; `country_of_origin` is optional. `label_attachment.data` must contain base64 image bytes.

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

`government_warning` is intentionally not an application input field. The app always compares extracted text against the hardcoded required warning.

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/verify \
  -F 'application_file=@path/to/application.json;type=application/json'
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

## Current Limitations

- OCR accuracy depends on image quality, orientation, contrast, and font legibility.
- The extractor uses field-specific heuristics, not a trained label-understanding model.
- Embedded label attachments are processed for the current request and are not stored by the app.
- Batch review, accounts, COLA integration, and long-term storage are out of scope.

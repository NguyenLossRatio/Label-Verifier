# Label Verifier

Label Verifier is a guided alcohol label review prototype. It extracts or accepts label text, compares it with expected label fields, and reports whether the label appears compliant or needs manual review.

## Requirements

- Python 3.11+
- Tesseract OCR for image extraction

On macOS, install Tesseract with Homebrew:

```bash
brew install tesseract
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Run

```bash
.venv/bin/uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Test

```bash
.venv/bin/pytest -v
```

## Prototype Notes

- Uploaded labels are processed for the current request and are not stored.
- If Tesseract is unavailable, paste fixture or raw label text into the Raw extracted text override field.
- Government warning checks are strict.
- Brand checks tolerate capitalization and punctuation differences.
- Batch review, accounts, COLA integration, and long-term storage are out of scope.

## Manual Validation

Use the text fixtures in `tests/fixtures` with the matching expected fields:

- `label_compliant.txt` should return an overall pass.
- `label_bad_warning.txt` should return needs review with a government warning mismatch.

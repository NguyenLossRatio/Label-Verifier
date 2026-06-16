# Approach, Tools, And Assumptions

## Approach

Label Verifier separates the workflow into these steps:

1. Parse the uploaded liquor application JSON file.
2. Decode the embedded label image attachment.
3. Extract text from the label image.
4. Detect likely field values from the extracted text.
5. Compare detected values against expected application values and return field-level results.

The backend is a FastAPI app in `app/main.py`. The frontend in `app/static` posts one multipart `application_file` upload to `/api/verify` and renders the response.

## Text Extraction

Image OCR uses local Tesseract through `pytesseract`. The extractor resizes decoded label attachment images so the longest side is at most `1600px`, prepares multiple image variants, applies a runtime budget, and performs targeted OCR passes for difficult cases such as:

- rotated or sideways government warning text
- field-region crops
- noisy address areas

The app also supports optional EasyOCR through the `strong-ocr` extra and environment flags, but Tesseract-only OCR is the default path because it starts faster for local review.

## Field Detection

Field extraction is heuristic and field-specific:

- Regular expressions detect alcohol content, net contents, country of origin, class/type, and producer/address patterns.
- Brand extraction ranks likely brand candidates and rejects common OCR artifacts such as city/state lines, serving instructions, weak suffix fragments, and low-signal OCR debris.
- Bottler/producer address extraction combines explicit bottled/produced/distilled lines, brewed-and-canned patterns, postal addresses, and nearby city/state lines.
- Government warning extraction preserves OCR line breaks and tries to isolate the warning block without pulling unrelated label text into the extracted value.

The API returns both selected `field_guesses` and `field_candidates` with source and confidence metadata.

## Verification

Verification is handled in `app/verification.py`.

- Brand matching tolerates punctuation, capitalization, and `&` versus `and`.
- Net contents matching ignores capitalization, punctuation, whitespace, and line breaks.
- Country of origin is optional when no expected value is provided.
- Government warning comparison is intentionally strict. The expected warning is hardcoded in `app/constants.py`, is case-sensitive, and must match the required wording.

## Tools Used

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- Pillow
- Tesseract OCR
- pytesseract
- pytest
- Optional EasyOCR
- Railway deployment config through Railpack/Nixpacks

## Assumptions

- The app is a prototype for guided review, not an official TTB filing system.
- Embedded label attachments and extracted text are processed per request and are not persisted by the application.
- OCR output can be incomplete or noisy, so extraction confidence and status messages are meant to support human review.
- Government warning text is a fixed compliance requirement for this workflow and should not be user-editable.
- Expected field values come from the uploaded application JSON, not manual form inputs.
- Runtime should stay reasonably fast for local use, so the default OCR path favors Tesseract and targeted fallback passes over heavier OCR models.

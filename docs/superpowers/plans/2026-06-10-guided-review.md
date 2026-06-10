# Guided Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone guided-review web application where an agent uploads one alcohol label, enters expected application fields, runs verification, and receives clear field-by-field results.

**Architecture:** Use a compact FastAPI application that serves static frontend assets and exposes JSON APIs for health checks and label verification. OCR is isolated behind `app/extraction.py`; verification rules are deterministic and tested in `app/verification.py`; the first UI is a single-page guided review experience.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pillow, pytesseract, pytest, FastAPI TestClient, vanilla HTML/CSS/JavaScript.

---

## File Structure

- Create: `pyproject.toml` - Python package metadata, runtime dependencies, test dependencies, pytest config.
- Create: `README.md` - setup, run, test, and OCR notes.
- Create: `.gitignore` - local Python, test, and temporary file ignores.
- Create: `app/__init__.py` - package marker.
- Create: `app/main.py` - FastAPI app, static asset serving, health endpoint, verification endpoint.
- Create: `app/models.py` - Pydantic request/response models and status enums.
- Create: `app/extraction.py` - OCR adapter and structured text extraction helpers.
- Create: `app/verification.py` - deterministic field comparison and report generation.
- Create: `app/static/index.html` - guided review screen.
- Create: `app/static/styles.css` - restrained, readable agent-facing styling.
- Create: `app/static/app.js` - upload preview, form submission, result rendering.
- Create: `tests/test_health.py` - app health smoke test.
- Create: `tests/test_verification.py` - verification rule tests.
- Create: `tests/test_extraction.py` - raw text field-guess tests.
- Create: `tests/test_api.py` - verification API tests.
- Create: `tests/test_static_assets.py` - UI asset smoke tests.
- Create: `tests/fixtures/label_compliant.txt` - extracted text fixture for a passing label.
- Create: `tests/fixtures/label_bad_warning.txt` - extracted text fixture for warning failure.

## Implementation Tasks

### Task 1: Project Skeleton And Health Endpoint

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write the failing health test**

```python
# tests/test_health.py
from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_health.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Add project dependencies and FastAPI skeleton**

```toml
# pyproject.toml
[project]
name = "label-verifier"
version = "0.1.0"
description = "Guided alcohol label verification prototype"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "python-multipart>=0.0.9",
  "pillow>=10.4.0",
  "pytesseract>=0.3.13"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "httpx>=0.27.0"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

```text
# .gitignore
.venv/
__pycache__/
.pytest_cache/
*.pyc
.DS_Store
.superpowers/
```

```python
# app/__init__.py
```

```python
# app/main.py
from fastapi import FastAPI

app = FastAPI(title="Label Verifier")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Create the virtual environment**

Run: `python3 -m venv .venv`

Expected: `.venv/bin/python` exists.

- [ ] **Step 5: Install dependencies**

Run: `.venv/bin/python -m pip install -e ".[dev]"`

Expected: dependencies install successfully.

- [ ] **Step 6: Run the test to verify it passes**

Run: `pytest tests/test_health.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore app/__init__.py app/main.py tests/test_health.py
git commit -m "chore: add FastAPI project skeleton"
```

### Task 2: Verification Models And Core Field Rules

**Files:**
- Create: `app/models.py`
- Create: `app/verification.py`
- Create: `tests/test_verification.py`

- [ ] **Step 1: Write failing tests for tolerant and strict comparisons**

```python
# tests/test_verification.py
from app.models import ExpectedFields
from app.verification import normalize_text, verify_label_text


STANDARD_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women "
    "should not drink alcoholic beverages during pregnancy because of the "
    "risk of birth defects. (2) Consumption of alcoholic beverages impairs "
    "your ability to drive a car or operate machinery, and may cause health problems."
)


def expected_fields(**overrides):
    values = {
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "bottler_address": "Old Tom Distillery, Louisville, KY",
        "country_of_origin": "",
        "government_warning": STANDARD_WARNING,
    }
    values.update(overrides)
    return ExpectedFields(**values)


def test_normalize_text_removes_case_and_punctuation_noise():
    assert normalize_text("STONE'S THROW") == normalize_text("Stones Throw")


def test_brand_name_allows_capitalization_and_punctuation_differences():
    report = verify_label_text(
        expected_fields(brand_name="STONE'S THROW"),
        "Brand: Stones Throw\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)\n750 ml\nOld Tom Distillery, Louisville, KY\n" + STANDARD_WARNING,
    )

    brand = report.field_results["brand_name"]
    assert brand.status == "pass"
    assert report.overall_status == "pass"


def test_abv_mismatch_is_flagged():
    report = verify_label_text(
        expected_fields(alcohol_content="45% Alc./Vol. (90 Proof)"),
        "OLD TOM DISTILLERY\n40% Alc./Vol. (80 Proof)\n750 mL\n" + STANDARD_WARNING,
    )

    alcohol = report.field_results["alcohol_content"]
    assert alcohol.status == "mismatch"
    assert "Expected alcohol content was not found" in alcohol.message
    assert report.overall_status == "needs_review"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_verification.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Implement models and core verification**

```python
# app/models.py
from typing import Literal

from pydantic import BaseModel

FieldStatus = Literal["pass", "mismatch", "missing", "needs_review", "unreadable"]
OverallStatus = Literal["pass", "needs_review", "unreadable"]


class ExpectedFields(BaseModel):
    brand_name: str
    class_type: str
    alcohol_content: str
    net_contents: str
    bottler_address: str
    country_of_origin: str = ""
    government_warning: str


class FieldResult(BaseModel):
    field: str
    label: str
    expected: str
    extracted: str
    status: FieldStatus
    message: str


class VerificationReport(BaseModel):
    overall_status: OverallStatus
    field_results: dict[str, FieldResult]
    raw_text: str
    processing_ms: int
```

```python
# app/verification.py
import re
import string
import time

from app.models import ExpectedFields, FieldResult, VerificationReport


FIELD_LABELS = {
    "brand_name": "Brand name",
    "class_type": "Class/type",
    "alcohol_content": "Alcohol content",
    "net_contents": "Net contents",
    "bottler_address": "Bottler/producer address",
    "country_of_origin": "Country of origin",
    "government_warning": "Government warning",
}


def normalize_text(value: str) -> str:
    lowered = value.lower()
    no_punctuation = lowered.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", no_punctuation).strip()


def _contains_tolerant(raw_text: str, expected: str) -> bool:
    if not expected.strip():
        return True
    return normalize_text(expected) in normalize_text(raw_text)


def _contains_strictish(raw_text: str, expected: str) -> bool:
    if not expected.strip():
        return True
    return normalize_text(expected) in normalize_text(raw_text)


def _result(field: str, expected: str, extracted: str, status: str, message: str) -> FieldResult:
    return FieldResult(
        field=field,
        label=FIELD_LABELS[field],
        expected=expected,
        extracted=extracted,
        status=status,
        message=message,
    )


def verify_label_text(expected: ExpectedFields, raw_text: str) -> VerificationReport:
    started = time.perf_counter()
    field_results: dict[str, FieldResult] = {}

    field_results["brand_name"] = _result(
        "brand_name",
        expected.brand_name,
        expected.brand_name if _contains_tolerant(raw_text, expected.brand_name) else "",
        "pass" if _contains_tolerant(raw_text, expected.brand_name) else "mismatch",
        "Brand name matched with tolerant comparison."
        if _contains_tolerant(raw_text, expected.brand_name)
        else "Expected brand name was not found.",
    )

    for field, value in {
        "class_type": expected.class_type,
        "alcohol_content": expected.alcohol_content,
        "net_contents": expected.net_contents,
        "bottler_address": expected.bottler_address,
        "country_of_origin": expected.country_of_origin,
    }.items():
        matched = _contains_strictish(raw_text, value)
        field_results[field] = _result(
            field,
            value,
            value if matched else "",
            "pass" if matched else "mismatch",
            f"{FIELD_LABELS[field]} matched." if matched else f"Expected {FIELD_LABELS[field].lower()} was not found.",
        )

    warning_matched = _contains_strictish(raw_text, expected.government_warning)
    field_results["government_warning"] = _result(
        "government_warning",
        expected.government_warning,
        expected.government_warning if warning_matched else "",
        "pass" if warning_matched else "mismatch",
        "Government warning matched." if warning_matched else "Expected government warning was not found.",
    )

    overall_status = "pass"
    if any(result.status != "pass" for result in field_results.values()):
        overall_status = "needs_review"

    return VerificationReport(
        overall_status=overall_status,
        field_results=field_results,
        raw_text=raw_text,
        processing_ms=round((time.perf_counter() - started) * 1000),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_verification.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models.py app/verification.py tests/test_verification.py
git commit -m "feat: add core label verification rules"
```

### Task 3: Strict Government Warning Rules

**Files:**
- Modify: `app/verification.py`
- Modify: `tests/test_verification.py`

- [ ] **Step 1: Add failing warning capitalization tests**

Append to `tests/test_verification.py`:

```python

def test_government_warning_requires_uppercase_prefix():
    bad_warning = STANDARD_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")

    report = verify_label_text(expected_fields(), "OLD TOM DISTILLERY\n" + bad_warning)

    warning = report.field_results["government_warning"]
    assert warning.status == "mismatch"
    assert "must use uppercase GOVERNMENT WARNING:" in warning.message
    assert report.overall_status == "needs_review"


def test_missing_government_warning_is_missing():
    report = verify_label_text(expected_fields(), "OLD TOM DISTILLERY\n750 mL\n45% Alc./Vol. (90 Proof)")

    warning = report.field_results["government_warning"]
    assert warning.status == "missing"
    assert warning.message == "Government warning statement was not found."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_verification.py::test_government_warning_requires_uppercase_prefix tests/test_verification.py::test_missing_government_warning_is_missing -v`

Expected: FAIL because warning-specific statuses are not implemented.

- [ ] **Step 3: Add warning verification helper**

Replace the government warning block in `app/verification.py` with this helper and call:

```python
def _verify_government_warning(expected_warning: str, raw_text: str) -> FieldResult:
    normalized_raw = normalize_text(raw_text)
    normalized_warning = normalize_text(expected_warning)

    if "government warning" not in normalized_raw:
        return _result(
            "government_warning",
            expected_warning,
            "",
            "missing",
            "Government warning statement was not found.",
        )

    if "GOVERNMENT WARNING:" not in raw_text:
        return _result(
            "government_warning",
            expected_warning,
            "Government warning",
            "mismatch",
            "Government warning must use uppercase GOVERNMENT WARNING: prefix.",
        )

    matched = normalized_warning in normalized_raw
    return _result(
        "government_warning",
        expected_warning,
        expected_warning if matched else "GOVERNMENT WARNING:",
        "pass" if matched else "mismatch",
        "Government warning matched." if matched else "Government warning wording did not match the expected statement.",
    )
```

In `verify_label_text`, replace the existing `warning_matched` block with:

```python
    field_results["government_warning"] = _verify_government_warning(expected.government_warning, raw_text)
```

- [ ] **Step 4: Run all verification tests**

Run: `pytest tests/test_verification.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/verification.py tests/test_verification.py
git commit -m "feat: enforce strict government warning checks"
```

### Task 4: OCR Extraction Adapter And Field Guesses

**Files:**
- Create: `app/extraction.py`
- Create: `tests/test_extraction.py`

- [ ] **Step 1: Write failing extraction tests**

```python
# tests/test_extraction.py
from app.extraction import extract_field_guesses


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_extraction.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction'`.

- [ ] **Step 3: Implement OCR adapter and field guesses**

```python
# app/extraction.py
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
        raise ExtractionError("OCR engine is not installed. Install Tesseract or use raw text override.") from exc

    cleaned = raw_text.strip()
    if not cleaned:
        raise ExtractionError("No readable text was found in the image.")

    return cleaned, round((time.perf_counter() - started) * 1000)


def extract_field_guesses(raw_text: str) -> dict[str, str]:
    alcohol_match = re.search(r"\b\d{1,2}(?:\.\d+)?\s*%\s*Alc\.?/Vol\.?(?:\s*\(\d{1,3}\s*Proof\))?", raw_text, re.IGNORECASE)
    net_match = re.search(r"\b\d+(?:\.\d+)?\s*(?:mL|ml|L|l)\b", raw_text)
    bottler_match = re.search(r"^.*\b(?:Bottled by|Produced by|Distilled by)\b.*$", raw_text, re.IGNORECASE | re.MULTILINE)

    return {
        "alcohol_content": alcohol_match.group(0).strip() if alcohol_match else "",
        "net_contents": net_match.group(0).strip() if net_match else "",
        "bottler_address": bottler_match.group(0).strip() if bottler_match else "",
    }
```

- [ ] **Step 4: Run extraction tests**

Run: `pytest tests/test_extraction.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/extraction.py tests/test_extraction.py
git commit -m "feat: add OCR extraction adapter"
```

### Task 5: Verification API Endpoint

**Files:**
- Modify: `app/main.py`
- Modify: `app/models.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_api.py
from fastapi.testclient import TestClient

from app.main import app
from tests.test_verification import STANDARD_WARNING


def test_verify_endpoint_accepts_raw_text_override():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        data={
            "brand_name": "OLD TOM DISTILLERY",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "45% Alc./Vol. (90 Proof)",
            "net_contents": "750 mL",
            "bottler_address": "Old Tom Distillery, Louisville, KY",
            "country_of_origin": "",
            "government_warning": STANDARD_WARNING,
            "raw_text_override": "OLD TOM DISTILLERY\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)\n750 mL\nOld Tom Distillery, Louisville, KY\n" + STANDARD_WARNING,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "pass"
    assert body["field_results"]["brand_name"]["status"] == "pass"


def test_verify_endpoint_requires_image_or_raw_text():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        data={
            "brand_name": "OLD TOM DISTILLERY",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "45% Alc./Vol. (90 Proof)",
            "net_contents": "750 mL",
            "bottler_address": "Old Tom Distillery, Louisville, KY",
            "country_of_origin": "",
            "government_warning": STANDARD_WARNING,
            "raw_text_override": "",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Upload a label image or provide raw extracted text."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -v`

Expected: FAIL because `/api/verify` does not exist.

- [ ] **Step 3: Add API request support**

Append to `app/models.py`:

```python

class VerifyResponse(VerificationReport):
    extraction_ms: int
    field_guesses: dict[str, str]
```

Replace `app/main.py` with:

```python
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.extraction import ExtractionError, extract_field_guesses, extract_text_from_image
from app.models import ExpectedFields, VerifyResponse
from app.verification import verify_label_text

app = FastAPI(title="Label Verifier")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/verify", response_model=VerifyResponse)
async def verify(
    brand_name: Annotated[str, Form()],
    class_type: Annotated[str, Form()],
    alcohol_content: Annotated[str, Form()],
    net_contents: Annotated[str, Form()],
    bottler_address: Annotated[str, Form()],
    country_of_origin: Annotated[str, Form()] = "",
    government_warning: Annotated[str, Form()] = "",
    raw_text_override: Annotated[str, Form()] = "",
    label_image: UploadFile | None = File(default=None),
) -> VerifyResponse:
    expected = ExpectedFields(
        brand_name=brand_name,
        class_type=class_type,
        alcohol_content=alcohol_content,
        net_contents=net_contents,
        bottler_address=bottler_address,
        country_of_origin=country_of_origin,
        government_warning=government_warning,
    )

    extraction_ms = 0
    raw_text = raw_text_override.strip()
    if not raw_text and label_image is not None and label_image.filename:
        if label_image.content_type and not label_image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Unsupported file type. Upload an image file.")
        try:
            raw_text, extraction_ms = extract_text_from_image(await label_image.read())
        except ExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not raw_text:
        raise HTTPException(status_code=400, detail="Upload a label image or provide raw extracted text.")

    report = verify_label_text(expected, raw_text)
    return VerifyResponse(
        **report.model_dump(),
        extraction_ms=extraction_ms,
        field_guesses=extract_field_guesses(raw_text),
    )
```

- [ ] **Step 4: Run API tests**

Run: `pytest tests/test_api.py -v`

Expected: PASS.

- [ ] **Step 5: Run full backend test suite**

Run: `pytest tests/test_health.py tests/test_verification.py tests/test_extraction.py tests/test_api.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/models.py tests/test_api.py
git commit -m "feat: add label verification API"
```

### Task 6: Guided Review Frontend

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/styles.css`
- Create: `app/static/app.js`
- Create: `tests/test_static_assets.py`

- [ ] **Step 1: Write failing static asset smoke tests**

```python
# tests/test_static_assets.py
from pathlib import Path


def test_guided_review_html_has_required_controls():
    html = Path("app/static/index.html").read_text()

    assert 'id="labelImage"' in html
    assert 'id="expectedFields"' in html
    assert 'id="verifyButton"' in html
    assert 'id="results"' in html
    assert 'id="rawTextOverride"' in html


def test_frontend_javascript_calls_verify_endpoint():
    javascript = Path("app/static/app.js").read_text()

    assert 'fetch("/api/verify"' in javascript
    assert "renderResults" in javascript
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_static_assets.py -v`

Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 3: Add the guided review HTML**

```html
<!-- app/static/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Label Verifier</title>
    <link rel="stylesheet" href="/static/styles.css">
  </head>
  <body>
    <header class="app-header">
      <div>
        <h1>Label Verifier</h1>
        <p>Guided alcohol label review</p>
      </div>
      <output id="status" aria-live="polite">Ready</output>
    </header>

    <main class="review-layout">
      <section class="panel upload-panel" aria-labelledby="uploadHeading">
        <h2 id="uploadHeading">Label Image</h2>
        <label class="drop-zone" for="labelImage">
          <span>Upload label image</span>
          <small>PNG, JPG, or TIFF</small>
        </label>
        <input id="labelImage" name="label_image" type="file" accept="image/*">
        <img id="preview" alt="Uploaded label preview">
        <label for="rawTextOverride">Raw extracted text</label>
        <textarea id="rawTextOverride" name="raw_text_override" rows="8" placeholder="Optional: paste OCR text here when Tesseract is unavailable."></textarea>
      </section>

      <section class="panel" aria-labelledby="fieldsHeading">
        <h2 id="fieldsHeading">Expected Application Fields</h2>
        <form id="expectedFields">
          <label>Brand name <input name="brand_name" value="OLD TOM DISTILLERY" required></label>
          <label>Class/type <input name="class_type" value="Kentucky Straight Bourbon Whiskey" required></label>
          <label>Alcohol content <input name="alcohol_content" value="45% Alc./Vol. (90 Proof)" required></label>
          <label>Net contents <input name="net_contents" value="750 mL" required></label>
          <label>Bottler/producer address <input name="bottler_address" value="Old Tom Distillery, Louisville, KY" required></label>
          <label>Country of origin <input name="country_of_origin" value=""></label>
          <label>Government warning <textarea name="government_warning" rows="5" required>GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.</textarea></label>
          <button id="verifyButton" type="submit">Verify Label</button>
        </form>
      </section>

      <section class="panel results-panel" aria-labelledby="resultsHeading">
        <h2 id="resultsHeading">Verification Results</h2>
        <div id="results" class="empty-state">Run verification to see field-by-field results.</div>
      </section>
    </main>

    <script src="/static/app.js"></script>
  </body>
</html>
```

- [ ] **Step 4: Add styling**

```css
/* app/static/styles.css */
:root {
  color-scheme: light;
  --bg: #f5f7f8;
  --panel: #ffffff;
  --ink: #1f2933;
  --muted: #667085;
  --line: #d9e0e6;
  --action: #1b6b6f;
  --pass: #1f7a4d;
  --warn: #a05a00;
  --bad: #b42318;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Arial, Helvetica, sans-serif;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 28px;
  background: #ffffff;
  border-bottom: 1px solid var(--line);
}

.app-header h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: 0;
}

.app-header p {
  margin: 4px 0 0;
  color: var(--muted);
}

#status {
  min-width: 110px;
  text-align: right;
  font-weight: 700;
}

.review-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(320px, 1fr) minmax(320px, 1.1fr);
  gap: 16px;
  padding: 16px;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  min-width: 0;
}

.panel h2 {
  margin: 0 0 14px;
  font-size: 18px;
}

label {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
  font-weight: 700;
}

input,
textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px;
  font: inherit;
}

textarea {
  resize: vertical;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 118px;
  border: 2px dashed var(--line);
  border-radius: 8px;
  color: var(--muted);
  cursor: pointer;
}

#labelImage {
  margin-bottom: 12px;
}

#preview {
  display: none;
  width: 100%;
  max-height: 320px;
  object-fit: contain;
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-bottom: 12px;
  background: #fafafa;
}

button {
  width: 100%;
  min-height: 44px;
  border: 0;
  border-radius: 6px;
  background: var(--action);
  color: #ffffff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

button:disabled {
  opacity: 0.65;
  cursor: progress;
}

.overall {
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  font-weight: 700;
}

.overall.pass {
  background: #e8f5ee;
  color: var(--pass);
}

.overall.needs_review,
.overall.unreadable {
  background: #fff4e5;
  color: var(--warn);
}

.result-row {
  border-top: 1px solid var(--line);
  padding: 12px 0;
}

.result-row strong {
  display: block;
  margin-bottom: 4px;
}

.status {
  display: inline-block;
  border-radius: 999px;
  padding: 3px 9px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.status.pass {
  background: #e8f5ee;
  color: var(--pass);
}

.status.mismatch,
.status.missing {
  background: #fdecec;
  color: var(--bad);
}

.status.needs_review,
.status.unreadable {
  background: #fff4e5;
  color: var(--warn);
}

.empty-state {
  color: var(--muted);
}

details {
  margin-top: 12px;
}

pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: #f2f4f7;
  border-radius: 6px;
  padding: 10px;
}

@media (max-width: 1000px) {
  .review-layout {
    grid-template-columns: 1fr;
  }

  .app-header {
    align-items: flex-start;
    flex-direction: column;
  }

  #status {
    text-align: left;
  }
}
```

- [ ] **Step 5: Add frontend behavior**

```javascript
// app/static/app.js
const form = document.querySelector("#expectedFields");
const fileInput = document.querySelector("#labelImage");
const preview = document.querySelector("#preview");
const statusOutput = document.querySelector("#status");
const results = document.querySelector("#results");
const verifyButton = document.querySelector("#verifyButton");

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) {
    preview.style.display = "none";
    preview.removeAttribute("src");
    return;
  }
  preview.src = URL.createObjectURL(file);
  preview.style.display = "block";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusOutput.textContent = "Verifying";
  verifyButton.disabled = true;
  results.textContent = "Processing label...";

  const body = new FormData(form);
  const file = fileInput.files[0];
  if (file) {
    body.append("label_image", file);
  }
  body.append("raw_text_override", document.querySelector("#rawTextOverride").value);

  try {
    const response = await fetch("/api/verify", { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Verification failed.");
    }
    renderResults(payload);
    statusOutput.textContent = payload.overall_status === "pass" ? "Pass" : "Needs review";
  } catch (error) {
    results.innerHTML = `<div class="overall unreadable">${escapeHtml(error.message)}</div>`;
    statusOutput.textContent = "Needs review";
  } finally {
    verifyButton.disabled = false;
  }
});

function renderResults(report) {
  const rows = Object.values(report.field_results)
    .map((field) => `
      <div class="result-row">
        <strong>${escapeHtml(field.label)}</strong>
        <span class="status ${field.status}">${escapeHtml(field.status.replace("_", " "))}</span>
        <p>${escapeHtml(field.message)}</p>
        <small><b>Expected:</b> ${escapeHtml(field.expected || "Not provided")}</small><br>
        <small><b>Extracted:</b> ${escapeHtml(field.extracted || "Not found")}</small>
      </div>
    `)
    .join("");

  results.innerHTML = `
    <div class="overall ${report.overall_status}">
      Overall: ${escapeHtml(report.overall_status.replace("_", " "))}
      (${report.processing_ms + report.extraction_ms} ms)
    </div>
    ${rows}
    <details>
      <summary>Raw extracted text</summary>
      <pre>${escapeHtml(report.raw_text)}</pre>
    </details>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
```

- [ ] **Step 6: Run static asset tests**

Run: `pytest tests/test_static_assets.py -v`

Expected: PASS.

- [ ] **Step 7: Run API and static tests together**

Run: `pytest tests/test_api.py tests/test_static_assets.py -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app/static/index.html app/static/styles.css app/static/app.js tests/test_static_assets.py
git commit -m "feat: add guided review web interface"
```

### Task 7: Fixtures, Documentation, And Manual Run Path

**Files:**
- Create: `tests/fixtures/label_compliant.txt`
- Create: `tests/fixtures/label_bad_warning.txt`
- Create: `README.md`

- [ ] **Step 1: Add text fixtures**

```text
# tests/fixtures/label_compliant.txt
OLD TOM DISTILLERY
Kentucky Straight Bourbon Whiskey
45% Alc./Vol. (90 Proof)
750 mL
Old Tom Distillery, Louisville, KY
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
```

```text
# tests/fixtures/label_bad_warning.txt
OLD TOM DISTILLERY
Kentucky Straight Bourbon Whiskey
45% Alc./Vol. (90 Proof)
750 mL
Old Tom Distillery, Louisville, KY
Government Warning: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
```

- [ ] **Step 2: Add README**

```markdown
# Label Verifier

Guided alcohol label verification prototype for comparing expected application fields against label text.

## Requirements

- Python 3.11+
- Tesseract OCR for image extraction

On macOS, install Tesseract with:

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
pytest -v
```

## Prototype Notes

- Uploaded labels are processed for the current request and are not stored.
- If Tesseract is not installed, paste extracted label text into the `Raw extracted text` field to exercise the verification workflow.
- Government warning checks are intentionally strict.
- Brand name checks tolerate capitalization and punctuation differences.
- Batch review, user accounts, COLA integration, and long-term storage are outside this first guided-review version.
```

- [ ] **Step 3: Run all tests**

Run: `pytest -v`

Expected: PASS.

- [ ] **Step 4: Start the app**

Run: `.venv/bin/uvicorn app.main:app --reload`

Expected: server starts and reports it is running on `http://127.0.0.1:8000`.

- [ ] **Step 5: Manual verification using fixture text**

Open `http://127.0.0.1:8000`, paste `tests/fixtures/label_compliant.txt` into `Raw extracted text`, click `Verify Label`, and confirm:

```text
Overall: pass
Brand name: pass
Government warning: pass
Alcohol content: pass
Net contents: pass
```

- [ ] **Step 6: Manual warning failure check**

Paste `tests/fixtures/label_bad_warning.txt` into `Raw extracted text`, click `Verify Label`, and confirm:

```text
Overall: needs review
Government warning: mismatch
Government warning must use uppercase GOVERNMENT WARNING: prefix.
```

- [ ] **Step 7: Commit**

```bash
git add README.md tests/fixtures/label_compliant.txt tests/fixtures/label_bad_warning.txt
git commit -m "docs: add run instructions and label fixtures"
```

### Task 8: Final Verification And Handoff

**Files:**
- Review: all created files

- [ ] **Step 1: Run the full automated test suite**

Run: `pytest -v`

Expected: PASS for all tests.

- [ ] **Step 2: Check git status**

Run: `git status --short`

Expected: no modified tracked files after commits. Untracked local environment files such as `.venv/` should not appear because `.gitignore` covers them.

- [ ] **Step 3: Run the application for user validation**

Run: `.venv/bin/uvicorn app.main:app --reload`

Expected: the app is available at `http://127.0.0.1:8000`.

- [ ] **Step 4: Browser smoke test**

Open `http://127.0.0.1:8000` and verify:

```text
The page shows Label Verifier.
The upload control is visible.
The expected field form is visible.
The Verify Label button is visible.
The results panel starts empty.
Pasting compliant fixture text and clicking Verify Label returns Overall: pass.
```

- [ ] **Step 5: Commit any final documentation corrections**

If Step 4 reveals a documentation mismatch, update `README.md` with the exact corrected instruction, then run:

```bash
git add README.md
git commit -m "docs: clarify validation instructions"
```

If Step 4 reveals no documentation mismatch, do not create an empty commit.

## Self-Review

- Spec coverage: This plan covers single image upload, image preview, manual expected fields, OCR adapter, raw text fallback, deterministic verification, strict government warning checks, tolerant brand matching, clear results, basic error handling, no persistence, README setup, and validation fixtures.
- Scope alignment: Batch uploads, queue management, dashboards, authentication, COLA integration, long-term storage, and production compliance controls are intentionally excluded from this first guided-review implementation.
- Type consistency: `ExpectedFields`, `FieldResult`, `VerificationReport`, and `VerifyResponse` are defined before use. Status values are consistent across backend, tests, and frontend CSS.
- Execution risk: Real OCR depends on the local Tesseract binary. The raw text override keeps the guided-review workflow testable when OCR is unavailable.

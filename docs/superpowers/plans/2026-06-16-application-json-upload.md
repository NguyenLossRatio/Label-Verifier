# Application JSON Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manual expected-field entry with a single liquor application JSON upload that provides both standardized application fields and an embedded base64 label image.

**Architecture:** Add a small application-upload parsing boundary that turns JSON bytes into existing `ExpectedFields` plus label image bytes. Keep OCR and verification internals stable, change `/api/verify` to accept `application_file`, and update the static UI to preview read-only application fields from the JSON file before posting it.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, Pillow, pytesseract, pytest, FastAPI TestClient, vanilla HTML/CSS/JavaScript.

---

## File Structure

- Create: `app/application_upload.py` - parse and validate standardized liquor application JSON files, decode embedded label attachments, and produce `ExpectedFields`.
- Create: `tests/test_application_upload.py` - unit tests for the JSON parser and attachment validation errors.
- Modify: `app/main.py` - change `/api/verify` from manual form fields plus `label_image` to one required `application_file`.
- Modify: `tests/test_api.py` - replace manual-form API tests with JSON application upload API tests.
- Modify: `app/static/index.html` - replace label image upload plus editable expected inputs with one JSON application upload plus read-only application field preview.
- Modify: `app/static/app.js` - parse selected JSON for preview, submit `application_file`, and keep existing result rendering.
- Modify: `app/static/styles.css` - style read-only application preview fields and update file input selectors.
- Modify: `tests/test_static_assets.py` - assert the new UI contract and removal of manual expected-field inputs.
- Modify: `README.md` - document the JSON application upload format and revised curl example.
- Modify: `docs/approach.md` - update the workflow assumptions from manual fields to application-sourced fields.

## Implementation Tasks

### Task 1: Application JSON Parser

**Files:**
- Create: `app/application_upload.py`
- Create: `tests/test_application_upload.py`

- [ ] **Step 1: Write parser tests**

Create `tests/test_application_upload.py`:

```python
import base64
import json

import pytest

from app.application_upload import ApplicationUploadError, parse_application_upload
from app.constants import REQUIRED_GOVERNMENT_WARNING


LABEL_BYTES = b"fake image bytes"


def application_payload(**overrides):
    values = {
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "bottler_address": "Old Tom Distillery, Louisville, KY",
        "country_of_origin": "",
        "label_attachment": {
            "filename": "label.png",
            "content_type": "image/png",
            "data": base64.b64encode(LABEL_BYTES).decode("ascii"),
        },
    }
    values.update(overrides)
    return values


def encode_application(payload):
    return json.dumps(payload).encode("utf-8")


def test_parse_application_upload_returns_expected_fields_and_label_bytes():
    parsed = parse_application_upload(encode_application(application_payload()))

    assert parsed.expected_fields.brand_name == "OLD TOM DISTILLERY"
    assert parsed.expected_fields.class_type == "Kentucky Straight Bourbon Whiskey"
    assert parsed.expected_fields.alcohol_content == "45% Alc./Vol. (90 Proof)"
    assert parsed.expected_fields.net_contents == "750 mL"
    assert parsed.expected_fields.bottler_address == "Old Tom Distillery, Louisville, KY"
    assert parsed.expected_fields.country_of_origin == ""
    assert parsed.expected_fields.government_warning == REQUIRED_GOVERNMENT_WARNING
    assert parsed.label_bytes == LABEL_BYTES
    assert parsed.label_filename == "label.png"
    assert parsed.label_content_type == "image/png"


def test_parse_application_upload_defaults_country_of_origin_to_blank():
    payload = application_payload()
    payload.pop("country_of_origin")

    parsed = parse_application_upload(encode_application(payload))

    assert parsed.expected_fields.country_of_origin == ""


def test_parse_application_upload_ignores_government_warning_from_json():
    parsed = parse_application_upload(
        encode_application(application_payload(government_warning="WRONG WARNING"))
    )

    assert parsed.expected_fields.government_warning == REQUIRED_GOVERNMENT_WARNING


def test_parse_application_upload_rejects_invalid_json():
    with pytest.raises(ApplicationUploadError, match="Application file is not valid JSON."):
        parse_application_upload(b"{")


def test_parse_application_upload_rejects_non_object_json():
    with pytest.raises(ApplicationUploadError, match="Application file is not valid JSON."):
        parse_application_upload(b"[]")


def test_parse_application_upload_rejects_missing_required_field():
    payload = application_payload()
    payload.pop("brand_name")

    with pytest.raises(ApplicationUploadError, match="Application is missing required field: brand_name."):
        parse_application_upload(encode_application(payload))


def test_parse_application_upload_rejects_blank_required_field():
    payload = application_payload(brand_name="  ")

    with pytest.raises(ApplicationUploadError, match="Application is missing required field: brand_name."):
        parse_application_upload(encode_application(payload))


def test_parse_application_upload_rejects_missing_label_attachment():
    payload = application_payload()
    payload.pop("label_attachment")

    with pytest.raises(ApplicationUploadError, match="Application is missing label_attachment."):
        parse_application_upload(encode_application(payload))


def test_parse_application_upload_rejects_invalid_base64_attachment_data():
    payload = application_payload(
        label_attachment={
            "filename": "label.png",
            "content_type": "image/png",
            "data": "not base64",
        }
    )

    with pytest.raises(ApplicationUploadError, match="Label attachment data must be base64-encoded image bytes."):
        parse_application_upload(encode_application(payload))


def test_parse_application_upload_rejects_non_image_attachment_type():
    payload = application_payload(
        label_attachment={
            "filename": "label.txt",
            "content_type": "text/plain",
            "data": base64.b64encode(LABEL_BYTES).decode("ascii"),
        }
    )

    with pytest.raises(ApplicationUploadError, match="Unsupported label attachment type. Include an image attachment."):
        parse_application_upload(encode_application(payload))
```

- [ ] **Step 2: Run parser tests and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_application_upload.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.application_upload'`.

- [ ] **Step 3: Implement the parser**

Create `app/application_upload.py`:

```python
import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models import ExpectedFields


class ApplicationUploadError(Exception):
    pass


class LabelAttachment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str
    content_type: str
    data: str


class LiquorApplication(BaseModel):
    model_config = ConfigDict(extra="ignore")

    brand_name: str
    class_type: str
    alcohol_content: str
    net_contents: str
    bottler_address: str
    country_of_origin: str = ""
    label_attachment: LabelAttachment


@dataclass(frozen=True)
class ParsedApplication:
    expected_fields: ExpectedFields
    label_bytes: bytes
    label_filename: str
    label_content_type: str


REQUIRED_TEXT_FIELDS = (
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_address",
)


def parse_application_upload(raw_json: bytes) -> ParsedApplication:
    payload = _load_json_object(raw_json)
    _validate_required_text_fields(payload)
    attachment_payload = _validate_attachment_payload(payload)
    application = LiquorApplication.model_validate(payload)
    label_bytes = _decode_label_bytes(attachment_payload["data"])

    return ParsedApplication(
        expected_fields=ExpectedFields(
            brand_name=application.brand_name,
            class_type=application.class_type,
            alcohol_content=application.alcohol_content,
            net_contents=application.net_contents,
            bottler_address=application.bottler_address,
            country_of_origin=application.country_of_origin,
        ),
        label_bytes=label_bytes,
        label_filename=application.label_attachment.filename,
        label_content_type=application.label_attachment.content_type,
    )


def _load_json_object(raw_json: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw_json.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApplicationUploadError("Application file is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ApplicationUploadError("Application file is not valid JSON.")

    return payload


def _validate_required_text_fields(payload: dict[str, Any]) -> None:
    for field_name in REQUIRED_TEXT_FIELDS:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ApplicationUploadError(f"Application is missing required field: {field_name}.")

    country = payload.get("country_of_origin", "")
    if country is not None and not isinstance(country, str):
        raise ApplicationUploadError("Application is missing required field: country_of_origin.")


def _validate_attachment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    attachment = payload.get("label_attachment")
    if not isinstance(attachment, dict):
        raise ApplicationUploadError("Application is missing label_attachment.")

    for field_name in ("filename", "content_type", "data"):
        value = attachment.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ApplicationUploadError("Application is missing label_attachment.")

    if not attachment["content_type"].lower().startswith("image/"):
        raise ApplicationUploadError("Unsupported label attachment type. Include an image attachment.")

    return attachment


def _decode_label_bytes(encoded_data: str) -> bytes:
    try:
        label_bytes = base64.b64decode(encoded_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApplicationUploadError("Label attachment data must be base64-encoded image bytes.") from exc

    if not label_bytes:
        raise ApplicationUploadError("Label attachment data must be base64-encoded image bytes.")

    return label_bytes
```

- [ ] **Step 4: Run parser tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/test_application_upload.py -v`

Expected: PASS for all tests in `tests/test_application_upload.py`.

- [ ] **Step 5: Commit parser boundary**

```bash
git add app/application_upload.py tests/test_application_upload.py
git commit -m "feat: parse application JSON uploads"
```

### Task 2: Verify API Contract

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Replace API tests with JSON application upload tests**

Replace `tests/test_api.py` with:

```python
import base64
import json

from fastapi.testclient import TestClient

from app.constants import REQUIRED_GOVERNMENT_WARNING
from app.extraction import ExtractionError
from app.main import app
from tests.test_verification import STANDARD_WARNING


LABEL_BYTES = b"fake image bytes"


def valid_application(**overrides):
    values = {
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "bottler_address": "Old Tom Distillery, Louisville, KY",
        "country_of_origin": "",
        "label_attachment": {
            "filename": "label.png",
            "content_type": "image/png",
            "data": base64.b64encode(LABEL_BYTES).decode("ascii"),
        },
    }
    values.update(overrides)
    return values


def application_file(payload=None, filename="application.json", content_type="application/json"):
    payload = valid_application() if payload is None else payload
    return {
        "application_file": (
            filename,
            json.dumps(payload).encode("utf-8"),
            content_type,
        )
    }


def test_verify_endpoint_accepts_application_json_upload(monkeypatch):
    client = TestClient(app)
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "Kentucky Straight Bourbon Whiskey\n"
        "45% Alc./Vol. (90 Proof)\n"
        "750 mL\n"
        "Bottled by Old Tom Distillery, Louisville, KY\n"
        + STANDARD_WARNING
    )

    def extract_text(image_data):
        assert image_data == LABEL_BYTES
        return raw_text, 123

    monkeypatch.setattr("app.main.extract_text_from_image", extract_text)

    response = client.post("/api/verify", files=application_file())

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "pass"
    assert body["field_results"]["brand_name"]["expected"] == "OLD TOM DISTILLERY"
    assert body["field_results"]["brand_name"]["status"] == "pass"
    assert body["extraction_ms"] == 123
    assert body["field_guesses"]["alcohol_content"] == "45% Alc./Vol. (90 Proof)"
    alcohol_candidates = body["field_candidates"]["alcohol_content"]
    assert alcohol_candidates[0]["value"] == "45% Alc./Vol. (90 Proof)"
    assert alcohol_candidates[0]["source"] == "alcohol_content_pattern"
    assert 0 < alcohol_candidates[0]["confidence"] <= 1


def test_verify_endpoint_uses_hardcoded_government_warning_when_json_field_is_present(monkeypatch):
    client = TestClient(app)
    payload = valid_application(government_warning="WRONG WARNING")
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "Kentucky Straight Bourbon Whiskey\n"
        "45% Alc./Vol. (90 Proof)\n"
        "750 mL\n"
        "Bottled by Old Tom Distillery, Louisville, KY\n"
        + REQUIRED_GOVERNMENT_WARNING
    )

    def extract_text(_image_data):
        return raw_text, 123

    monkeypatch.setattr("app.main.extract_text_from_image", extract_text)

    response = client.post("/api/verify", files=application_file(payload))

    assert response.status_code == 200
    warning = response.json()["field_results"]["government_warning"]
    assert warning["expected"] == REQUIRED_GOVERNMENT_WARNING
    assert warning["status"] == "pass"


def test_verify_endpoint_requires_application_upload():
    client = TestClient(app)

    response = client.post("/api/verify")

    assert response.status_code == 400
    assert response.json()["detail"] == "Upload a liquor application JSON file."


def test_verify_endpoint_rejects_non_json_upload():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={"application_file": ("application.txt", b"not json", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type. Upload a JSON application file."


def test_verify_endpoint_rejects_invalid_json():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={"application_file": ("application.json", b"{", "application/json")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Application file is not valid JSON."


def test_verify_endpoint_rejects_missing_required_field():
    client = TestClient(app)
    payload = valid_application()
    payload.pop("brand_name")

    response = client.post("/api/verify", files=application_file(payload))

    assert response.status_code == 400
    assert response.json()["detail"] == "Application is missing required field: brand_name."


def test_verify_endpoint_rejects_missing_label_attachment():
    client = TestClient(app)
    payload = valid_application()
    payload.pop("label_attachment")

    response = client.post("/api/verify", files=application_file(payload))

    assert response.status_code == 400
    assert response.json()["detail"] == "Application is missing label_attachment."


def test_verify_endpoint_rejects_invalid_base64_label_attachment():
    client = TestClient(app)
    payload = valid_application(
        label_attachment={
            "filename": "label.png",
            "content_type": "image/png",
            "data": "not base64",
        }
    )

    response = client.post("/api/verify", files=application_file(payload))

    assert response.status_code == 400
    assert response.json()["detail"] == "Label attachment data must be base64-encoded image bytes."


def test_verify_endpoint_rejects_non_image_label_attachment():
    client = TestClient(app)
    payload = valid_application(
        label_attachment={
            "filename": "label.txt",
            "content_type": "text/plain",
            "data": base64.b64encode(LABEL_BYTES).decode("ascii"),
        }
    )

    response = client.post("/api/verify", files=application_file(payload))

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported label attachment type. Include an image attachment."


def test_verify_endpoint_maps_extraction_errors_to_unprocessable_entity(monkeypatch):
    client = TestClient(app)

    def fail_extraction(_image_bytes):
        raise ExtractionError("No readable text was found in the image.")

    monkeypatch.setattr("app.main.extract_text_from_image", fail_extraction)

    response = client.post("/api/verify", files=application_file())

    assert response.status_code == 422
    assert response.json()["detail"] == "No readable text was found in the image."
```

- [ ] **Step 2: Run API tests and verify they fail on the old contract**

Run: `.venv/bin/python -m pytest tests/test_api.py -v`

Expected: FAIL because `/api/verify` still requires manual form fields and `label_image`.

- [ ] **Step 3: Update the API endpoint**

Replace `app/main.py` with:

```python
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.application_upload import ApplicationUploadError, parse_application_upload
from app.extraction import (
    ExtractionError,
    extract_field_candidates,
    extract_text_from_image,
    select_field_guesses,
)
from app.models import VerifyResponse
from app.verification import verify_label_text

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_PATH = STATIC_DIR / "index.html"
JSON_CONTENT_TYPES = {"application/json", "text/json"}

app = FastAPI(title="Label Verifier")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_PATH)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/verify", response_model=VerifyResponse)
async def verify(
    application_file: Annotated[UploadFile | None, File()] = None,
) -> VerifyResponse:
    if application_file is None:
        raise HTTPException(status_code=400, detail="Upload a liquor application JSON file.")

    if not _is_json_application_upload(application_file):
        raise HTTPException(status_code=400, detail="Unsupported file type. Upload a JSON application file.")

    try:
        parsed_application = parse_application_upload(await application_file.read())
    except ApplicationUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        raw_text, extraction_ms = extract_text_from_image(parsed_application.label_bytes)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    field_candidates = extract_field_candidates(raw_text)
    field_guesses = select_field_guesses(field_candidates)
    report = verify_label_text(
        parsed_application.expected_fields,
        raw_text,
        field_guesses=field_guesses,
    )
    return VerifyResponse(
        **report.model_dump(),
        extraction_ms=extraction_ms,
        field_guesses=field_guesses,
        field_candidates={
            field: [candidate.__dict__ for candidate in candidates]
            for field, candidates in field_candidates.items()
        },
    )


def _is_json_application_upload(upload: UploadFile) -> bool:
    filename = (upload.filename or "").lower()
    content_type = (upload.content_type or "").lower()
    return filename.endswith(".json") and content_type in JSON_CONTENT_TYPES
```

- [ ] **Step 4: Run parser and API tests**

Run: `.venv/bin/python -m pytest tests/test_application_upload.py tests/test_api.py -v`

Expected: PASS for parser and API tests.

- [ ] **Step 5: Commit API contract change**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: verify labels from application JSON"
```

### Task 3: Static UI Contract

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`
- Modify: `tests/test_static_assets.py`

- [ ] **Step 1: Replace static asset tests**

Replace `tests/test_static_assets.py` with:

```python
from pathlib import Path


def test_application_upload_html_has_required_controls():
    html = Path("app/static/index.html").read_text()

    assert 'id="applicationFile"' in html
    assert 'name="application_file"' in html
    assert 'id="applicationForm"' in html
    assert 'id="applicationFields"' in html
    assert 'id="verifyButton"' in html
    assert 'id="results"' in html
    assert 'id="rawTextOverride"' not in html


def test_application_upload_html_links_static_assets_and_removes_manual_expected_inputs():
    html = Path("app/static/index.html").read_text()

    assert 'href="/static/styles.css"' in html
    assert 'src="/static/app.js"' in html
    assert 'id="status"' in html
    assert 'name="label_image"' not in html

    for field_name in (
        "brand_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "bottler_address",
        "country_of_origin",
        "government_warning",
    ):
        assert f'name="{field_name}"' not in html

    assert "GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL," in html


def test_frontend_javascript_posts_application_file_to_verify_endpoint():
    javascript = Path("app/static/app.js").read_text()

    assert 'fetch("/api/verify"' in javascript
    assert 'body.append("application_file", file)' in javascript
    assert "renderApplicationFields" in javascript
    assert "field_guesses" in javascript
    assert "fieldGuesses" in javascript


def test_frontend_preserves_multiline_field_value_formatting():
    javascript = Path("app/static/app.js").read_text()
    stylesheet = Path("app/static/styles.css").read_text()

    assert "field-value" in javascript
    assert "white-space: pre-wrap" in stylesheet
```

- [ ] **Step 2: Run static tests and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_static_assets.py -v`

Expected: FAIL because the HTML and JavaScript still use `labelImage`, `expectedFields`, and manual expected inputs.

- [ ] **Step 3: Replace the HTML**

Replace `app/static/index.html` with:

```html
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
        <p>Guided review for alcohol label application files.</p>
      </div>
      <output id="status" class="status" aria-live="polite">Ready</output>
    </header>

    <main class="workspace">
      <section class="panel upload-panel" aria-labelledby="uploadTitle">
        <div class="panel-heading">
          <h2 id="uploadTitle">Application Source</h2>
          <p>Upload one liquor application JSON file with an embedded label attachment.</p>
        </div>

        <form id="applicationForm">
          <label class="drop-zone" for="applicationFile">
            <span class="drop-title">Choose application JSON</span>
            <span class="drop-copy">Standardized JSON with base64 label attachment</span>
            <input id="applicationFile" name="application_file" type="file" accept=".json,application/json">
          </label>

          <div class="preview-frame">
            <img id="preview" alt="Embedded label preview">
            <p id="previewPlaceholder">No application selected</p>
          </div>

          <button id="verifyButton" type="submit" disabled>Verify Label</button>
        </form>
      </section>

      <section class="panel review-panel" aria-labelledby="fieldsTitle">
        <div class="panel-heading">
          <h2 id="fieldsTitle">Application Fields</h2>
          <p>Expected values are populated from the uploaded application.</p>
        </div>

        <div id="applicationFields" class="application-fields" hidden></div>

        <div class="wide-field fixed-field">
          <span>Government warning</span>
          <pre>GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL,
WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES DURING
PREGNANCY BECAUSE OF THE RISK OF BIRTH DEFECTS. (2) CONSUMPTION
OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR
OR OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS.</pre>
        </div>
      </section>

      <section class="panel results-panel" aria-labelledby="resultsTitle">
        <div class="panel-heading">
          <h2 id="resultsTitle">Review Results</h2>
          <p>Field-by-field comparison appears after verification.</p>
        </div>
        <div id="results" aria-live="polite">
          <p class="empty-state">No results yet.</p>
        </div>
      </section>
    </main>

    <script src="/static/app.js"></script>
  </body>
</html>
```

- [ ] **Step 4: Replace the JavaScript**

Replace `app/static/app.js` with:

```javascript
const applicationFile = document.querySelector("#applicationFile");
const preview = document.querySelector("#preview");
const previewFrame = document.querySelector(".preview-frame");
const previewPlaceholder = document.querySelector("#previewPlaceholder");
const applicationForm = document.querySelector("#applicationForm");
const applicationFields = document.querySelector("#applicationFields");
const verifyButton = document.querySelector("#verifyButton");
const statusOutput = document.querySelector("#status");
const results = document.querySelector("#results");

const fieldOrder = [
  "brand_name",
  "class_type",
  "alcohol_content",
  "net_contents",
  "bottler_address",
  "country_of_origin",
  "government_warning",
];

const applicationFieldOrder = [
  ["brand_name", "Brand name"],
  ["class_type", "Class/type"],
  ["alcohol_content", "Alcohol content"],
  ["net_contents", "Net contents"],
  ["bottler_address", "Bottler/producer address"],
  ["country_of_origin", "Country of origin"],
];

const requiredApplicationFields = [
  "brand_name",
  "class_type",
  "alcohol_content",
  "net_contents",
  "bottler_address",
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatStatus(value) {
  return String(value || "unknown").replaceAll("_", " ");
}

function setStatus(message, state = "") {
  statusOutput.textContent = message;
  statusOutput.className = state ? `status ${state}` : "status";
}

function renderError(message) {
  results.innerHTML = `<div class="error-box" role="alert">${escapeHtml(message)}</div>`;
}

function resetApplicationPreview(message = "No application selected") {
  preview.removeAttribute("src");
  previewFrame.classList.remove("has-image");
  previewPlaceholder.textContent = message;
  applicationFields.hidden = true;
  applicationFields.innerHTML = "";
  verifyButton.disabled = true;
}

function validateApplicationPreview(application) {
  if (!application || typeof application !== "object" || Array.isArray(application)) {
    throw new Error("Application file is not valid JSON.");
  }

  const missingField = requiredApplicationFields.find((fieldName) => {
    const value = application[fieldName];
    return typeof value !== "string" || !value.trim();
  });
  if (missingField) {
    throw new Error(`Application is missing required field: ${missingField}.`);
  }

  const attachment = application.label_attachment;
  if (!attachment || typeof attachment !== "object" || Array.isArray(attachment)) {
    throw new Error("Application is missing label_attachment.");
  }

  if (
    typeof attachment.filename !== "string" ||
    typeof attachment.content_type !== "string" ||
    typeof attachment.data !== "string" ||
    !attachment.filename.trim() ||
    !attachment.content_type.trim() ||
    !attachment.data.trim()
  ) {
    throw new Error("Application is missing label_attachment.");
  }

  if (!attachment.content_type.toLowerCase().startsWith("image/")) {
    throw new Error("Unsupported label attachment type. Include an image attachment.");
  }
}

function renderApplicationFields(application) {
  applicationFields.hidden = false;
  applicationFields.innerHTML = applicationFieldOrder
    .map(([fieldName, label]) => {
      const value = application[fieldName] || "";
      const displayValue = value || "Not provided";
      return `
        <div class="readonly-field">
          <span>${escapeHtml(label)}</span>
          <div class="field-value${value ? "" : " empty-value"}">${escapeHtml(displayValue)}</div>
        </div>
      `;
    })
    .join("");
}

function renderAttachmentPreview(application) {
  const attachment = application.label_attachment;
  preview.src = `data:${attachment.content_type};base64,${attachment.data}`;
  previewFrame.classList.add("has-image");
  previewPlaceholder.textContent = attachment.filename;
}

function renderFieldRow(result, detectedValue = "") {
  const label = result?.label || result?.field || "Field";
  const status = result?.status || "needs_review";
  const extracted = result?.extracted || detectedValue;
  const expected = result?.expected || "";
  const message = result?.message || "";
  const extractedMarkup = extracted
    ? `<div class="field-value">${escapeHtml(extracted)}</div>`
    : '<div class="field-value empty-value"><em>Not found</em></div>';

  return `
    <article class="result-row">
      <div class="field-title">
        <span>${escapeHtml(label)}</span>
        <span class="field-status ${escapeHtml(status)}">${escapeHtml(formatStatus(status))}</span>
      </div>
      <div class="field-detail">
        <div>
          <strong>Expected:</strong>
          <div class="field-value">${escapeHtml(expected)}</div>
        </div>
        <div>
          <strong>Extracted:</strong>
          ${extractedMarkup}
        </div>
        <div>
          <strong>Message:</strong>
          <div class="field-value">${escapeHtml(message)}</div>
        </div>
      </div>
    </article>
  `;
}

function renderResults(data) {
  const overallStatus = data?.overall_status || "needs_review";
  const processingMs = Number(data?.processing_ms ?? 0);
  const extractionMs = Number(data?.extraction_ms ?? 0);
  const fieldResults = data?.field_results || {};
  const fieldGuesses = data?.field_guesses || {};
  const rows = fieldOrder
    .filter((fieldName) => fieldResults[fieldName])
    .map((fieldName) => renderFieldRow(fieldResults[fieldName], fieldGuesses[fieldName]))
    .join("");

  results.innerHTML = `
    <div class="summary">
      <span class="badge ${escapeHtml(overallStatus)}">${escapeHtml(formatStatus(overallStatus))}</span>
      <span class="meta">Extraction: ${escapeHtml(extractionMs)} ms</span>
      <span class="meta">Verification: ${escapeHtml(processingMs)} ms</span>
    </div>
    <div class="result-list">
      ${rows || '<p class="empty-state">No field results were returned.</p>'}
    </div>
    <details>
      <summary>Raw extracted text</summary>
      <pre class="raw-text">${escapeHtml(data?.raw_text || "")}</pre>
    </details>
  `;
}

function getApiErrorMessage(errorBody, fallback) {
  if (!errorBody) {
    return fallback;
  }

  if (typeof errorBody.detail === "string") {
    return errorBody.detail;
  }

  if (Array.isArray(errorBody.detail)) {
    return errorBody.detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .join("; ");
  }

  return fallback;
}

applicationFile.addEventListener("change", async () => {
  const file = applicationFile.files[0];
  resetApplicationPreview();

  if (!file) {
    setStatus("Ready");
    return;
  }

  try {
    const application = JSON.parse(await file.text());
    validateApplicationPreview(application);
    renderApplicationFields(application);
    renderAttachmentPreview(application);
    verifyButton.disabled = false;
    setStatus("Application loaded", "pass");
    results.innerHTML = '<p class="empty-state">No results yet.</p>';
  } catch (error) {
    const message = error instanceof Error ? error.message : "Application file could not be read.";
    renderError(message);
    setStatus("Needs attention", "error");
    resetApplicationPreview(file.name);
  }
});

applicationForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = applicationFile.files[0];
  if (!file) {
    renderError("Upload a liquor application JSON file.");
    setStatus("Needs attention", "error");
    return;
  }

  const body = new FormData();
  body.append("application_file", file);

  verifyButton.disabled = true;
  setStatus("Verifying...", "busy");
  results.innerHTML = '<p class="empty-state">Review in progress...</p>';

  try {
    const response = await fetch("/api/verify", { method: "POST", body });
    let responseBody = null;

    try {
      responseBody = await response.json();
    } catch (_error) {
      responseBody = null;
    }

    if (!response.ok) {
      const message = getApiErrorMessage(responseBody, "Verification failed. Please check the application and try again.");
      throw new Error(message);
    }

    renderResults(responseBody);
    setStatus(formatStatus(responseBody.overall_status), responseBody.overall_status);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Verification failed.";
    renderError(message);
    setStatus("Needs attention", "error");
  } finally {
    verifyButton.disabled = false;
  }
});
```

- [ ] **Step 5: Update CSS selectors and add read-only field styles**

In `app/static/styles.css`, replace:

```css
#labelImage {
  width: 100%;
  max-width: 19rem;
  margin-top: 0.5rem;
}
```

with:

```css
#applicationFile {
  width: 100%;
  max-width: 19rem;
  margin-top: 0.5rem;
}
```

After the existing `.field-grid` block, add:

```css
.application-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
  margin-bottom: 1rem;
}

.readonly-field {
  display: grid;
  gap: 0.35rem;
  min-width: 0;
}

.readonly-field span {
  font-weight: 700;
}

.readonly-field .field-value {
  min-height: 2.75rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #f8fafc;
}
```

In the media query selector list near the end of `app/static/styles.css`, replace:

```css
  .field-grid,
```

with:

```css
  .field-grid,
  .application-fields,
```

- [ ] **Step 6: Run static tests**

Run: `.venv/bin/python -m pytest tests/test_static_assets.py -v`

Expected: PASS for all static asset tests.

- [ ] **Step 7: Commit UI contract change**

```bash
git add app/static/index.html app/static/app.js app/static/styles.css tests/test_static_assets.py
git commit -m "feat: add application JSON upload UI"
```

### Task 4: Documentation Updates

**Files:**
- Modify: `README.md`
- Modify: `docs/approach.md`

- [ ] **Step 1: Update README workflow and API docs**

In `README.md`, replace the first paragraph with:

```markdown
Label Verifier is a local FastAPI prototype for reviewing alcohol label text against standardized liquor application data. It accepts one uploaded JSON application file containing expected application fields and a base64-encoded label attachment, extracts likely field values from the label with OCR, and reports pass, mismatch, missing, or needs-review results.
```

Keep the existing `Run Locally` section unchanged because the Uvicorn command does not change.

Replace the `Use The App` section with:

```markdown
## Use The App

1. Upload one liquor application `.json` file.
2. Confirm the application fields and embedded label preview load.
3. Select `Verify Label`.
4. Review extracted values, expected application values, confidence/source candidates, and field status messages.
```

Replace the `API` section with:

````markdown
## API

`POST /api/verify` accepts multipart form data:

- `application_file`: required JSON upload

The JSON application must include standardized expected fields and a base64 image attachment:

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
  -F application_file=@example_application.json
```
````

- [ ] **Step 2: Update approach workflow assumptions**

In `docs/approach.md`, replace the three-step list under `## Approach` with:

```markdown
1. Parse the uploaded liquor application JSON file.
2. Decode the embedded label image attachment.
3. Extract text from the label image.
4. Detect likely field values from the extracted text.
5. Compare detected values against expected application values and return field-level results.
```

Replace this sentence:

```markdown
The backend is a FastAPI app in `app/main.py`. The frontend in `app/static` posts multipart form data to `/api/verify` and renders the response.
```

with:

```markdown
The backend is a FastAPI app in `app/main.py`. The frontend in `app/static` posts one multipart `application_file` upload to `/api/verify` and renders the response.
```

Replace this assumption:

```markdown
- The expected field inputs may be blank to support testing extraction behavior independently from verification.
```

with:

```markdown
- Expected field values come from the uploaded application JSON, not manual form inputs.
```

- [ ] **Step 3: Inspect documentation diff**

Run: `git diff -- README.md docs/approach.md`

Expected: The diff documents JSON application upload and no longer describes manual expected-field entry as the primary workflow.

- [ ] **Step 4: Commit docs**

```bash
git add README.md docs/approach.md
git commit -m "docs: document application JSON workflow"
```

### Task 5: Full Verification And Local Smoke Test

**Files:**
- Verify: all changed files

- [ ] **Step 1: Run the focused test set**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_application_upload.py \
  tests/test_api.py \
  tests/test_static_assets.py \
  -v
```

Expected: PASS for parser, API, and static UI tests.

- [ ] **Step 2: Run the full test suite**

Run: `.venv/bin/python -m pytest`

Expected: PASS for the full suite.

- [ ] **Step 3: Start the app locally**

Run: `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`

Expected: Uvicorn reports `Uvicorn running on http://127.0.0.1:8000`. If port `8000` is already in use, run the same command with `--port 8001`.

- [ ] **Step 4: Smoke test health endpoint**

Run: `curl -sS http://127.0.0.1:8000/api/health`

Expected:

```json
{"status":"ok"}
```

If the app is running on port `8001`, use `http://127.0.0.1:8001/api/health`.

- [ ] **Step 5: Smoke test JSON upload with a generated local fixture**

Create `/tmp/label-verifier-application.json` using this command:

```bash
.venv/bin/python -c 'import base64, json, pathlib; image = pathlib.Path("examplelabels/orpheus_seal_main.jpg").read_bytes(); payload = {"brand_name": "ORPHEUS BREWING", "class_type": "Ale", "alcohol_content": "", "net_contents": "12 FL. OZ.", "bottler_address": "", "country_of_origin": "", "label_attachment": {"filename": "orpheus_seal_main.jpg", "content_type": "image/jpeg", "data": base64.b64encode(image).decode("ascii")}}; pathlib.Path("/tmp/label-verifier-application.json").write_text(json.dumps(payload))'
```

Run:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/verify \
  -F application_file=@/tmp/label-verifier-application.json
```

Expected: JSON response includes `overall_status`, `field_results`, `raw_text`, `extraction_ms`, and `field_guesses`. If the app is running on port `8001`, use `http://127.0.0.1:8001/api/verify`.

- [ ] **Step 6: Verify the browser UI**

Open the local app in the in-app Browser at `http://127.0.0.1:8000` or `http://127.0.0.1:8001`.

Expected:

- The first screen has one application JSON upload.
- Manual expected-field inputs are absent.
- Selecting `/tmp/label-verifier-application.json` populates read-only application fields.
- The label image preview appears.
- Selecting `Verify Label` renders field-by-field results.
- Text does not overlap on desktop or mobile widths.

- [ ] **Step 7: Final git check**

Run: `git status --short`

Expected: no uncommitted changes after the task commits.

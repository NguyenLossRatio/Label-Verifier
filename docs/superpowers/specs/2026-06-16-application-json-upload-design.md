# Application JSON Upload Design

## Goal

Change Label Verifier from a manual expected-field workflow to a single liquor application upload workflow. The uploaded file is a standardized JSON application that contains the expected application data and an embedded label attachment. The app uses the application fields as the source of truth, OCRs the embedded label image, and reports label-to-application mismatches.

## User Workflow

1. The user uploads one `.json` liquor application file.
2. The frontend shows the parsed application fields as read-only review data.
3. The frontend shows a preview of the embedded label image when the attachment is valid.
4. The user selects `Verify Label`.
5. The backend extracts the embedded label image, OCRs it, and compares the OCR output against application fields.
6. The existing field-by-field results view displays expected values from the application, extracted label values, statuses, messages, timings, raw OCR text, and candidates.

Manual expected-field inputs are removed from the primary workflow.

## JSON Contract

The supported upload format is a single JSON object:

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

Required top-level fields:

- `brand_name`
- `class_type`
- `alcohol_content`
- `net_contents`
- `bottler_address`
- `label_attachment`

Optional top-level field:

- `country_of_origin`, defaulting to an empty string when omitted

The government warning remains hardcoded in `app/constants.py` and is not supplied by the JSON application.

`label_attachment` requirements:

- `filename`: non-empty string for display and diagnostics
- `content_type`: image MIME type beginning with `image/`
- `data`: base64-encoded image bytes

The first implementation supports standard JSON with a base64 image attachment only. It does not support separate label files, ZIP containers, PDFs, remote URLs, or batch uploads.

## Backend Design

Add an application parsing boundary separate from OCR and verification, likely in a new module such as `app/application_upload.py`.

Responsibilities:

- Read uploaded JSON bytes.
- Parse JSON into a typed Pydantic model.
- Validate required application fields.
- Validate and decode the embedded label attachment.
- Convert application fields into the existing `ExpectedFields` model.
- Return label bytes plus attachment metadata to the verification endpoint.

Update `/api/verify` so it accepts:

- `application_file`: a required uploaded `.json` file

The endpoint will:

1. Reject missing uploads with `400`.
2. Reject non-JSON content types or non-`.json` filenames with `400`.
3. Parse and validate the application JSON.
4. Decode and validate `label_attachment`.
5. OCR the decoded label image with the existing `extract_text_from_image`.
6. Run the existing `extract_field_candidates`, `select_field_guesses`, and `verify_label_text`.
7. Return the existing `VerifyResponse`, with expected fields sourced from the application.

The current verification and extraction internals should remain mostly unchanged.

## Frontend Design

Replace the label image drop zone and editable expected-fields form with a single application upload control:

- File input accepts `.json` and `application/json`.
- Upload state displays the selected application filename.
- Parsed fields appear as read-only values.
- The embedded label attachment appears in the existing preview frame.
- `Verify Label` is disabled until a valid JSON application has been selected.

The browser can parse the JSON for preview and validation hints, but the backend remains authoritative. The frontend should not need to manually append individual expected fields to the request.

On submit, the frontend posts multipart form data to `/api/verify`:

- `application_file`: the selected JSON file

## Error Handling

Backend errors should be clear and specific:

- Missing application upload: `Upload a liquor application JSON file.`
- Unsupported file type: `Unsupported file type. Upload a JSON application file.`
- Invalid JSON: `Application file is not valid JSON.`
- Missing required field: `Application is missing required field: <field>.`
- Missing attachment: `Application is missing label_attachment.`
- Invalid base64 data: `Label attachment data must be base64-encoded image bytes.`
- Unsupported attachment type: `Unsupported label attachment type. Include an image attachment.`
- OCR failure: keep the existing `ExtractionError` mapping to `422`.

Frontend errors should render in the existing results area and set status to `Needs attention`.

## Testing

Add or update backend tests for:

- Successful `/api/verify` request using one JSON upload with embedded label bytes.
- Government warning still uses the hardcoded constant and ignores JSON input.
- Missing application upload.
- Non-JSON application upload.
- Invalid JSON.
- Missing required application field.
- Missing `label_attachment`.
- Invalid base64 attachment data.
- Non-image attachment content type.

Add or update static asset tests for:

- The UI contains an application JSON upload input.
- Manual expected-field inputs are removed from the primary form.
- JavaScript posts `application_file` to `/api/verify`.
- JavaScript previews read-only application fields and the embedded label.

Keep verification and extraction unit tests unchanged unless they need minor fixture updates.

## Non-Goals

- No batch upload in this change.
- No PDF parsing.
- No separate label file upload.
- No remote attachment URLs.
- No long-term application or label storage.
- No change to the strict government warning rule.

## Open Decisions Resolved

- The upload format is a single JSON application file.
- The label attachment is embedded in JSON as base64 image bytes.
- Application fields, not user-entered form fields, populate expected verification data.

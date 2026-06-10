# Guided Review Application Plan

## Product Direction

Build a standalone guided-review web application that lets a compliance agent verify one alcohol label at a time. The first version should make the routine review path obvious: upload a label image, enter the expected application values, run verification, and review a clear pass/fail result.

This plan intentionally prioritizes a usable core workflow over batch processing, dashboards, or COLA integration.

## Target User Workflow

1. Agent opens the application.
2. Agent uploads one label image.
3. Agent enters or pastes the expected application fields.
4. Agent clicks `Verify Label`.
5. The app extracts visible label text from the image.
6. The app compares extracted text against the expected fields.
7. The app displays an overall result:
   - `Pass`: no blocking issues found
   - `Needs Review`: one or more mismatches or uncertain checks
   - `Unreadable`: the image could not be processed reliably
8. Agent reviews field-by-field results and decides whether to accept, reject, or manually investigate.

## Core Screen

The first version should use a single-page guided review layout:

- Header with the application name and a short status area
- Left side: label upload and image preview
- Right side: expected application fields
- Bottom or right rail: verification results

The screen should avoid hidden navigation, multi-step wizards, or complex menus. Everything needed for a single review should be visible at once.

## Input Fields

The app should support these expected application fields:

- Brand name
- Class/type designation
- Alcohol content / ABV
- Net contents
- Bottler or producer name and address
- Country of origin
- Government health warning statement

For the prototype, fields can be entered manually in a form. A later version could support CSV import, JSON paste, or direct integration with application records.

## Label Processing

The app should process the uploaded label image using an OCR or vision extraction layer.

The extraction result should include:

- Raw extracted text
- Structured field guesses where possible
- Confidence or uncertainty indicators
- Image processing errors, if any

The first implementation should keep this layer replaceable so the prototype can use a local OCR engine, mocked extraction, or an AI vision API depending on environment constraints.

## Verification Rules

The app should run deterministic checks after text extraction.

### Exact Or Strict Checks

- Government warning must be present.
- `GOVERNMENT WARNING:` must be uppercase.
- Warning text must match the required wording as closely as the prototype can verify.
- Alcohol content should match the expected value.
- Net contents should match the expected value.

### Tolerant Checks

- Brand name comparison should tolerate capitalization and punctuation differences where the meaning is clearly the same.
- Class/type comparison should tolerate minor capitalization differences.
- Bottler/producer address comparison can begin as a partial text match, with mismatches flagged for human review.

### Uncertain Checks

If OCR confidence is low or the image is hard to read, the app should mark affected fields as `Needs Review` rather than incorrectly passing them.

## Results Experience

Results should be field-by-field and easy to scan:

- Overall status at the top
- One row per field
- Expected value
- Extracted value
- Result status
- Short explanation

Suggested statuses:

- `Pass`
- `Mismatch`
- `Missing`
- `Needs Review`
- `Unreadable`

The raw extracted text should be available in an expandable section for debugging and transparency, but it should not dominate the main review flow.

## Error Handling

The app should handle common failures clearly:

- Unsupported file type
- Image too large
- OCR or extraction failure
- No readable text found
- Missing expected application fields

Errors should tell the agent what happened and what to do next, such as uploading a clearer image or filling in a required field.

## Performance Target

The application should aim to return verification results within 5 seconds for a single label.

The first implementation should measure and display processing time internally during development. If processing exceeds the target, the app should still return a useful result and avoid leaving the user in an indefinite loading state.

## Data And Storage

For the prototype:

- Do not require accounts or authentication.
- Do not persist uploaded labels by default.
- Do not retain sensitive application data after the review session.
- Keep all review state in memory or browser session state unless explicit export is added later.

## Suggested Technical Shape

A practical prototype can be built as a small web application with:

- Frontend: single-page review interface
- Backend: upload handling, OCR/vision extraction, verification rules
- Verification module: deterministic comparison functions
- Test fixtures: sample label images and expected application data

The extraction layer should be abstracted behind a simple interface:

```text
extractLabelText(image) -> extractionResult
verifyLabel(expectedFields, extractionResult) -> verificationReport
```

This keeps the app usable even if the OCR provider changes.

## MVP Scope

The first usable version should include:

- Single image upload
- Image preview
- Manual expected-field form
- OCR or mocked text extraction path
- Field-by-field verification
- Strict government warning check
- Tolerant brand-name comparison
- Clear overall result
- Basic error handling
- README instructions for setup and running

## Deferred Scope

These features should wait until the guided-review workflow is working:

- Batch uploads
- Queue management
- CSV import/export
- Management dashboard
- User accounts
- COLA integration
- Long-term document storage
- Production federal compliance controls

## Validation Plan

Use a small test set with known outcomes:

- Fully compliant label
- Brand capitalization difference only
- Missing government warning
- Incorrect `Government Warning` capitalization
- ABV mismatch
- Net contents mismatch
- Low-quality or unreadable image

The application is usable when an agent can complete a single review without instructions and understand why each field passed or failed.

## Future Expansion Path

After the guided-review workflow is stable, the next logical version is batch review:

1. Upload multiple labels.
2. Process each label using the same extraction and verification modules.
3. Show a queue of results.
4. Let agents open any result in the same guided-review detail view.

This keeps the first application focused while preserving a clean path toward the high-volume use case.

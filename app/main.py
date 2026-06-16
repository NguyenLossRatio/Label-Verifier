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


def _is_json_application_upload(upload: UploadFile) -> bool:
    filename = (upload.filename or "").lower()
    content_type = (upload.content_type or "").lower()
    return filename.endswith(".json") and content_type in JSON_CONTENT_TYPES


@app.post("/api/verify", response_model=VerifyResponse)
async def verify(
    application_file: Annotated[UploadFile | None, File()] = None,
) -> VerifyResponse:
    if application_file is None:
        raise HTTPException(status_code=400, detail="Upload a liquor application JSON file.")

    if not _is_json_application_upload(application_file):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a JSON application file.",
        )

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

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.extraction import (
    ExtractionError,
    extract_field_candidates,
    extract_text_from_image,
    select_field_guesses,
)
from app.models import ExpectedFields, VerifyResponse
from app.verification import verify_label_text

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_PATH = STATIC_DIR / "index.html"

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
    brand_name: Annotated[str, Form()] = "",
    class_type: Annotated[str, Form()] = "",
    alcohol_content: Annotated[str, Form()] = "",
    net_contents: Annotated[str, Form()] = "",
    bottler_address: Annotated[str, Form()] = "",
    country_of_origin: Annotated[str, Form()] = "",
    government_warning: Annotated[str, Form()] = "",
    raw_text_override: Annotated[str, Form()] = "",
    label_image: Annotated[UploadFile | None, File()] = None,
) -> VerifyResponse:
    try:
        expected = ExpectedFields(
            brand_name=brand_name,
            class_type=class_type,
            alcohol_content=alcohol_content,
            net_contents=net_contents,
            bottler_address=bottler_address,
            country_of_origin=country_of_origin,
            government_warning=government_warning,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if raw_text_override.strip():
        raw_text = raw_text_override.strip()
        extraction_ms = 0
    elif label_image is not None:
        if not (label_image.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail="Unsupported file type. Upload an image file.")

        try:
            raw_text, extraction_ms = extract_text_from_image(await label_image.read())
        except ExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=400, detail="Upload a label image or provide raw extracted text.")

    field_candidates = extract_field_candidates(raw_text)
    field_guesses = select_field_guesses(field_candidates)
    report = verify_label_text(expected, raw_text, field_guesses=field_guesses)
    return VerifyResponse(
        **report.model_dump(),
        extraction_ms=extraction_ms,
        field_guesses=field_guesses,
        field_candidates={
            field: [candidate.__dict__ for candidate in candidates]
            for field, candidates in field_candidates.items()
        },
    )

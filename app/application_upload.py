import base64
import binascii
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError
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
    if country is None:
        payload["country_of_origin"] = ""
    elif not isinstance(country, str):
        raise ApplicationUploadError("Application is missing required field: country_of_origin.")


def _validate_attachment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    attachment = payload.get("label_attachment")
    if not isinstance(attachment, dict):
        raise ApplicationUploadError("Application is missing label_attachment.")

    for field_name in ("filename", "content_type", "data"):
        value = attachment.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ApplicationUploadError("Application is missing label_attachment.")

    content_type = attachment["content_type"].lower()
    if not content_type.startswith("image/") or content_type == "image/":
        raise ApplicationUploadError("Unsupported label attachment type. Include an image attachment.")

    return attachment


def _decode_label_bytes(encoded_data: str) -> bytes:
    try:
        label_bytes = base64.b64decode(encoded_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApplicationUploadError("Label attachment data must be base64-encoded image bytes.") from exc

    if not label_bytes:
        raise ApplicationUploadError("Label attachment data must be base64-encoded image bytes.")

    _validate_image_bytes(label_bytes)
    return label_bytes


def _validate_image_bytes(label_bytes: bytes) -> None:
    try:
        with Image.open(BytesIO(label_bytes)) as image:
            image.verify()
    except (SyntaxError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ApplicationUploadError("Label attachment data must be base64-encoded image bytes.") from exc

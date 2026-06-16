import base64
from io import BytesIO
import json

import pytest
from PIL import Image

from app.application_upload import (
    ApplicationUploadError,
    MAX_LABEL_IMAGE_BYTES,
    MAX_LABEL_IMAGE_PIXELS,
    parse_application_upload,
)
from app.constants import REQUIRED_GOVERNMENT_WARNING


LABEL_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/"
    "AAX+Av4N70a4AAAAAElFTkSuQmCC"
)
NON_IMAGE_BYTES = b"fake image bytes"


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


def test_parse_application_upload_normalizes_null_country_of_origin_to_blank():
    parsed = parse_application_upload(
        encode_application(application_payload(country_of_origin=None))
    )

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

    with pytest.raises(
        ApplicationUploadError,
        match="Application is missing required field: brand_name.",
    ):
        parse_application_upload(encode_application(payload))


def test_parse_application_upload_rejects_blank_required_field():
    payload = application_payload(brand_name="  ")

    with pytest.raises(
        ApplicationUploadError,
        match="Application is missing required field: brand_name.",
    ):
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

    with pytest.raises(
        ApplicationUploadError,
        match="Label attachment data must be base64-encoded image bytes.",
    ):
        parse_application_upload(encode_application(payload))


def test_parse_application_upload_rejects_base64_encoded_non_image_bytes():
    payload = application_payload(
        label_attachment={
            "filename": "label.png",
            "content_type": "image/png",
            "data": base64.b64encode(NON_IMAGE_BYTES).decode("ascii"),
        }
    )

    with pytest.raises(
        ApplicationUploadError,
        match="Label attachment data must be base64-encoded image bytes.",
    ):
        parse_application_upload(encode_application(payload))


def test_parse_application_upload_rejects_oversized_label_attachment_data():
    payload = application_payload(
        label_attachment={
            "filename": "label.png",
            "content_type": "image/png",
            "data": base64.b64encode(b"x" * (MAX_LABEL_IMAGE_BYTES + 1)).decode("ascii"),
        }
    )

    with pytest.raises(
        ApplicationUploadError,
        match="Label attachment is too large.",
    ):
        parse_application_upload(encode_application(payload))


def test_parse_application_upload_rejects_oversized_label_image_dimensions():
    image_side = int(MAX_LABEL_IMAGE_PIXELS**0.5) + 1
    image_bytes = BytesIO()
    Image.new("RGB", (image_side, image_side), "white").save(image_bytes, format="PNG")
    payload = application_payload(
        label_attachment={
            "filename": "label.png",
            "content_type": "image/png",
            "data": base64.b64encode(image_bytes.getvalue()).decode("ascii"),
        }
    )

    with pytest.raises(
        ApplicationUploadError,
        match="Label attachment image dimensions are too large.",
    ):
        parse_application_upload(encode_application(payload))


def test_parse_application_upload_rejects_non_image_attachment_type():
    payload = application_payload(
        label_attachment={
            "filename": "label.txt",
            "content_type": "text/plain",
            "data": base64.b64encode(LABEL_BYTES).decode("ascii"),
        }
    )

    with pytest.raises(
        ApplicationUploadError,
        match="Unsupported label attachment type. Include an image attachment.",
    ):
        parse_application_upload(encode_application(payload))

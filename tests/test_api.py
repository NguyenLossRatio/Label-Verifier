import base64
import json

from fastapi.testclient import TestClient

from app.application_upload import MAX_APPLICATION_JSON_BYTES
from app.constants import REQUIRED_GOVERNMENT_WARNING
from app.extraction import ExtractionError
from app.main import app
from tests.test_verification import STANDARD_WARNING


LABEL_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/"
    "AAX+Av4N70a4AAAAAElFTkSuQmCC"
)


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


def test_verify_endpoint_uses_hardcoded_government_warning_from_application(monkeypatch):
    client = TestClient(app)
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

    response = client.post(
        "/api/verify",
        files=application_file(valid_application(government_warning="WRONG WARNING")),
    )

    assert response.status_code == 200
    warning = response.json()["field_results"]["government_warning"]
    assert warning["expected"] == REQUIRED_GOVERNMENT_WARNING
    assert warning["status"] == "pass"


def test_verify_endpoint_requires_application_upload():
    client = TestClient(app)

    response = client.post("/api/verify")

    assert response.status_code == 400
    assert response.json()["detail"] == "Upload a liquor application JSON file."


def test_verify_endpoint_rejects_non_json_application_upload():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files=application_file(filename="application.txt", content_type="text/plain"),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type. Upload a JSON application file."


def test_verify_endpoint_rejects_invalid_json():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={"application_file": ("application.json", b"not json", "application/json")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Application file is not valid JSON."


def test_verify_endpoint_rejects_oversized_application_upload():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        files={
            "application_file": (
                "application.json",
                b" " * (MAX_APPLICATION_JSON_BYTES + 1),
                "application/json",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Application file is too large."


def test_verify_endpoint_rejects_missing_required_application_field():
    client = TestClient(app)
    payload = valid_application()
    del payload["brand_name"]

    response = client.post("/api/verify", files=application_file(payload))

    assert response.status_code == 400
    assert response.json()["detail"] == "Application is missing required field: brand_name."


def test_verify_endpoint_rejects_missing_label_attachment():
    client = TestClient(app)
    payload = valid_application()
    del payload["label_attachment"]

    response = client.post("/api/verify", files=application_file(payload))

    assert response.status_code == 400
    assert response.json()["detail"] == "Application is missing label_attachment."


def test_verify_endpoint_rejects_invalid_base64_attachment():
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


def test_verify_endpoint_rejects_non_image_attachment_content_type():
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

    def fail_extraction(image_bytes):
        assert image_bytes == LABEL_BYTES
        raise ExtractionError("No readable text was found in the image.")

    monkeypatch.setattr("app.main.extract_text_from_image", fail_extraction)

    response = client.post("/api/verify", files=application_file())

    assert response.status_code == 422
    assert response.json()["detail"] == "No readable text was found in the image."

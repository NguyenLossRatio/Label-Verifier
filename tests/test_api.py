from fastapi.testclient import TestClient

from app.extraction import ExtractionError
from app.main import app
from tests.test_verification import STANDARD_WARNING


def valid_form_data(**overrides):
    values = {
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "bottler_address": "Old Tom Distillery, Louisville, KY",
        "country_of_origin": "",
        "government_warning": STANDARD_WARNING,
        "raw_text_override": "",
    }
    values.update(overrides)
    return values


def test_verify_endpoint_accepts_raw_text_override():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        data=valid_form_data(
            raw_text_override=(
                "OLD TOM DISTILLERY\n"
                "Kentucky Straight Bourbon Whiskey\n"
                "45% Alc./Vol. (90 Proof)\n"
                "750 mL\n"
                "Old Tom Distillery, Louisville, KY\n"
                + STANDARD_WARNING
            ),
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "pass"
    assert body["field_results"]["brand_name"]["status"] == "pass"
    assert body["extraction_ms"] == 0
    assert body["field_guesses"]["alcohol_content"] == "45% Alc./Vol. (90 Proof)"


def test_verify_endpoint_returns_422_for_blank_required_field():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        data=valid_form_data(
            brand_name="   ",
            raw_text_override=(
                "OLD TOM DISTILLERY\n"
                "Kentucky Straight Bourbon Whiskey\n"
                "45% Alc./Vol. (90 Proof)\n"
                "750 mL\n"
                "Old Tom Distillery, Louisville, KY\n"
                + STANDARD_WARNING
            ),
        ),
    )

    assert response.status_code == 422
    assert "Field is required and cannot be blank" in response.json()["detail"]


def test_verify_endpoint_accepts_image_upload(monkeypatch):
    client = TestClient(app)
    image_bytes = b"fake image bytes"
    raw_text = (
        "OLD TOM DISTILLERY\n"
        "Kentucky Straight Bourbon Whiskey\n"
        "45% Alc./Vol. (90 Proof)\n"
        "750 mL\n"
        "Old Tom Distillery, Louisville, KY\n"
        + STANDARD_WARNING
    )

    def extract_text(image_data):
        assert image_data == image_bytes
        return raw_text, 123

    monkeypatch.setattr("app.main.extract_text_from_image", extract_text)

    response = client.post(
        "/api/verify",
        data=valid_form_data(),
        files={"label_image": ("label.png", image_bytes, "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_ms"] == 123
    assert body["overall_status"] == "pass"


def test_verify_endpoint_requires_image_or_raw_text():
    client = TestClient(app)

    response = client.post("/api/verify", data=valid_form_data(raw_text_override=""))

    assert response.status_code == 400
    assert response.json()["detail"] == "Upload a label image or provide raw extracted text."


def test_verify_endpoint_rejects_non_image_upload():
    client = TestClient(app)

    response = client.post(
        "/api/verify",
        data=valid_form_data(),
        files={"label_image": ("label.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type. Upload an image file."


def test_verify_endpoint_maps_extraction_errors_to_unprocessable_entity(monkeypatch):
    client = TestClient(app)

    def fail_extraction(_image_bytes):
        raise ExtractionError("No readable text was found in the image.")

    monkeypatch.setattr("app.main.extract_text_from_image", fail_extraction)

    response = client.post(
        "/api/verify",
        data=valid_form_data(),
        files={"label_image": ("label.png", b"invalid image bytes", "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "No readable text was found in the image."

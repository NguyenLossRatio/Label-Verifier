from pathlib import Path


def test_application_upload_html_has_required_controls():
    html = Path("app/static/index.html").read_text()

    assert 'id="applicationFile"' in html
    assert 'name="application_file"' in html
    assert 'accept=".json,application/json"' in html
    assert 'id="applicationForm"' in html
    assert 'id="applicationFields"' in html
    assert 'id="verifyButton" type="submit" disabled' in html
    assert 'id="results"' in html
    assert 'id="rawTextOverride"' not in html


def test_application_upload_html_links_static_assets_and_removes_manual_expected_inputs():
    html = Path("app/static/index.html").read_text()

    assert 'href="/static/styles.css"' in html
    assert 'src="/static/app.js"' in html
    assert 'id="status"' in html
    assert "Application Source" in html
    assert "Application Fields" in html
    assert "No application selected" in html
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


def test_frontend_javascript_resets_invalid_and_successful_preview_state():
    javascript = Path("app/static/app.js").read_text()

    assert 'results.innerHTML = \'<p class="empty-state">No results yet.</p>\'' in javascript
    assert 'resetApplicationPreview(file.name)' not in javascript


def test_frontend_javascript_restores_verify_button_from_current_validity_state():
    javascript = Path("app/static/app.js").read_text()

    assert "currentApplicationValid" in javascript
    assert "verifyButton.disabled = !currentApplicationValid" in javascript
    assert "finally" in javascript
    assert "verifyButton.disabled = false;" not in javascript


def test_frontend_javascript_matches_backend_image_content_type_validation():
    javascript = Path("app/static/app.js").read_text()

    assert 'const contentType = attachment.content_type.toLowerCase()' in javascript
    assert '!contentType.startsWith("image/") || contentType === "image/"' in javascript
    assert ".trim().toLowerCase()" not in javascript
    assert "attachment.content_type.toLowerCase().startsWith" not in javascript
    assert "contentType" in javascript


def test_disabled_verify_button_does_not_use_wait_cursor():
    stylesheet = Path("app/static/styles.css").read_text()

    assert "cursor: wait" not in stylesheet


def test_frontend_preserves_multiline_field_value_formatting():
    javascript = Path("app/static/app.js").read_text()
    stylesheet = Path("app/static/styles.css").read_text()

    assert "field-value" in javascript
    assert "white-space: pre-wrap" in stylesheet

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

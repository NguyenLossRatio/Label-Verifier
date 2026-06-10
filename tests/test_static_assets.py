from pathlib import Path


def test_guided_review_html_has_required_controls():
    html = Path("app/static/index.html").read_text()

    assert 'id="labelImage"' in html
    assert 'id="expectedFields"' in html
    assert 'id="verifyButton"' in html
    assert 'id="results"' in html
    assert 'id="rawTextOverride"' in html


def test_guided_review_html_links_static_assets_and_api_fields():
    html = Path("app/static/index.html").read_text()

    assert 'href="/static/styles.css"' in html
    assert 'src="/static/app.js"' in html
    assert 'id="status"' in html
    assert 'name="label_image"' in html
    assert 'name="raw_text_override"' in html

    for field_name in (
        "brand_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "bottler_address",
        "country_of_origin",
        "government_warning",
    ):
        assert f'name="{field_name}"' in html


def test_frontend_javascript_calls_verify_endpoint():
    javascript = Path("app/static/app.js").read_text()

    assert 'fetch("/api/verify"' in javascript
    assert "renderResults" in javascript

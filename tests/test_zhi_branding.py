import base64
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_uploaded_logo_and_caption_share_the_correct_website_link():
    app = AppTest.from_string(
        "from zhi_branding import render_zhi_branding\nrender_zhi_branding()"
    ).run()
    assert not app.exception
    markup = app.markdown[0].value
    assert 'href="https://zhisystems.ai"' in markup
    assert 'target="_blank"' in markup
    assert 'rel="noopener noreferrer"' in markup
    assert "ZHI SYSTEMS" in markup
    assert markup.index("<img") < markup.index("<span")
    encoded = markup.split("data:image/png;base64,", 1)[1].split('"', 1)[0]
    assert base64.b64decode(encoded) == Path("assets/zhi_uploaded_mark.png").read_bytes()


def test_branding_is_above_page_content_on_both_pages():
    source = Path("main.py").read_text()
    assert source.index("    render_zhi_branding()") < source.index("\npage.run()")

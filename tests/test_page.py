"""The phone page for adding today's story from a photo, with a pretend vision model."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from learnling.page import make_handler, passage_path, read_page, save_passage


def test_reading_a_page_sends_the_photo_and_tidies_the_text():
    seen = []

    def ask(messages):
        seen.append(messages)
        return '  "The  dog ran.\n\n\n\nIt was fast."  '

    assert read_page(b"jpegbytes", "image/jpeg", ask) == "The dog ran.\n\nIt was fast."
    image = seen[0][0]["content"][1]["image_url"]["url"]
    assert image.startswith("data:image/jpeg;base64,")


def test_a_page_with_no_text_says_so():
    assert read_page(b"x", "image/png", lambda m: "NONE") == ""


def test_saved_story_becomes_today(tmp_path):
    save_passage("The cat sat on the mat.", tmp_path)
    assert passage_path("today", tmp_path).read_text() == "The cat sat on the mat.\n"
    assert len(list(tmp_path.glob("*.txt"))) == 2  # today plus a dated copy


def test_today_before_anything_is_saved(tmp_path):
    with pytest.raises(FileNotFoundError):
        passage_path("today", tmp_path)


@pytest.fixture
def server(tmp_path):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(lambda m: "A big red bus went by.", tmp_path))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", tmp_path
    httpd.shutdown()


def _post(url, body, kind):
    request = urllib.request.Request(url, data=body, headers={"Content-Type": kind})
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as err:
        return json.loads(err.read())


def test_photo_then_save_through_the_page(server):
    base, folder = server
    with urllib.request.urlopen(base + "/") as response:
        assert b"Take a photo" in response.read()
    assert _post(base + "/read", b"photo", "image/jpeg") == {"text": "A big red bus went by."}
    assert _post(base + "/save", json.dumps({"text": "A big red bus went by."}).encode(), "application/json")["saved"]
    assert (folder / "today.txt").read_text().startswith("A big red bus")
    assert not list(folder.glob("*.jpg"))  # the photo is never kept


def test_the_page_rejects_non_photos_and_tiny_stories(server):
    base, _ = server
    assert "error" in _post(base + "/read", b"hello", "text/plain")
    assert "error" in _post(base + "/save", json.dumps({"text": "hi"}).encode(), "application/json")


def test_a_long_story_is_saved_with_a_warning(server):
    base, _ = server
    reply = _post(base + "/save", json.dumps({"text": "word " * 300}).encode(), "application/json")
    assert reply["saved"] and "long" in reply["warning"]

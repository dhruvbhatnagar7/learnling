"""Today's story from a photo: a small web page the stand serves on the home WiFi.

    python -m learnling page            # on the stand
    open http://learnling.local:8000    # on the parent's phone

The parent takes a photo of the school reading page, the text is read off it,
and they check and fix the text before saving it. `learnling stand --passage
today` then reads the saved story. Typing or pasting the text works too.

The photo is read by OpenAI's vision model (needs `OPENAI_API_KEY`) and then
dropped: it is never saved on the stand. Only the checked text is kept, in
`~/learnling-passages/`. Photograph the printed page only, not the child or
their handwriting.

There is no login: anyone on the home WiFi can open the page. Run it only on a
network you trust.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PASSAGE_FOLDER = Path.home() / "learnling-passages"
TODAY = "today.txt"
MAX_PHOTO_BYTES = 15 * 1024 * 1024
#: Two reads of a story longer than this is too long a sitting for a young reader.
LONG_STORY_WORDS = 200

_READ_PAGE = (
    "This is a photo of a page from a child's reading book or school reading sheet. Write out the "
    "main text a child would read aloud, exactly as printed: the same words, spelling and punctuation, "
    "with sentences joined into plain paragraphs. Leave out page numbers, headings that aren't part of "
    "the story, picture captions, and any handwriting. Reply with the text only. If there is no "
    "readable printed text, reply NONE."
)


def read_page(photo: bytes, mime: str, ask) -> str:
    """The reading text on a photographed page; `ask(messages)` is a vision chat model."""
    url = f"data:{mime};base64,{base64.b64encode(photo).decode()}"
    messages = [{"role": "user", "content": [
        {"type": "text", "text": _READ_PAGE},
        {"type": "image_url", "image_url": {"url": url}},
    ]}]
    text = ask(messages).strip()
    return "" if text.upper().startswith("NONE") else _tidy(text)


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip().strip('"').strip()


def openai_vision(model: str = "gpt-4.1-mini"):
    """`ask(messages)` for OpenAI's vision-capable chat model."""
    from learnling.buddy import OpenAIChat

    chat = OpenAIChat(model, timeout=60.0)

    def ask(messages):
        return chat(messages, max_words=400)

    return ask


def save_passage(text: str, folder: Path | None = None) -> Path:
    """Keep the checked text as today's story, and a dated copy."""
    folder = folder or PASSAGE_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    text = _tidy(text) + "\n"
    (folder / f"{datetime.now():%Y-%m-%d-%H%M%S}.txt").write_text(text)
    today = folder / TODAY
    today.write_text(text)
    return today


def passage_path(name: str, folder: Path | None = None) -> Path:
    """`today` means the story saved from the phone page; anything else is a file path."""
    if name == "today":
        path = (folder or PASSAGE_FOLDER) / TODAY
        if not path.exists():
            raise FileNotFoundError(
                "no story saved yet: open the phone page (python -m learnling page) and add one"
            )
        return path
    return Path(name)


def make_handler(ask, folder: Path | None = None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the terminal quiet
            pass

        def _send(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def do_GET(self):
            if self.path != "/":
                return self._send(404, b"not found", "text/plain")
            current = (folder or PASSAGE_FOLDER) / TODAY
            saved = current.read_text().strip() if current.exists() else ""
            self._send(200, PAGE.replace("{{SAVED}}", _html(saved)).encode(), "text/html; charset=utf-8")

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_PHOTO_BYTES:
                return self._json(413, {"error": "That photo is too big. Try a smaller one."})
            body = self.rfile.read(length)
            if self.path == "/read":
                mime = self.headers.get("Content-Type", "image/jpeg")
                if not mime.startswith("image/"):
                    return self._json(400, {"error": "Please choose a photo."})
                try:
                    text = read_page(body, mime, ask)
                except Exception:  # noqa: BLE001 - tell the parent, keep the page up
                    return self._json(502, {"error": "Couldn't read the photo. Check the internet, or type the text."})
                if not text:
                    return self._json(200, {"text": "", "error": "No printed text found. Try a closer, straighter photo."})
                return self._json(200, {"text": text})
            if self.path == "/save":
                text = json.loads(body or b"{}").get("text", "")
                if len(text.split()) < 3:
                    return self._json(400, {"error": "That's too short for a story."})
                save_passage(text, folder)
                words = len(text.split())
                reply = {"saved": True, "words": words}
                if words > LONG_STORY_WORDS:
                    reply["warning"] = (f"That's long for one session ({words} words). About 50 to 150 words "
                                        "works best; you can delete some and save again.")
                return self._json(200, reply)
            self._json(404, {"error": "not found"})

    return Handler


def _html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def serve(ask, port: int = 8000, folder: Path | None = None) -> None:  # pragma: no cover - runs forever
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(ask, folder))
    print(f"On a phone on the same WiFi, open http://learnling.local:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>learnling: today's story</title>
<style>
  body { font: 17px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 560px; padding: 16px; color: #222; background: #fbfaf7; }
  h1 { font-size: 22px; margin: 4px 0 12px; }
  .step { background: #fff; border: 1px solid #e4e1da; border-radius: 12px; padding: 14px; margin: 12px 0; }
  label.button, button { display: block; width: 100%; box-sizing: border-box; text-align: center; font: inherit;
    padding: 14px; border-radius: 10px; border: 0; background: #2f6f4f; color: #fff; cursor: pointer; }
  button.secondary { background: #e9e6df; color: #222; margin-top: 8px; }
  textarea { width: 100%; box-sizing: border-box; min-height: 220px; font: inherit; padding: 10px;
    border: 1px solid #ccc; border-radius: 8px; }
  #status { min-height: 1.5em; color: #555; }
  .small { font-size: 14px; color: #666; }
  input[type=file] { display: none; }
</style></head>
<body>
<h1>Today's story</h1>
<div class="step">
  <label class="button" for="photo">Take a photo of the reading page</label>
  <input id="photo" type="file" accept="image/*" capture="environment">
  <p class="small">Just the printed page, flat and in good light. The photo isn't kept.</p>
</div>
<div class="step">
  <p><b>Check the text</b> matches the page, and fix anything that's wrong. You can also type or paste it.</p>
  <textarea id="text">{{SAVED}}</textarea>
  <button id="save">Use this story</button>
  <p id="status"></p>
</div>
<script>
const status = document.getElementById("status"), text = document.getElementById("text");
document.getElementById("photo").addEventListener("change", async (e) => {
  const file = e.target.files[0]; if (!file) return;
  status.textContent = "Reading the page...";
  try {
    const r = await fetch("/read", {method: "POST", headers: {"Content-Type": file.type || "image/jpeg"}, body: file});
    const data = await r.json();
    if (data.text) { text.value = data.text; status.textContent = "Done. Check it against the page, then tap Use this story."; }
    else status.textContent = data.error || "Something went wrong.";
  } catch (err) { status.textContent = "Couldn't reach the stand."; }
  e.target.value = "";
});
document.getElementById("save").addEventListener("click", async () => {
  status.textContent = "Saving...";
  try {
    const r = await fetch("/save", {method: "POST", headers: {"Content-Type": "application/json"},
                                     body: JSON.stringify({text: text.value})});
    const data = await r.json();
    status.textContent = data.saved ? (data.warning || `Saved (${data.words} words). The stand will read this story next.`) : (data.error || "Something went wrong.");
  } catch (err) { status.textContent = "Couldn't reach the stand."; }
});
</script>
</body></html>
"""

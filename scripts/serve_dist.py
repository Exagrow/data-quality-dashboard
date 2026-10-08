"""Serve dist/ the way a static host does, to check a production build locally.

The one rule that matters is the clean URL lookup (`$uri`, then `$uri.html`): Framework
builds clean URLs, so /data-quality is data-quality.html. Python's own static server
does not know that.

  uv run npm run build && uv run scripts/serve_dist.py 8087
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIST = Path(__file__).resolve().parent.parent / "dist"


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        translated = Path(super().translate_path(path))
        clean = translated.with_name(translated.name + ".html")
        return str(clean if not translated.exists() and clean.exists() else translated)

    def send_error(self, code, message=None, explain=None):
        if code == 404 and (DIST / "404.html").exists():
            body = (DIST / "404.html").read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().send_error(code, message, explain)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8087
    print(f"serving {DIST} at http://localhost:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(DIST))).serve_forever()

"""
הרצה מקומית של האתר, כמו ב-Vercel:  python dev_server.py  ->  http://localhost:8000
קבצים רגילים מוגשים כמו שהם, ו-/api/search, /api/answer מופעלים מתיקיית api.
"""
import importlib.util
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
for line in open(os.path.join(HERE, "..", ".env"), encoding="utf-8") if os.path.exists(
        os.path.join(HERE, "..", ".env")) else []:
    if "=" in line:
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)


def load_api(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "api", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.handler


API = {"/api/ask": load_api("ask")}


class Dev(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def _api(self, method):
        h = API.get(self.path.split("?")[0])
        if h and hasattr(h, method):
            getattr(h, method)(self)
            return True
        return False

    def do_GET(self):
        if not self._api("do_GET"):
            super().do_GET()

    def do_POST(self):
        if not self._api("do_POST"):
            self.send_error(404)

    def do_OPTIONS(self):
        if not self._api("do_OPTIONS"):
            self.send_error(404)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Dev).serve_forever()

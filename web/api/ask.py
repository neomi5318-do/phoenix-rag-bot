"""
/api/ask - נקודת הקצה היחידה של הבוט.

GET  -> "חימום": טוען את המודל לזיכרון כשהדף נפתח, כדי שהשאלה הראשונה תהיה מהירה.
POST -> {"question": "...", "history": [{"q": ..., "a": ...}]}
        1. מחפש באתר את 7 הקטעים הרלוונטיים (lib/retrieval.py)
        2. מנסח תשובה רק מהם, עם ציטוט מאומת ומוקד מתאים (lib/bot.py)
"""
import os
import sys
import time
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import bot, retrieval  # noqa: E402
from lib.responses import clean_history, read_json, send_cors_preflight, send_json  # noqa: E402


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        send_cors_preflight(self)

    def do_GET(self):
        t = time.time()
        retrieval.load_data()
        send_json(self, 200, {"ready": True, "ms": int((time.time() - t) * 1000)})

    def do_POST(self):
        t = time.time()
        try:
            body = read_json(self)
            question = (body.get("question") or "").strip()[:500]
            history = clean_history(body.get("history"))
            if not question:
                return send_json(self, 400, {"error": "חסרה שאלה"})

            chunks = retrieval.search(bot.search_query(question, history))
            result = bot.answer(question, history, chunks)
            result["ms"] = int((time.time() - t) * 1000)
            send_json(self, 200, result)
        except Exception as e:  # noqa: BLE001
            print("ask error:", repr(e))
            send_json(self, 503, {"error": "המערכת עמוסה כרגע. נסו שוב בעוד רגע."})

"""
השרת של הבוט (Flask). ב-Vercel הוא רץ כפונקציה אחת; הקבצים שבתיקייה public/
(הדף, הווידג'ט, הגופנים והשאלות הנפוצות) מוגשים ישירות, בלי לעבור כאן.

נקודות קצה:
  GET  /api/insights -> הנתונים לדוח "מה הלקוחות שואלים ואין לזה תשובה באתר"
  GET  /api/ask  -> "חימום": טוען את המודל לזיכרון כשהדף נפתח
  POST /api/ask  -> {"question": "...", "history": [{"q": ..., "a": ..., "urls": [...]}]}
                    1. מחפש באתר את 6 הקטעים הרלוונטיים (lib/retrieval.py)
                    2. מנסח תשובה רק מהם, עם ציטוט מאומת ומוקד מתאים (lib/bot.py)

הרצה מקומית:  python app.py  ->  http://localhost:8000
"""
import os
import time

from flask import Flask, jsonify, request, send_from_directory

from lib import bot, insights, retrieval

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(HERE, "public")

app = Flask(__name__, static_folder=None)
VERSION = os.getenv("VERCEL_GIT_COMMIT_SHA", "local")[:7]   # כדי לבדוק איזו גרסה רצה


@app.after_request
def allow_other_sites(response):
    """כדי שהווידג'ט יעבוד גם כשהוא מוטמע באתר אחר."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def clean_history(raw):
    """היסטוריית השיחה מהדפדפן: רק שאלה ותשובה, קצרות, עד 3 אחרונות."""
    out = []
    for h in (raw or [])[-3:]:
        if isinstance(h, dict) and isinstance(h.get("q"), str) and isinstance(h.get("a"), str):
            urls = [u for u in (h.get("urls") or []) if isinstance(u, str)
                    and u.startswith("https://www.fnx.co.il/")][:3]     # רק עמודים מהאתר
            out.append({"q": h["q"][:500], "a": h["a"][:1500], "urls": urls})
    return out


@app.route("/api/ask", methods=["GET", "POST", "OPTIONS"])
def ask():
    if request.method == "OPTIONS":
        return "", 204
    t = time.time()

    if request.method == "GET":                      # חימום
        retrieval.load_data()
        return jsonify(ready=True, version=VERSION, ms=int((time.time() - t) * 1000))

    try:
        body = request.get_json(silent=True) or {}
        question = str(body.get("question") or "").strip()[:500]
        history = clean_history(body.get("history"))
        if not question:
            return jsonify(error="חסרה שאלה"), 400

        chunks = bot.find_chunks(question, history)
        result = bot.answer(question, history, chunks)
        result["ms"] = int((time.time() - t) * 1000)
        if result.get("model") != "no-match":      # ג'יבריש ("???") הוא לא פער תוכן - לא נרשם בדוח
            insights.record(question, result, chunks[0]["section"] if chunks else "")
        return jsonify(result)
    except Exception as e:  # noqa: BLE001
        print("ask error:", repr(e))
        return jsonify(error="המערכת עמוסה כרגע. נסו שוב בעוד רגע."), 503


@app.route("/api/insights")
def insights_report():
    """הנתונים למסך "מה הלקוחות שואלים" (public/insights.html)."""
    try:
        return jsonify(insights.report())
    except Exception as e:  # noqa: BLE001
        print("insights report error:", repr(e))
        return jsonify(enabled=False, error="הדוח לא זמין כרגע"), 503


@app.route("/")
def home():
    return send_from_directory(PUBLIC, "index.html")


# בהרצה מקומית בלבד: מגישים גם את שאר הקבצים מ-public/ (ב-Vercel הם מוגשים ישירות)
if not os.getenv("VERCEL"):
    @app.route("/<path:name>")
    def public_file(name):
        return send_from_directory(PUBLIC, name)


if __name__ == "__main__":
    env = os.path.join(HERE, "..", ".env")
    if os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)
    app.run(port=int(os.getenv("PORT", "8000")), threaded=True)

"""עזרים קטנים לפונקציות השרת: קריאת JSON מהבקשה ושליחת JSON בחזרה."""
import json


def read_json(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    if length > 20_000:
        raise ValueError("בקשה גדולה מדי")
    return json.loads(handler.rfile.read(length) or b"{}")


def send_json(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")   # כדי שהווידג'ט יעבוד גם מאתר אחר
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def send_cors_preflight(handler):
    handler.send_response(204)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()


def clean_history(raw):
    """היסטוריית השיחה מהדפדפן: רק שאלה ותשובה, קצרות."""
    out = []
    for h in (raw or [])[-3:]:
        if isinstance(h, dict) and isinstance(h.get("q"), str) and isinstance(h.get("a"), str):
            out.append({"q": h["q"][:500], "a": h["a"][:1500]})
    return out

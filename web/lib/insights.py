"""
דוח "פערי תוכן" לפניקס: אילו שאלות לקוחות שואלים - ואין עליהן תשובה באתר.

מה נשמר (במסד Upstash Redis, שמחובר ל-Vercel):
- מונים: כמה שאלות נשאלו, וכמה מכל סטטוס (נמצא / לא נמצא / אישי).
- לכל שאלה *שלא נמצאה לה תשובה*: נוסח השאלה (אחרי מחיקת מספרים ומיילים), הנושא, ותאריך.
לא נשמרים: שם, כתובת IP, או כל פרט מזהה. מספרים ארוכים ומיילים מוחלפים ב-•••.

אם המסד לא מחובר - הבוט ממשיך לעבוד רגיל, פשוט בלי דוח.
"""
import json
import os
import re
import time
from collections import Counter

import requests

KEY = "makor:gaps"
MAX_KEEP = 1000


def _conn():
    url = os.getenv("KV_REST_API_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN")
    return (url, token) if url and token else (None, None)


def enabled():
    return _conn()[0] is not None


def _redis(*commands):
    """שולח כמה פקודות Redis בבקשה אחת (pipeline) דרך ה-REST API של Upstash."""
    url, token = _conn()
    r = requests.post(f"{url}/pipeline", json=[list(c) for c in commands], timeout=3,
                      headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return [x.get("result") for x in r.json()]


def mask(text):
    text = re.sub(r"\S+@\S+", "•••", text)
    return re.sub(r"\d[\d\- ]{4,}\d", "•••", text)


def record(question, result):
    """רושם שאלה אחת. לא מפיל את הבוט אם המסד לא זמין."""
    if not enabled():
        return
    status = result.get("status", "")
    cmds = [("INCR", "makor:total"), ("INCR", f"makor:status:{status}")]
    if status == "not_found":
        item = {"q": mask(question)[:300], "topic": result.get("department", {}).get("name", ""),
                "ts": int(time.time())}
        cmds += [("LPUSH", KEY, json.dumps(item, ensure_ascii=False)), ("LTRIM", KEY, 0, MAX_KEEP - 1)]
    try:
        _redis(*cmds)
    except Exception as e:  # noqa: BLE001
        print("insights error:", repr(e))


def report():
    """הנתונים למסך הדוח."""
    if not enabled():
        return {"enabled": False}
    total, answered, not_found, personal, raw = _redis(
        ("GET", "makor:total"), ("GET", "makor:status:answered"),
        ("GET", "makor:status:not_found"), ("GET", "makor:status:personal"),
        ("LRANGE", KEY, 0, MAX_KEEP - 1))
    gaps = [json.loads(x) for x in raw or []]
    topics = Counter(g.get("topic") or "כללי" for g in gaps)
    return {
        "enabled": True,
        "total": int(total or 0),
        "answered": int(answered or 0),
        "not_found": int(not_found or 0),
        "personal": int(personal or 0),
        "topics": topics.most_common(8),
        "recent": gaps[:40],
    }

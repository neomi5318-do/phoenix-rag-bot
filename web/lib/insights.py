"""
דוח "פערי תוכן" לפניקס: אילו שאלות לקוחות שואלים - ואין עליהן תשובה באתר.

מה נשמר (במסד Upstash Redis, שמחובר ל-Vercel):
- מונים: כמה שאלות נשאלו, וכמה מכל סטטוס (נמצא / לא נמצא / אישי).
- לכל שאלה *שלא נמצאה לה תשובה*: נוסח השאלה (אחרי מחיקת מספרים ומיילים), הנושא
  (האזור באתר שהכי קרוב לשאלה), ותאריך.
לא נשמרים: שם, כתובת IP, או כל פרט מזהה. מספרים ארוכים ומיילים מוחלפים ב-•••.
מה לא נכנס בכלל לדוח: קשקוש, שאלה של מילה אחת, ושאלה שלא קשורה לנושא (ראו worth_reporting).

אם המסד לא מחובר - הבוט ממשיך לעבוד רגיל, פשוט בלי דוח.
"""
import json
import os
import re
import time
from collections import Counter

import requests

# v2: הדוח התחיל מחדש ב-22.10.2026, עם המסנן (worth_reporting). הרשומות מלפני המסנן לא מוצגות.
PREFIX = "makor:v2"
KEY = f"{PREFIX}:gaps"
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


# הנושא של שאלה שלא נענתה = האזור באתר שהכי קרוב אליה (לפי הקטע הראשון שנמצא בחיפוש)
AREAS = {"car-insurance": "ביטוח רכב", "apartment-insurance": "ביטוח דירה", "health-insurance": "ביטוח בריאות",
         "travel-insurance": "ביטוח נסיעות לחו\"ל", "pets-insurance": "ביטוח חיות מחמד",
         "mortgage-insurance": "ביטוח משכנתא", "life-insurance": "ביטוח חיים", "pension-savings": "פנסיה",
         "pension_retirement": "פנסיה", "gemel": "קופות גמל", "savings": "חיסכון", "ishtalmutfund": "קרן השתלמות",
         "loans": "הלוואות", "claims-customer-service": "תביעות", "customer-service": "שירות לקוחות",
         "business-insurance": "ביטוח עסקים", "other-insurances": "ביטוחים נוספים",
         "marine_aviation_insurance": "ביטוח ימי ואווירי", "home": "כללי"}


def worth_reporting(question, result, chunks=()):
    """מה נכנס לדוח: רק שאלה אמיתית שקשורה לביטוח / חיסכון / שירותי הפניקס. שלושה תנאים:
    1. המודל סימן במפורש שהשאלה קשורה לנושא (on_topic) - לא בדיחה, מתכון או ניסיון לשנות כללים.
    2. לפחות מילה אחת מהשאלה מופיעה באתר הפניקס (חיפוש המילים מצא משהו) - לא קשקוש.
    3. לפחות שתי מילים.
    כך הצוות רואה רק פערים אמיתיים."""
    if result.get("model") == "no-match" or result.get("on_topic") is not True:
        return False
    if chunks and not any(c.get("keyword", 0) > 0 for c in chunks):
        return False
    return len(re.findall(r"[^\W\d_]{2,}", question)) >= 2


def mask(text):
    text = re.sub(r"\S+@\S+", "•••", text)
    return re.sub(r"\d[\d\- ]{4,}\d", "•••", text)


def record(question, result, area=""):
    """רושם שאלה אחת. לא מפיל את הבוט אם המסד לא זמין."""
    if not enabled():
        return
    status = result.get("status", "")
    cmds = [("INCR", f"{PREFIX}:total"), ("INCR", f"{PREFIX}:status:{status}")]
    if status == "not_found":
        item = {"q": mask(question)[:300], "topic": AREAS.get(area, area or "כללי"),
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
        ("GET", f"{PREFIX}:total"), ("GET", f"{PREFIX}:status:answered"),
        ("GET", f"{PREFIX}:status:not_found"), ("GET", f"{PREFIX}:status:personal"),
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

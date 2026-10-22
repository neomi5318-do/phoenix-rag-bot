"""
מטמון תשובות: שאלה שכבר נשאלה (אותה שאלה, באותו הקשר של שיחה) מקבלת את התשובה השמורה -
מיד, ובלי להשתמש במכסה של מודל השפה. למשל: התסריט מהאתגר, שהרבה אנשים ינסו.

- נשמר ב-Upstash Redis (אותו מסד של הדוח) ל-3 ימים.
- המפתח כולל את גרסת הקוד, כך שאחרי כל עדכון של הבוט המטמון מתחיל מחדש.
- אם המסד לא מחובר או לא זמין - פשוט עונים כרגיל.
"""
import hashlib
import json
import os
import re

from . import insights

TTL = 3 * 24 * 3600
VERSION = os.getenv("VERCEL_GIT_COMMIT_SHA", "local")[:7]


def _key(question, history):
    prev = history[-1] if history else {}
    raw = "|".join([re.sub(r"\s+", " ", question.strip().lower()),
                    prev.get("q", ""), ",".join(prev.get("urls", []))])
    return f"makor:cache:{VERSION}:" + hashlib.sha1(raw.encode()).hexdigest()


def get(question, history):
    if not insights.enabled():
        return None
    try:
        raw = insights._redis(("GET", _key(question, history)))[0]
        return json.loads(raw) if raw else None
    except Exception as e:  # noqa: BLE001
        print("cache get error:", repr(e))
        return None


def put(question, history, result):
    if not insights.enabled() or result.get("model") == "no-match":
        return
    try:
        insights._redis(("SET", _key(question, history), json.dumps(result, ensure_ascii=False), "EX", TTL))
    except Exception as e:  # noqa: BLE001
        print("cache put error:", repr(e))

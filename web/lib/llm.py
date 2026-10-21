"""
קריאה למודלי השפה - בקשת HTTP פשוטה, בלי ספריות של ספקים.

שני ספקים, ושניהם בחינם:
- Gemini (גוגל): עברית מצוינת. בחינם: 20 שאלות ביום לכל מודל, ובשעות עומס הוא לפעמים איטי.
- Groq: מודלים פתוחים, מהירים מאוד (כ-2 שניות). עברית טובה, מעט פחות טבעית.

איך בוחרים מודל לכל שאלה ("מירוץ מגובה"):
1. שולחים למודל הראשון ברשימה.
2. אם הוא נכשל (מכסה, עומס) - שולחים מיד לבא בתור.
3. אם הוא פשוט איטי - אחרי HEDGE_AFTER שניות שולחים *במקביל* גם לבא בתור,
   ולוקחים את התשובה שמגיעה ראשונה.
כך הלקוחה לא מחכה למודל תקוע, ועדיין מקבלת את Gemini כשהוא זמין.
מודל שנכשל "נזכר" כחסום לזמן מה, כדי לא לבזבז עליו זמן בשאלה הבאה.
"""
import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
HEDGE_AFTER = 5           # שניות - אחרי זה מתחילים במקביל גם את המודל הבא

_pool = ThreadPoolExecutor(max_workers=8)
_blocked_until = {}       # מודל -> עד מתי לא לנסות אותו


class ModelError(Exception):
    pass


def _gemini(model, system, prompt, schema, timeout=25):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ModelError("no GEMINI_API_KEY")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json",
                             "responseSchema": schema},
    }
    r = requests.post(GEMINI_URL.format(model=model), json=body, timeout=timeout,
                      headers={"x-goog-api-key": key})
    if r.status_code != 200:
        raise ModelError(f"{r.status_code} {r.text[:300]}")
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _groq(model, system, prompt, schema, timeout=25):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ModelError("no GROQ_API_KEY")
    body = {"model": model, "temperature": 0.1, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}]}
    r = requests.post(GROQ_URL, json=body, timeout=timeout,
                      headers={"Authorization": f"Bearer {key}"})
    if r.status_code != 200:
        raise ModelError(f"{r.status_code} {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


# סדר הניסיון: Gemini ו-Groq לסירוגין, כדי שהגיבוי המהיר יגיע מוקדם
CHAIN = [
    ("gemini-3.8-flash", _gemini),
    ("openai/gpt-oss-120b", _groq),
    ("gemini-3.5-flash", _gemini),
    ("openai/gpt-oss-20b", _groq),
    ("gemini-3.6-flash", _gemini),
    ("gemini-3.7-flash", _gemini),
    ("gemini-3.1-flash-lite", _gemini),
    ("qwen/qwen3.8-27b", _groq),
]


def _block(model, error):
    """כמה זמן לא לנסות שוב את המודל, לפי סוג השגיאה."""
    msg = str(error)
    if "PerDay" in msg or "per day" in msg.lower() or "TPD" in msg:
        _blocked_until[model] = time.time() + 3 * 3600   # מכסה יומית
    elif "429" in msg:
        _blocked_until[model] = time.time() + 60          # מכסה לדקה
    else:
        _blocked_until[model] = time.time() + 120         # עומס / תקלה


def generate_json(system, prompt, schema, validate):
    """מחזיר (תשובה כמילון, שם המודל). validate בודק שהמבנה תקין."""
    chain = [(m, f) for m, f in CHAIN if _blocked_until.get(m, 0) <= time.time()] or CHAIN
    running, errors = {}, []

    def launch():
        model, call = chain.pop(0)
        running[_pool.submit(call, model, system, prompt, schema)] = model

    launch()
    while running:
        done, _ = wait(running, timeout=HEDGE_AFTER if chain else None, return_when=FIRST_COMPLETED)
        if not done:                     # המודל איטי -> מפעילים במקביל את הבא בתור
            launch()
            continue
        for future in done:
            model = running.pop(future)
            try:
                data = json.loads(future.result())
                if validate(data):
                    return data, model
                errors.append(f"{model}: invalid")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{model}: {str(e)[:100]}")
                _block(model, e)
        if not running and chain:        # כולם נכשלו -> הבא בתור
            launch()
    raise ModelError("כל המודלים נכשלו: " + " | ".join(errors))

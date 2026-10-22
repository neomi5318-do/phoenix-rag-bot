"""
מריץ את התסריט מהאתגר מול הבוט (באתר החי או מקומית) ושומר את התשובות האמיתיות
ל-public/showcase.json - הדף "לצוות הפניקס" מציג אותן כמו שהן.

שימוש:  python build_showcase.py https://makor-phoenix.vercel.app
"""
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

SCRIPT = ["יש לי נזילה בבית, איך אני מגישה תביעה?", "ותוך כמה זמן מקבלים תשובה?",
          "האם הפוליסה שלי מכסה את זה?"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "showcase.json")


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
    history, turns = [], []
    for q in SCRIPT:
        t = time.time()
        r = requests.post(f"{base}/api/ask", json={"question": q, "history": history}, timeout=90).json()
        if "answer" not in r:
            raise SystemExit(f"אין תשובה ל: {q} -> {r}")
        turns.append({"question": q, "status": r["status"], "answer": r["answer"], "sources": r["sources"],
                      "department": r["department"]["name"], "seconds": round(time.time() - t, 1)})
        history.append({"q": q, "a": r["answer"], "urls": [s["url"] for s in r["sources"]]})
        print(f"{r['status']:10} {time.time() - t:4.1f}s  {q}")
        time.sleep(8)
    now = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M")
    json.dump({"recorded": now, "site": base, "turns": turns},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("נשמר:", OUT)


if __name__ == "__main__":
    main()

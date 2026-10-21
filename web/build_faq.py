"""
מכין את "שאלות נפוצות" (faq.json): מריץ כל שאלה דרך הבוט האמיתי, ושומר את התשובה.
אחרי ההרצה עוברים על התשובות ידנית, ומוחקים/מתקנים מה שלא מדויק - ולכן הן "נבדקו".

שימוש:  python build_faq.py
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for line in open(os.path.join(HERE, "..", ".env"), encoding="utf-8"):
    if "=" in line:
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

from lib import bot, retrieval  # noqa: E402

TOPICS = [
    ("תביעות ונזקים", ["יש לי נזילה בבית, איך מגישים תביעה?",
                       "מה הדבר הראשון שצריך לעשות אחרי תאונת דרכים?"]),
    ("ביטוח רכב", ["מה ההבדל בין ביטוח מקיף לביטוח צד ג'?",
                   "מי נחשב נהג צעיר ומי נחשב נהג חדש?"]),
    ("ביטוח דירה", ["באיזה אמצעי תשלום אפשר לשלם על ביטוח דירה?"]),
    ("חיות מחמד", ["מה ההשתתפות העצמית בביטוח לכלב?",
                   "אילו גזעי כלבים אי אפשר לבטח בכיסוי צד ג'?"]),
    ("נסיעות לחו\"ל", ["איך מאריכים ביטוח נסיעות כשכבר נמצאים בחו\"ל?",
                       "אפשר לקנות ביטוח נסיעות עם מחלה כרונית?"]),
]
OUT = os.path.join(HERE, "public", "faq.json")


def main():
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {"topics": []}
    done = {i["question"]: i for t in old["topics"] for i in t["items"]}
    topics = []
    for name, questions in TOPICS:
        items = []
        for q in questions:
            if q in done:
                items.append(done[q])
                continue
            time.sleep(8)                      # קצב מתון (מכסות לדקה)
            r = bot.answer(q, [], retrieval.search(q))
            print(f"[{r['status']}] {r['model']} {q}\n{r['answer']}\n", flush=True)
            if r["status"] == "answered":
                items.append({"question": q, "answer": r["answer"], "sources": r["sources"],
                              "department": r["department"]["key"]})
        topics.append({"name": name, "items": items})
        json.dump({"checked_at": "2026-10-21", "topics": topics},
                  open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

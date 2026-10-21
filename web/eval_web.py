"""
בדיקת גרסת Vercel על אותן 30 שאלות (../eval/questions.json).

שני מצבים:
  python eval_web.py retrieval   -> בודק רק את החיפוש (בלי מודל שפה, בלי מכסה):
                                    האם עמוד מהאזור הנכון ועובדת המפתח נמצאים ב-7 הקטעים?
  python eval_web.py full        -> בוט מלא, עם אותם כללי ציון כמו ב-eval.py המקורי.
תוצאות: ../eval/web_results.json
"""
import json
import re
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

QUESTIONS = json.load(open(os.path.join(HERE, "..", "eval", "questions.json"), encoding="utf-8"))
BY_ID = {q["id"]: q for q in QUESTIONS}
OUT = os.path.join(HERE, "..", "eval", "web_results.json")


def area(path):
    return "/" + path.strip("/").split("/")[0] + "/"


def history_for(q, results):
    """כמו בדפדפן: השאלה הקודמת, התשובה שלה, והעמודים שמהם ענינו."""
    if not q.get("context"):
        return []
    prev = BY_ID[q["context"]]
    r = results.get(prev["id"], {})
    return [{"q": prev["question"], "a": r.get("answer", ""),
             "urls": [s["url"] for s in r.get("sources", [])]}]


def retrieval_eval():
    hits, total = 0, 0
    for q in QUESTIONS:
        if q["type"] not in ("answerable", "follow_up") or not q.get("expected_path"):
            continue
        total += 1
        prev = BY_ID.get(q.get("context"), {}).get("expected_path")
        fake = {q["context"]: {"sources": [{"url": "https://www.fnx.co.il" + prev}]}} if prev and q.get("context") else {}
        chunks = bot.find_chunks(q["question"], history_for(q, fake))
        urls = [c["url"].split("fnx.co.il")[-1] for c in chunks]
        in_area = any(u.startswith(area(q["expected_path"])) for u in urls)
        facts = all(any(any(alt in c["text"] for alt in f.split("|")) for c in chunks)
                    for f in q.get("must_contain", []))
        ok = in_area and facts
        hits += ok
        print(f"{'✅' if ok else '❌'} {q['id']} area={in_area} facts={facts}  {q['question']}")
    print(f"\nאחזור: {hits}/{total}")


def is_pass(q, r):
    status = r["status"]
    if q.get("forbid") and re.search(q["forbid"], r["answer"].split("\n", 1)[-1].strip()):
        return False                     # למשל "כן, הפוליסה שלך מכסה" בשאלה אישית
    urls = [s["url"].split("fnx.co.il")[-1] for s in r["sources"]]
    if q["type"] == "answerable":
        if status != "answered":
            return False
        if q.get("expected_path") and not any(u.startswith(area(q["expected_path"])) for u in urls):
            return False
        return all(any(alt in r["answer"] for alt in f.split("|")) for f in q.get("must_contain", []))
    if q["type"] == "not_on_site":
        return status in ("not_found", "personal")
    if q["type"] == "boundary":
        return status in ("personal", "not_found")
    if q["type"] == "follow_up":         # אם יש תשובה מוגדרת - חייבים לענות אותה
        if q.get("must_contain"):
            return status == "answered" and all(any(a in r["answer"] for a in f.split("|"))
                                                for f in q["must_contain"])
        return status in ("answered", "not_found")
    return False


def full_eval():
    results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for q in QUESTIONS:
        if q["id"] in results:
            results[q["id"]]["pass"] = is_pass(q, results[q["id"]])
            continue
        hist = history_for(q, results)
        chunks = bot.find_chunks(q["question"], hist)
        r = None
        for attempt in range(3):          # מכסות לדקה: מחכים ומנסים שוב
            t = time.time()
            try:
                r = bot.answer(q["question"], hist, chunks)
                break
            except Exception as e:  # noqa: BLE001
                print("  ממתין למכסה:", str(e)[:120], flush=True)
                time.sleep(65)
        if r is None:
            print("עצירה:", q["id"])
            break
        r["seconds"] = round(time.time() - t, 1)
        r["question"], r["type"] = q["question"], q["type"]
        r["quotes_ok"] = sum(1 for s in r["sources"] if s["quote"])
        r["pass"] = is_pass(q, r)
        results[q["id"]] = r
        answers[q["id"]] = r["answer"]
        json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{'✅' if r['pass'] else '❌'} {q['id']} [{r['status']}] {r['model']} {r['seconds']}s "
              f"quotes {r['quotes_ok']}/{len(r['sources'])} dept={r['department']['key']}  {q['question']}",
              flush=True)
        time.sleep(10)                    # קצב מתון, כדי לא לחרוג ממכסות לדקה
    json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    passed = sum(v["pass"] for v in results.values())
    print(f"\nסה״כ: {passed}/{len(results)}")


if __name__ == "__main__":
    (full_eval if sys.argv[1:] == ["full"] else retrieval_eval)()

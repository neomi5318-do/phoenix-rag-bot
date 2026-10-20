"""
שלב 6 - הערכה: מריץ את שאלות הבדיקה (eval/questions.json) ומודד את הבוט.

מה נחשב "הצלחה" לכל סוג שאלה:
- answerable  : הבוט ענה (answered), והעמוד הצפוי נמצא בין המקורות שהוא ציין.
- not_on_site : הבוט אמר שהמידע לא באתר (not_found) - כלומר לא המציא.
- boundary    : הבוט לא נתן תשובה אישית - סטטוס personal או not_found.
- follow_up   : הבוט הבין את ההקשר מהשאלה הקודמת וענה (או אמר בכנות שאין מידע).

התוצאות נשמרות תוך כדי ריצה, כך שאם המכסה נגמרת באמצע - ההרצה הבאה ממשיכה.
פלט: eval/results.json + eval/report.md
"""
import json
import os
import time

import rag

QUESTIONS = "eval/questions.json"
RESULTS = "eval/results.json"
REPORT = "eval/report.md"


def is_pass(q, r):
    status = r["status"]
    urls = [s["url"].split("fnx.co.il")[-1] for s in r["sources"]]
    if q["type"] == "answerable":
        return status == "answered" and (not q.get("expected_path") or q["expected_path"] in urls)
    if q["type"] == "not_on_site":
        return status == "not_found"
    if q["type"] == "boundary":
        return status in ("personal", "not_found")
    if q["type"] == "follow_up":
        return status in ("answered", "not_found") and r["standalone_question"] != q["question"]
    return False


def main():
    questions = json.load(open(QUESTIONS, encoding="utf-8"))
    results = json.load(open(RESULTS, encoding="utf-8")) if os.path.exists(RESULTS) else {}
    by_id = {q["id"]: q for q in questions}

    for q in questions:
        if q["id"] in results:
            continue
        history = []
        if q.get("context"):                       # שאלת המשך: קודם השאלה שהיא ממשיכה
            prev = results.get(q["context"]) or rag.ask(by_id[q["context"]]["question"])
            history = [(prev["question"], prev["answer"])]
        try:
            r = rag.ask(q["question"], history)
        except Exception as e:
            print(f"עצירה ב-{q['id']}: {str(e)[:150]}")
            break
        r["pass"] = is_pass(q, r)
        r["type"] = q["type"]
        results[q["id"]] = r
        json.dump(results, open(RESULTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{'✅' if r['pass'] else '❌'} {q['id']} [{r['status']}] ({r['model']}) {q['question']}",
              flush=True)
        time.sleep(4)

    write_report(questions, results)


def write_report(questions, results):
    lines = ["# תוצאות הבדיקה", ""]
    by_type = {}
    for q in questions:
        if q["id"] in results:
            by_type.setdefault(q["type"], []).append(results[q["id"]]["pass"])
    names = {"answerable": "יש תשובה באתר", "not_on_site": "אין תשובה באתר (לא להמציא)",
             "boundary": "גבולות (שאלה אישית / ייעוץ)", "follow_up": "שאלות המשך"}
    total = sum(sum(v) for v in by_type.values())
    count = sum(len(v) for v in by_type.values())
    lines += [f"**סה״כ: {total}/{count} עברו**", "", "| סוג | עברו |", "|---|---|"]
    for t, v in by_type.items():
        lines.append(f"| {names.get(t, t)} | {sum(v)}/{len(v)} |")
    lines += ["", "## פירוט", ""]
    for q in questions:
        r = results.get(q["id"])
        if not r:
            continue
        lines.append(f"### {'✅' if r['pass'] else '❌'} {q['id']} · {q['question']}")
        if r["standalone_question"] != q["question"]:
            lines.append(f"*הובנה כ:* {r['standalone_question']}")
        lines.append(f"**סטטוס:** {r['status']} · **מצופה:** {q.get('note', '')}")
        lines.append("")
        lines.append("> " + r["answer"].replace("\n", "\n> "))
        for s in r["sources"]:
            lines.append(f"- מקור: {s['url']}")
        lines.append("")
    open(REPORT, "w", encoding="utf-8").write("\n".join(lines))
    print(f"\nסה״כ: {total}/{count} | הדוח נשמר ב-{REPORT}")


if __name__ == "__main__":
    main()

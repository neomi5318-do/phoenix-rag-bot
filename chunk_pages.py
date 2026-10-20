"""
שלב 2 - ניקוי וחיתוך: הופך את העמודים שנאספו לקטעים קצרים שאפשר לחפש בהם.

איך זה עובד:
1. לכל עמוד: מוציאים טקסט מה-HTML של אזור התוכן, תוך שמירה על הכותרות (h1/h2/h3).
2. מחלקים את העמוד ל"סעיפים" לפי הכותרות. שאלה נפוצה + התשובה שלה = סעיף אחד,
   כך שהן לא נחתכות זו מזו.
3. סעיפים קטנים מאותו נושא מתאחדים לקטע אחד; סעיפים ארוכים מתפצלים עם חפיפה.
4. לכל קטע מצורף "שביל" - כותרת העמוד > כותרת הסעיף - כדי שגם קטע קצר
   ("השתתפות עצמית: 250 ש״ח") יידע לאיזה נושא הוא שייך.

ניקוי:
- לא זורקים שורות קצרות (מספרי טלפון כמו *5070 הם מידע חשוב).
- זורקים בלוקים שחוזרים כמעט בכל עמוד (הסתייגות משפטית, "אולי יעניין אותך").
- עמודים כפולים (אותו טקסט בדיוק, או הפניה לאותו עמוד) נשמרים פעם אחת.
- סעיף שמופיע זהה בהרבה עמודים נשמר פעם אחת בלבד.

פלט: data/chunks.json
"""
import hashlib
import json
import re
from collections import Counter

from bs4 import BeautifulSoup

IN_FILE = "data/raw_pages.jsonl"
OUT_FILE = "data/chunks.json"

TARGET = 900        # אורך קטע רצוי, בתווים
MAX = 1400          # מעל זה מפצלים
OVERLAP = 150       # חפיפה בין חלקים של סעיף ארוך

# סעיפים שהם ניווט או המלצות קריאה, לא תוכן
SKIP_HEADINGS = ["אולי יעניין אותך", "מאמרים נוספים", "כתבות נוספות", "עוד בנושא"]
# שורות שהן כפתורים / ניווט
NOISE_LINES = {"דף הבית", "התחלת שיחה", "הזמנת שיחה", "לקבלת הצעה", "לקבלת הצעה>",
               "להגשת תביעה", "טופס תביעה", "מידע נוסף", "לדבר איתנו", "טיפים",
               "פעולות מהירות", "שאלות נפוצות", "מידע שימושי", "מה חדש", "מושגים",
               "חוקים", "|", "חיוג למוקד", "שליחת מייל"}
# שורות-קישור וזמן קריאה: "למידע נוסף על ביטוח מקיף", "3 דקות"
NOISE_PATTERN = re.compile(r"^(למידע|לפרטים)( נוסף| נוספים)?( על| בנושא)? .{0,40}>?$|^\d+(\.\d+)? ?דקות$")
# ההסתייגות המשפטית שחוזרת בתחתית רוב העמודים
DISCLAIMER = re.compile(r"מידע זה הינו כללי|תנאי הפוליסה גוברים|אינו מהווה חוות דעת|"
                        r"החברה עושה מאמצים בכדי לוודא|"
                        r"בכפוף לתהליכי הצירוף|סכומי הביטוח המפורטים צמודים")
H = "⁣H"  # סימן פנימי לתחילת כותרת


def page_lines(main_html):
    """ממיר HTML לרשימת שורות, כשכותרות מסומנות ברמה שלהן."""
    soup = BeautifulSoup(main_html, "html.parser")
    for tag in soup(["button", "form", "input", "select", "img", "picture", "iframe"]):
        tag.decompose()
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        level = int(h.name[1])
        text = h.get_text(" ", strip=True)
        h.replace_with(f"\n{H}{level} {text}\n" if text else "")
    for li in soup.find_all("li"):
        li.insert(0, "• ")
    lines = []
    for ln in soup.get_text("\n").split("\n"):
        ln = re.sub(r"\s+", " ", ln).strip()
        if not ln or ln in NOISE_LINES or ln == "•" or NOISE_PATTERN.match(ln):
            continue
        if lines and lines[-1] == ln:      # שורה כפולה רצופה (גרסת מובייל/דסקטופ)
            continue
        lines.append(ln)
    return lines


def page_sections(title, lines):
    """מחלק את השורות לסעיפים. כל סעיף: שביל כותרות + גוף."""
    path = {}          # רמה -> כותרת
    sections = []
    current = {"path": [], "body": []}
    for ln in lines:
        if ln.startswith(H):
            if current["body"]:
                sections.append(current)
            level, text = int(ln[len(H)]), ln[len(H) + 2:]
            path = {k: v for k, v in path.items() if k < level}
            path[level] = text
            current = {"path": [path[k] for k in sorted(path)], "body": []}
        else:
            current["body"].append(ln)
    if current["body"]:
        sections.append(current)

    out = []
    seen_body = set()
    for s in sections:
        if any(skip in " ".join(s["path"]) for skip in SKIP_HEADINGS):
            continue
        body = [b for b in s["body"] if not DISCLAIMER.search(b) and b != "."]
        # מחיקת כפילויות בתוך העמוד (בלוקים שמופיעים פעמיים)
        key = "\n".join(body)
        if not body or key in seen_body:
            continue
        seen_body.add(key)
        heading = " > ".join(p for p in s["path"] if p and p not in title)
        out.append({"heading": heading, "text": "\n".join(body)})
    return out


def split_long(text):
    """מפצל טקסט ארוך לחלקים, בגבולות שורה, עם חפיפה."""
    if len(text) <= MAX:
        return [text]
    parts, start = [], 0
    while start < len(text):
        end = min(start + TARGET, len(text))
        if end < len(text):
            cut = text.rfind("\n", start + TARGET // 2, end)
            if cut == -1:
                cut = text.rfind(" ", start + TARGET // 2, end)
            if cut != -1:
                end = cut
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP, start + 1)
        nl = text.find("\n", start, end)       # להתחיל חלק חדש בתחילת שורה
        if nl != -1:
            start = nl + 1
    return [p for p in parts if p]


def merge_small(sections):
    """מאחד סעיפים קטנים רצופים לקטע אחד עד לאורך היעד."""
    merged, buf = [], None
    for s in sections:
        block = (f"{s['heading']}:\n" if s["heading"] else "") + s["text"]
        if buf and len(buf["text"]) + len(block) <= TARGET:
            buf["text"] += "\n\n" + block
            if s["heading"]:
                buf["headings"].append(s["heading"])
        else:
            if buf:
                merged.append(buf)
            buf = {"text": block, "headings": [s["heading"]] if s["heading"] else []}
    if buf:
        merged.append(buf)
    return merged


def main():
    records = [json.loads(l) for l in open(IN_FILE, encoding="utf-8") if l.strip()]
    pages = [r for r in records if r.get("status") == 200 and r.get("main_html")]

    # עמודים כפולים: הפניה לאותה כתובת סופית, או אותו טקסט בדיוק
    unique, seen_final, seen_text = [], set(), set()
    for r in pages:
        final = r["final_url"].rstrip("/")
        lines = page_lines(r["main_html"])
        text_key = hashlib.sha1("\n".join(lines).encode()).hexdigest()
        if final in seen_final or text_key in seen_text:
            continue
        seen_final.add(final)
        seen_text.add(text_key)
        title = re.sub(r"\s*\|\s*הפניקס\s*$", "", r["title"]).strip()
        unique.append({**r, "title": title, "lines": lines})

    # סעיפים שחוזרים זהים בהרבה עמודים (למשל "כל הדרכים לדבר איתנו") נשמרים פעם אחת
    all_sections = [(p, page_sections(p["title"], p["lines"])) for p in unique]
    body_count = Counter(s["text"] for _, secs in all_sections for s in secs)
    kept_once = set()

    chunks = []
    for p, secs in all_sections:
        filtered = []
        for s in secs:
            if body_count[s["text"]] > 1:
                if s["text"] in kept_once:
                    continue
                kept_once.add(s["text"])
            filtered.append(s)
        for block in merge_small(filtered):
            for i, piece in enumerate(split_long(block["text"])):
                if len(piece) < 40:
                    continue
                cid = hashlib.sha1(f"{p['final_url']}|{piece}".encode()).hexdigest()[:16]
                chunks.append({
                    "id": cid,
                    "url": p["final_url"],
                    "title": p["title"],
                    "section": p["section"],
                    "headings": block["headings"],
                    "fetched_at": p["fetched_at"],
                    "text": piece,
                })

    # מזהים חייבים להיות ייחודיים
    chunks = list({c["id"]: c for c in chunks}.values())
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=1)

    lens = sorted(len(c["text"]) for c in chunks)
    print(f"עמודים שנאספו: {len(pages)} | ייחודיים: {len(unique)} | "
          f"כפולים שהוסרו: {len(pages) - len(unique)}")
    print(f"קטעים: {len(chunks)} | אורך חציוני: {lens[len(lens) // 2]} | "
          f"מינימום: {lens[0]} | מקסימום: {lens[-1]}")


if __name__ == "__main__":
    main()

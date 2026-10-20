"""
שלב 1 - איסוף: מוריד את העמודים הציבוריים של אתר הפניקס ושומר אותם כמו שהם.

עקרונות:
- אוספים פעם אחת, מעבדים הרבה פעמים: שומרים את ה-HTML של אזור התוכן (<main>),
  כדי שאפשר יהיה לשפר את הניקוי והחיתוך בלי לסרוק שוב את האתר.
- אפשר לעצור ולהמשיך: כל עמוד נכתב מיד לקובץ, ובהרצה הבאה מדלגים על מה שכבר נאסף.
- קצב מנומס: שנייה בין בקשות, ורק עמודים ציבוריים מתוך ה-sitemap.
- לכל עמוד נשמר תאריך איסוף, כדי לדעת מתי לרענן.

פלט: data/raw_pages.jsonl - שורה אחת (JSON) לכל עמוד.
"""
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

SITEMAP_URL = "https://www.fnx.co.il/sitemap.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 (phoenix-rag-bot; hackathon project)"}
OUT_FILE = "data/raw_pages.jsonl"
DELAY_SECONDS = 1.0  # קצב מנומס

# אזורים באתר שאינם מיועדים ללקוח, ולכן לא נכנסים לבוט
EXCLUDE_SECTIONS = {
    "investor-relations",  # דוחות כספיים למשקיעים
    "tags",                # עמודי תגיות - רשימות קישורים בלי תוכן
    "career",              # דרושים
    "fnx-insurance-ltd",   # עמודי תאגיד
    "en",                  # האתר באנגלית
}
EXCLUDE_WORDS = ["/404", ".pdf"]


def section_of(url):
    """האזור באתר = החלק הראשון בנתיב. למשל /car-insurance/... -> car-insurance"""
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[0] if parts else "home"


def get_urls():
    r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "xml")
    urls = [loc.text.strip() for loc in soup.find_all("loc")]
    chosen = [
        u for u in urls
        if section_of(u) not in EXCLUDE_SECTIONS
        and not any(w in u.lower() for w in EXCLUDE_WORDS)
    ]
    return list(dict.fromkeys(chosen)), len(urls)


def fetch_page(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    record = {
        "url": url,
        "final_url": r.url,  # אם הייתה הפניה, זו הכתובת שבה הסתיים
        "section": section_of(url),
        "status": r.status_code,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if r.status_code != 200:
        return record

    soup = BeautifulSoup(r.text, "html.parser")
    record["title"] = soup.title.get_text(strip=True) if soup.title else url
    main = soup.find("main") or soup.find("article") or soup.body
    for tag in main(["script", "style", "noscript", "svg"]):
        tag.decompose()
    record["main_html"] = str(main)
    return record


def already_done():
    if not os.path.exists(OUT_FILE):
        return set()
    with open(OUT_FILE, encoding="utf-8") as f:
        return {json.loads(line)["url"] for line in f if line.strip()}


def main():
    urls, total_in_sitemap = get_urls()
    done = already_done()
    todo = [u for u in urls if u not in done]
    print(f"ב-sitemap: {total_in_sitemap} | נבחרו: {len(urls)} | "
          f"כבר נאספו: {len(done)} | נותרו: {len(todo)}", flush=True)

    os.makedirs("data", exist_ok=True)
    ok = failed = 0
    with open(OUT_FILE, "a", encoding="utf-8") as out:
        for i, url in enumerate(todo, 1):
            record = None
            for attempt in range(2):  # ניסיון חוזר אחד על תקלת רשת
                try:
                    record = fetch_page(url)
                    break
                except requests.RequestException as e:
                    print(f"  תקלה ({attempt + 1}/2): {url} - {e}", flush=True)
                    time.sleep(5)
            if record is None:
                failed += 1
                continue
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            if record["status"] == 200:
                ok += 1
            else:
                failed += 1
            if i % 25 == 0 or i == len(todo):
                print(f"[{i}/{len(todo)}] תקינים: {ok} | נכשלו: {failed}", flush=True)
            time.sleep(DELAY_SECONDS)

    print(f"סיום. נאספו בהרצה הזו: {ok} | נכשלו: {failed}", flush=True)


if __name__ == "__main__":
    main()

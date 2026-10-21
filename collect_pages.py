"""
שלב 1 - איסוף: מוריד את העמודים הציבוריים של אתר הפניקס ושומר אותם כמו שהם.

עקרונות:
- אוספים פעם אחת, מעבדים הרבה פעמים: שומרים את ה-HTML של אזור התוכן (<main>),
  כדי שאפשר יהיה לשפר את הניקוי והחיתוך בלי לסרוק שוב את האתר.
- אפשר לעצור ולהמשיך: כל עמוד נכתב מיד לקובץ, ובהרצה הבאה מדלגים על מה שכבר נאסף.
- קצב מנומס: שנייה בין בקשות, ורק עמודים ציבוריים מתוך ה-sitemap.
- לכל עמוד נשמר תאריך איסוף, כדי לדעת מתי לרענן.
- חסימות: על 403 / 429 / 5xx מחכים ומנסים שוב (Exponential Backoff: 5, 15, 45 שניות,
  ואם השרת שלח Retry-After - מכבדים אותו). עמוד שנחסם לא נרשם כ"נאסף" - ינוסה בהרצה הבאה.
  לא עוקפים מנגנוני הגנה (WAF/CAPTCHA) של האתר.
- דפי JS: האתר בנוי ב-Nuxt ורוב העמודים מגיעים מהשרת כ-HTML מלא. עמוד שהתוכן שלו
  נטען רק בדפדפן (אזור התוכן ריק) מסומן empty=True ומדווח בסוף - כדי שנדע מה חסר.

פלט: data/raw_pages.jsonl - שורה אחת (JSON) לכל עמוד.
"""
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SITEMAP_URL = "https://www.fnx.co.il/sitemap.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 (phoenix-rag-bot; hackathon project)"}
OUT_FILE = "data/raw_pages.jsonl"
DELAY_SECONDS = 1.0  # קצב מנומס
RETRY_STATUS = {403, 429, 500, 502, 503, 504}   # חסימה / עומס - כדאי לנסות שוב
BACKOFF = [5, 15, 45]                           # שניות המתנה לפני כל ניסיון חוזר

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


def get_following_redirects(url, max_hops=5):
    """עוקב אחרי הפניות בעצמו, ומשדרג כל הפניה ל-http לכתובת https.
    (חלק מהעמודים באתר מפנים לכתובת http, שלא תמיד נגישה.)"""
    for _ in range(max_hops):
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308) and "Location" in r.headers:
            url = urljoin(url, r.headers["Location"])
            if url.startswith("http://"):
                url = "https://" + url[len("http://"):]
            continue
        return r
    return r


def fetch_page(url):
    r = get_following_redirects(url)
    record = {
        "url": url,
        "final_url": r.url,  # אם הייתה הפניה, זו הכתובת שבה הסתיים
        "section": section_of(url),
        "status": r.status_code,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "retry_after": r.headers.get("Retry-After"),
    }
    if r.status_code != 200:
        return record

    soup = BeautifulSoup(r.text, "html.parser")
    record["title"] = soup.title.get_text(strip=True) if soup.title else url
    main = soup.find("main") or soup.find("article") or soup.body
    for tag in main(["script", "style", "noscript", "svg"]):
        tag.decompose()
    record["main_html"] = str(main)
    record["empty"] = len(main.get_text(" ", strip=True)) < 50   # התוכן נטען ב-JS
    return record


def fetch_with_backoff(url):
    """מוריד עמוד; בחסימה או עומס מחכה ומנסה שוב, בהמתנה שגדלה בכל פעם."""
    record = None
    for attempt, pause in enumerate([0] + BACKOFF):
        if pause:
            print(f"  ניסיון {attempt + 1}: מחכה {pause} שניות ({url})", flush=True)
            time.sleep(pause)
        try:
            record = fetch_page(url)
        except requests.RequestException as e:      # תקלת רשת
            print(f"  תקלת רשת: {e}", flush=True)
            continue
        if record["status"] not in RETRY_STATUS:
            return record
        retry_after = record.get("retry_after")
        if retry_after and retry_after.isdigit() and int(retry_after) <= 120:
            time.sleep(int(retry_after))
    return record


def already_done():
    """עמודים שכבר טופלו: נאספו (200) או לא קיימים באתר (404). עמוד שנחסם - ינוסה שוב."""
    if not os.path.exists(OUT_FILE):
        return set()
    with open(OUT_FILE, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    return {r["url"] for r in records if r.get("status") in (200, 404, 410)}


def main():
    urls, total_in_sitemap = get_urls()
    done = already_done()
    todo = [u for u in urls if u not in done]
    print(f"ב-sitemap: {total_in_sitemap} | נבחרו: {len(urls)} | "
          f"כבר נאספו: {len(done)} | נותרו: {len(todo)}", flush=True)

    os.makedirs("data", exist_ok=True)
    ok = failed = empty = 0
    with open(OUT_FILE, "a", encoding="utf-8") as out:
        for i, url in enumerate(todo, 1):
            record = fetch_with_backoff(url)
            if record is None:
                failed += 1
                continue
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            if record["status"] == 200:
                ok += 1
                empty += record.get("empty", False)
            else:
                failed += 1
            if i % 25 == 0 or i == len(todo):
                print(f"[{i}/{len(todo)}] תקינים: {ok} | נכשלו: {failed}", flush=True)
            time.sleep(DELAY_SECONDS)

    print(f"סיום. נאספו בהרצה הזו: {ok} | נכשלו: {failed} | "
          f"עמודים שהתוכן שלהם נטען ב-JS (ריקים): {empty}", flush=True)


if __name__ == "__main__":
    main()

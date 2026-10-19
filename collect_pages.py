import json
import os
import time
import requests
from bs4 import BeautifulSoup

SITEMAP_URL = "https://www.fnx.co.il/sitemap.xml"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# רק אזורים שרלוונטיים ללקוח
INCLUDE = [
    "/claims-customer-service/claims-appartment-insurance/",
    "/claims-customer-service/claims-car-insurance/",
    "/apartment-insurance/",
    "/customer-service/",
    "/car-insurance/",
    "/health-insurance/",
]
# מילים שמסמנות עמודים לא רלוונטיים
EXCLUDE = ["/en/", "/tags/", "/404", "terms-of-use", "/career/"]
PER_AREA = 25        # מקסימום עמודים לכל אזור
DELAY_SECONDS = 1.0  # קצב מנומס


def get_urls():
    r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(r.text, "xml")
    urls = [loc.text.strip() for loc in soup.find_all("loc")]
    chosen = []
    for area in INCLUDE:
        area_urls = [
            u for u in urls
            if area in u and not any(x in u for x in EXCLUDE)
        ]
        chosen.extend(area_urls[:PER_AREA])
    # הסרת כפילויות תוך שמירה על סדר
    return list(dict.fromkeys(chosen))


def extract_page(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else url
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body
    text = main.get_text(separator="\n", strip=True)
    return {"url": url, "title": title, "text": text}


def main():
    urls = get_urls()
    print("כתובות שנבחרו:", len(urls))

    pages = []
    seen_texts = set()
    for i, url in enumerate(urls, 1):
        try:
            page = extract_page(url)
        except Exception as e:
            print("שגיאה:", url, e)
            continue
        if page and len(page["text"]) > 300 and page["text"][:500] not in seen_texts:
            seen_texts.add(page["text"][:500])
            pages.append(page)
            print(f"[{i}/{len(urls)}] {len(page['text'])} תווים  {url}")
        time.sleep(DELAY_SECONDS)

    os.makedirs("data", exist_ok=True)
    with open("data/pages.json", "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)
    print("נשמרו", len(pages), "עמודים")


main()
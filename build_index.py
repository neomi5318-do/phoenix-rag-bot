"""
שלב 3 - אינדקס סמנטי: הופך כל קטע לווקטור (embedding) ושומר במסד וקטורי (Chroma).

- מוסיף לאינדקס רק קטעים חדשים, ומוחק קטעים שכבר לא קיימים - כך שאפשר להריץ
  שוב ושוב אחרי איסוף מחדש, בלי לבנות הכול מאפס.
- כותרת העמוד והכותרות של הסעיף מצורפות לטקסט שמומר לווקטור, כדי שגם קטע קצר
  יימצא לפי הנושא שלו.
- על חריגה ממכסה (429) מחכים ומנסים שוב, עם המתנה שהולכת וגדלה.
"""
import json
import os
import re
import time

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768          # מספיק לאיכות טובה, וחוסך מקום פי 4 לעומת 3072
# בדרגה החינמית כל טקסט נספר כבקשה, והמגבלה היא 100 בקשות בדקה לכל מודל.
# לכן שולחים מנות של 30 טקסטים כל 21 שניות (כ-85 בדקה), עם מרווח ביטחון.
BATCH_SIZE = 30
SECONDS_PER_BATCH = 21
MAX_RETRIES = 8
DB_PATH = "chroma_db"
COLLECTION = "phoenix"


def embed_texts(texts, task_type):
    """שולח מנה של טקסטים ומחזיר רשימת וקטורים, עם ניסיון חוזר על 429."""
    wait = 65   # גם בקשה שנדחתה נספרת במכסה, אז מחכים דקה שלמה
    for attempt in range(MAX_RETRIES):
        try:
            result = client.models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=EMBED_DIM
                ),
            )
            vectors = [e.values for e in result.embeddings]
            if len(vectors) != len(texts):
                raise RuntimeError(
                    f"ציפיתי ל-{len(texts)} וקטורים וקיבלתי {len(vectors)}"
                )
            return vectors
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg:
                quota = re.findall(r"quotaId': '([^']+)'", msg)
                print(f"  מגבלת קצב {quota}, מחכה {wait} שניות...", flush=True)
                if any("PerDay" in q for q in quota):
                    raise RuntimeError("נגמרה המכסה היומית של האמבדינגים - ממשיכים מחר "
                                       "(ההרצה הבאה תמשיך מאיפה שעצרנו)")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("נכשל אחרי כמה ניסיונות - כנראה נגמרה המכסה היומית")


def embedding_text(chunk):
    """הטקסט שממנו נבנה הווקטור: כותרת העמוד + כותרות הסעיף + התוכן."""
    head = chunk["title"]
    if chunk.get("headings"):
        head += " | " + " | ".join(chunk["headings"][:3])
    return f"{head}\n{chunk['text']}"


def get_collection():
    db = chromadb.PersistentClient(path=DB_PATH)
    return db.get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def main():
    with open("data/chunks.json", encoding="utf-8") as f:
        chunks = json.load(f)
    by_id = {c["id"]: c for c in chunks}

    collection = get_collection()
    existing = set(collection.get(include=[])["ids"])

    stale = list(existing - by_id.keys())
    if stale:
        for i in range(0, len(stale), 500):
            collection.delete(ids=stale[i:i + 500])
        print(f"נמחקו מהאינדקס {len(stale)} קטעים שכבר לא קיימים")

    todo = [c for c in chunks if c["id"] not in existing]
    print(f"קטעים: {len(chunks)} | כבר באינדקס: {len(existing) - len(stale)} | "
          f"להוסיף: {len(todo)}", flush=True)

    started = time.time()
    for start in range(0, len(todo), BATCH_SIZE):
        batch_started = time.time()
        batch = todo[start:start + BATCH_SIZE]
        vectors = embed_texts([embedding_text(c) for c in batch], "RETRIEVAL_DOCUMENT")
        collection.add(
            ids=[c["id"] for c in batch],
            embeddings=vectors,
            documents=[c["text"] for c in batch],
            metadatas=[{
                "url": c["url"],
                "title": c["title"],
                "section": c["section"],
                "headings": " | ".join(c.get("headings", [])),
                "fetched_at": c["fetched_at"],
            } for c in batch],
        )
        done = min(start + BATCH_SIZE, len(todo))
        print(f"נשמרו {done}/{len(todo)} ({time.time() - started:.0f} שניות)", flush=True)
        if done < len(todo):
            time.sleep(max(0, SECONDS_PER_BATCH - (time.time() - batch_started)))

    print("האינדקס מוכן. קטעים באינדקס:", collection.count())


if __name__ == "__main__":
    main()

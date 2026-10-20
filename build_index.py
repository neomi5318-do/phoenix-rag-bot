"""
שלב 3 - אינדקס סמנטי: הופך כל קטע לווקטור (embedding) ושומר במסד וקטורי (Chroma).

- האמבדינגים מחושבים מקומית (ראו embeddings.py) - בלי מכסה ובלי עלות.
- מוסיף לאינדקס רק קטעים חדשים, ומוחק קטעים שכבר לא קיימים - כך שאפשר להריץ
  שוב אחרי איסוף מחדש, בלי לבנות הכול מאפס.
- כותרת העמוד והכותרות של הסעיף מצורפות לטקסט שמומר לווקטור, כדי שגם קטע קצר
  יימצא לפי הנושא שלו.
"""
import json
import time

import chromadb

from embeddings import MODEL_NAME, embed_passages

BATCH_SIZE = 64
DB_PATH = "chroma_db"
COLLECTION = "phoenix"


def embedding_text(chunk):
    """הטקסט שממנו נבנה הווקטור: כותרת העמוד + כותרות הסעיף + התוכן."""
    head = chunk["title"]
    if chunk.get("headings"):
        head += " | " + " | ".join(chunk["headings"][:3])
    return f"{head}\n{chunk['text']}"


def get_collection():
    db = chromadb.PersistentClient(path=DB_PATH)
    col = db.get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine", "embed_model": MODEL_NAME}
    )
    if col.metadata.get("embed_model") != MODEL_NAME:
        # אינדקס ישן שנבנה במודל אחר - וקטורים ממודלים שונים לא ניתנים להשוואה
        print("האינדקס הקיים נבנה במודל אחר - בונה מחדש")
        db.delete_collection(COLLECTION)
        col = db.create_collection(
            name=COLLECTION, metadata={"hnsw:space": "cosine", "embed_model": MODEL_NAME}
        )
    return col


def main():
    with open("data/chunks.json", encoding="utf-8") as f:
        chunks = json.load(f)
    by_id = {c["id"]: c for c in chunks}

    collection = get_collection()
    existing = set(collection.get(include=[])["ids"])

    stale = list(existing - by_id.keys())
    for i in range(0, len(stale), 500):
        collection.delete(ids=stale[i:i + 500])
    if stale:
        print(f"נמחקו מהאינדקס {len(stale)} קטעים שכבר לא קיימים")

    todo = [c for c in chunks if c["id"] not in existing]
    print(f"קטעים: {len(chunks)} | כבר באינדקס: {len(existing) - len(stale)} | "
          f"להוסיף: {len(todo)}", flush=True)

    started = time.time()
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        collection.add(
            ids=[c["id"] for c in batch],
            embeddings=embed_passages([embedding_text(c) for c in batch]),
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
        if done % 640 == 0 or done == len(todo):
            print(f"נשמרו {done}/{len(todo)} ({time.time() - started:.0f} שניות)", flush=True)

    print("האינדקס מוכן. קטעים באינדקס:", collection.count())


if __name__ == "__main__":
    main()

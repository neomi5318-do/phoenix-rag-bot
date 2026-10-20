import json
import os
import time

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
EMBED_MODEL = "gemini-embedding-001"
BATCH_SIZE = 50
PAUSE_SECONDS = 4
MAX_RETRIES = 6


def embed_texts(texts, task_type):
    """שולח מנה של טקסטים ומחזיר רשימת וקטורים, עם ניסיון חוזר על 429."""
    wait = 10
    for attempt in range(MAX_RETRIES):
        try:
            result = client.models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            vectors = [e.values for e in result.embeddings]
            if len(vectors) != len(texts):
                raise RuntimeError(
                    "ציפיתי ל-{len(texts)} וקטורים וקיבלתי {len(vectors)}"
                )
            return vectors
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                print(f"  מגבלת קצב, מחכה {wait} שניות...")
                time.sleep(wait)
                wait *= 2
            else:
                raise
    raise RuntimeError("נכשל אחרי כמה ניסיונות")


def main():
    with open("data/chunks.json", encoding="utf-8") as f:
        chunks = json.load(f)

    db = chromadb.PersistentClient(path="chroma_db")
    collection = db.get_or_create_collection(
        name="phoenix", metadata={"hnsw:space": "cosine"}
    )

    done = set(collection.get()["ids"])
    todo = [c for c in chunks if c["id"] not in done]
    print(f"סה״כ קטעים: {len(chunks)} | כבר באינדקס: {len(done)} | נותרו: {len(todo)}")

    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        # הכותרת מצורפת לטקסט כדי לשפר את האחזור
        texts = [f"{c['title']}\n{c['text']}" for c in batch]
        vectors = embed_texts(texts, "RETRIEVAL_DOCUMENT")

        collection.add(
            ids=[c["id"] for c in batch],
            embeddings=vectors,
            documents=[c["text"] for c in batch],
            metadatas=[{"url": c["url"], "title": c["title"]} for c in batch],
        )
        print(f"נשמרו {min(start + BATCH_SIZE, len(todo))}/{len(todo)}")
        time.sleep(PAUSE_SECONDS)

    print("האינדקס מוכן. קטעים באינדקס:", collection.count())


main()
"""
מכין את הנתונים לגרסת Vercel (מריצים מקומית, אחרי build_index.py של הגרסה הראשית).

קלט:  ../data/chunks.json   (הקטעים שיצר chunk_pages.py)
      ../chroma_db           (הווקטורים שיצר build_index.py עם multilingual-e5-base)
פלט:  data/chunks.json      (רק השדות שהבוט צריך)
      data/vectors.npy      (וקטור לכל קטע, באותו סדר, float16 כדי לחסוך מקום)

את הקטעים לא ממירים שוב לווקטורים - לוקחים אותם מהאינדקס הקיים (אותו מודל).
בשרת רק השאלה עוברת המרה, עם גרסה קלה של אותו מודל (lib/embedder.py).

שימוש:  python build_data.py
"""
import json
import os

import chromadb
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT_DIR = os.path.join(HERE, "data")


def main():
    chunks = json.load(open(os.path.join(ROOT, "data", "chunks.json"), encoding="utf-8"))
    slim = [{"id": c["id"], "url": c["url"], "title": c["title"], "section": c["section"],
             "headings": c.get("headings", [])[:3], "text": c["text"]} for c in chunks]

    col = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")).get_collection("phoenix")
    got = col.get(ids=[c["id"] for c in slim], include=["embeddings"])
    by_id = dict(zip(got["ids"], got["embeddings"]))
    missing = [c["id"] for c in slim if c["id"] not in by_id]
    if missing:
        raise SystemExit(f"{len(missing)} קטעים חסרים באינדקס - הריצו קודם את build_index.py")

    vectors = np.array([by_id[c["id"]] for c in slim], dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(slim, open(os.path.join(OUT_DIR, "chunks.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    np.save(os.path.join(OUT_DIR, "vectors.npy"), vectors.astype(np.float16))
    print(f"נשמרו {len(slim)} קטעים, וקטורים {vectors.shape}")


if __name__ == "__main__":
    main()

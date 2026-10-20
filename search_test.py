import os

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

EMBED_MODEL = "gemini-embedding-001"
TOP_K = 3

db = chromadb.PersistentClient(path="chroma_db")
collection = db.get_collection("phoenix")


def search(question):
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=question,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    vector = result.embeddings[0].values
    return collection.query(query_embeddings=[vector], n_results=TOP_K)


questions = [
    "יש לי נזילה בבית, איך אני מגישה תביעה?",
    "תוך כמה זמן מקבלים תשובה על תביעה?",
    "כמה עולה ביטוח לכלב?",
]

for q in questions:
    print("=" * 70)
    print("שאלה:", q)
    res = search(q)
    for i in range(len(res["ids"][0])):
        dist = res["distances"][0][i]
        meta = res["metadatas"][0][i]
        print(f"\n--- תוצאה {i+1} (מרחק {dist:.3f}) ---")
        print(meta["url"])
        print(res["documents"][0][i][:300])
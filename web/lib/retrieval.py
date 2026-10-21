"""
אחזור: מוצא את הקטעים מהאתר שהכי רלוונטיים לשאלה.

שתי שיטות חיפוש, ואז מיזוג:
1. חיפוש סמנטי - השאלה הופכת לווקטור, ומשווים אותו לווקטורים של כל הקטעים.
   מוצא גם ניסוחים אחרים ("נזילה" ~ "נזקי מים").
2. חיפוש מילות מפתח (BM25) - האלגוריתם הקלאסי של מנועי חיפוש.
   תופס מונחים מדויקים ("אמסטף", "השתתפות עצמית").
3. מיזוג RRF - כל קטע מקבל ניקוד לפי המקום שלו בכל רשימה: 1/(60+מקום).
   קטע שמופיע גבוה בשתי הרשימות - עולה לראש.
"""
import json
import os
import re

import numpy as np
from rank_bm25 import BM25Okapi

from . import embedder

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
VECTOR_K = 15
KEYWORD_K = 15
FINAL_K = 6
HEB_PREFIXES = "והבלמשכ"

_chunks = None
_vectors = None
_bm25 = None


def tokenize(text):
    """פירוק למילים לחיפוש מילות מפתח. בעברית מוסיפים גם את המילה בלי אות השימוש
    שבתחילתה (״לכלב״ -> גם ״כלב״), כי אין לנו מנתח מורפולוגי."""
    words = re.findall(r"[א-תa-zA-Z0-9]+", text.lower())
    tokens = []
    for w in words:
        tokens.append(w)
        if len(w) >= 4 and w[0] in HEB_PREFIXES:
            tokens.append(w[1:])
            if len(w) >= 5 and w[1] == "ה":       # ״בהשתתפות״ -> ״השתתפות״
                tokens.append(w[2:])
    return tokens


def load_chunks():
    """רק הטקסטים של הקטעים (מהיר - בלי וקטורים)."""
    global _chunks
    if _chunks is None:
        with open(os.path.join(DATA_DIR, "chunks.json"), encoding="utf-8") as f:
            _chunks = json.load(f)
    return _chunks


def load_data():
    """טוען את הקטעים, הווקטורים, אינדקס מילות המפתח והמודל (פעם אחת לכל שרת)."""
    global _vectors, _bm25
    load_chunks()
    if _vectors is None:
        _vectors = np.load(os.path.join(DATA_DIR, "vectors.npy")).astype(np.float32)
        _bm25 = BM25Okapi([tokenize(f"{c['title']} {' '.join(c['headings'])} {c['text']}")
                           for c in _chunks])
    embedder.load()


def chunks_by_ids(ids):
    index = {c["id"]: c for c in load_chunks()}
    return [index[i] for i in ids if i in index]


def search(query, final_k=FINAL_K):
    """מחזיר את final_k הקטעים הטובים ביותר לשאלה, מהטוב לפחות טוב."""
    load_data()

    q = embedder.embed_query(query)
    similarity = _vectors @ q                          # דמיון לכל קטע (מכפלה פנימית)
    vec_rank = np.argsort(-similarity)[:VECTOR_K]

    scores = _bm25.get_scores(tokenize(query))
    kw_rank = [i for i in np.argsort(-scores)[:KEYWORD_K] if scores[i] > 0]

    fused = {}
    for rank, i in enumerate(vec_rank):
        fused[int(i)] = fused.get(int(i), 0) + 1 / (60 + rank)
    for rank, i in enumerate(kw_rank):
        fused[int(i)] = fused.get(int(i), 0) + 1 / (60 + rank)

    best = sorted(fused, key=lambda i: -fused[i])[:final_k]
    return [{**_chunks[i], "similarity": float(similarity[i])} for i in best]

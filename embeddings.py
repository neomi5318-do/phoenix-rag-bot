"""
מודל האמבדינג: multilingual-e5-base - מודל פתוח שרץ מקומית על המחשב.

למה מקומי ולא Gemini:
- בדרגה החינמית של Gemini מותרות 1,000 הטמעות ביום, והאתר הוא כ-4,600 קטעים.
- מקומי = אין מכסה, אין עלות, והבוט לא תלוי בשירות חיצוני בשביל החיפוש.
- המודל תומך בעברית (100 שפות), שוקל כ-1GB, ויורד אוטומטית בהרצה הראשונה.

מודלי e5 דורשים קידומת: "query: " לשאלה, "passage: " לקטע מהאתר.
"""
from functools import lru_cache

MODEL_NAME = "intfloat/multilingual-e5-base"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME, device="cpu")


def embed_passages(texts, batch_size=16):
    vecs = _model().encode([f"passage: {t}" for t in texts], batch_size=batch_size,
                           normalize_embeddings=True, show_progress_bar=False)
    return vecs.tolist()


def embed_query(text):
    return _model().encode(f"query: {text}", normalize_embeddings=True).tolist()

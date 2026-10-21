"""
הופך טקסט לווקטור (embedding) - בלי PyTorch, עם ONNX Runtime.

המודל: multilingual-e5-base של intfloat - אותו מודל בדיוק שבנה את האינדקס -
בגרסה "מכווצת" (quantized int8, כ-280MB, במקום 1.1GB) ובפורמט ONNX, כדי שירוץ בשרת קטן.
הקטעים מהאתר עברו המרה לווקטורים פעם אחת מראש (data/vectors.npy), ובשרת רק השאלה עוברת המרה.
נבדק מול גרסה קטנה יותר (e5-small): שתיהן מוצאות את המידע, ו-base מדרג אותו גבוה יותר.

איך זה עובד, ב-4 צעדים:
1. tokenizer מפרק את הטקסט ל"טוקנים" (חלקי מילים) ומספרים.
2. המודל מחזיר וקטור לכל טוקן.
3. ממצעים את כל הווקטורים של הטוקנים (mean pooling) -> וקטור אחד לכל הטקסט.
4. מנרמלים לאורך 1 - כך שמכפלה פשוטה בין שני וקטורים = הדמיון ביניהם (cosine).

מודלי e5 דורשים קידומת: "query: " לשאלה, "passage: " לקטע מהאתר.
"""
import os
import urllib.request

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

MODEL_REPO = os.getenv("EMBED_MODEL_REPO", "Xenova/multilingual-e5-base")
MAX_TOKENS = 512

_session = None
_tokenizer = None


def _download(filename, dest_dir):
    """מוריד קובץ מ-Hugging Face פעם אחת, ושומר אותו (בשרת: בתיקיית /tmp)."""
    path = os.path.join(dest_dir, filename.replace("/", "_"))
    if not os.path.exists(path):
        os.makedirs(dest_dir, exist_ok=True)
        url = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{filename}"
        tmp = path + ".part"
        urllib.request.urlretrieve(url, tmp)
        os.replace(tmp, path)
    return path


def load(model_dir=None):
    """טוען את המודל לזיכרון (פעם אחת לכל שרת). מחזיר True כשמוכן."""
    global _session, _tokenizer
    if _session is not None:
        return True
    model_dir = model_dir or os.getenv("EMBED_MODEL_DIR", "/tmp/e5")
    onnx_path = _download("onnx/model_quantized.onnx", model_dir)
    tok_path = _download("tokenizer.json", model_dir)

    _tokenizer = Tokenizer.from_file(tok_path)
    _tokenizer.enable_truncation(MAX_TOKENS)
    _tokenizer.enable_padding()
    options = ort.SessionOptions()
    options.intra_op_num_threads = int(os.getenv("EMBED_THREADS", "2"))
    _session = ort.InferenceSession(onnx_path, options, providers=["CPUExecutionProvider"])
    return True


def embed(texts, prefix):
    """רשימת טקסטים -> מטריצה של וקטורים מנורמלים (שורה לכל טקסט)."""
    load()
    enc = _tokenizer.encode_batch([prefix + t for t in texts])
    ids = np.array([e.ids for e in enc], dtype=np.int64)
    mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
    feeds = {"input_ids": ids, "attention_mask": mask}
    if "token_type_ids" in [i.name for i in _session.get_inputs()]:
        feeds["token_type_ids"] = np.zeros_like(ids)
    tokens = _session.run(None, feeds)[0]                 # [טקסטים, טוקנים, ממדים]

    m = mask[..., None].astype(np.float32)                # ממצעים רק טוקנים אמיתיים
    vectors = (tokens * m).sum(axis=1) / m.sum(axis=1)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def embed_query(text):
    return embed([text], "query: ")[0]


def embed_passages(texts):
    return embed(texts, "passage: ")

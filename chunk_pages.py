import json
import re

CHUNK_SIZE = 800      # אורך קטע בתווים (בערך)
OVERLAP = 150         # חפיפה בין קטעים
MIN_LINE = 25         # שורות קצרות מזה נחשבות רעש

def clean_text(text):
    lines = [ln.strip() for ln in text.split("\n")]
    kept = []
    seen = set()
    for ln in lines:
        if len(ln) < MIN_LINE:
            continue
        if ln in seen:  # שורה שכבר הופיעה בעמוד
            continue
        seen.add(ln)
        kept.append(ln)
    return "\n".join(kept)
def split_text(text):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        # לנסות לסיים בסוף משפט או שורה
        if end < len(text):
            cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if cut > start + CHUNK_SIZE // 2:
                end = cut + 1
        piece = text[start:end].strip()
        if len(piece) > 100:
            chunks.append(piece)
        if end >= len(text):
            break
        start = end - OVERLAP
    return chunks


def main():
    with open("data/pages.json", encoding="utf-8") as f:
        pages = json.load(f)

    all_chunks = []
    for page in pages:
        text = clean_text(page["text"])
        for i, piece in enumerate(split_text(text)):
            all_chunks.append({
                "id": f"{len(all_chunks)}",
                "url": page["url"],
                "title": page["title"],
                "text": piece,
            })

    with open("data/chunks.json", "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print("עמודים:", len(pages))
    print("קטעים:", len(all_chunks))
    print("\nדוגמה לקטע:\n")
    print(all_chunks[0]["title"])
    print(all_chunks[0]["text"][:500])


main()
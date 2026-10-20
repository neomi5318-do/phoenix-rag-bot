"""
מעלה את הבוט ל-Hugging Face Space.

שימוש:
    HF_TOKEN=... python deploy/deploy_space.py <user>/<space-name>

מה עולה: קוד הבוט, האינדקס (chroma_db) וקובץ הקטעים - בלי שלבי האיסוף,
כי ה-Space רק עונה על שאלות. מפתח Gemini לא עולה: מגדירים אותו
ב-Space כסוד (Settings -> Variables and secrets -> GEMINI_API_KEY).
"""
import os
import shutil
import sys
import tempfile

from huggingface_hub import HfApi

FILES = ["app.py", "rag.py", "embeddings.py", "data/chunks.json"]
REQUIREMENTS = ["python-dotenv==1.2.3", "google-genai==2.31.0", "chromadb==1.5.9",
                "rank-bm25==0.2.2", "sentence-transformers==6.1.0", "streamlit==1.66.0"]


def main():
    repo_id = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with tempfile.TemporaryDirectory() as tmp:
        for f in FILES:
            os.makedirs(os.path.join(tmp, os.path.dirname(f)), exist_ok=True)
            shutil.copy(os.path.join(root, f), os.path.join(tmp, f))
        shutil.copytree(os.path.join(root, "chroma_db"), os.path.join(tmp, "chroma_db"))
        shutil.copy(os.path.join(root, "deploy", "Dockerfile"), os.path.join(tmp, "Dockerfile"))
        shutil.copy(os.path.join(root, "deploy", "SPACE_README.md"), os.path.join(tmp, "README.md"))
        with open(os.path.join(tmp, "requirements.txt"), "w") as f:
            f.write("\n".join(REQUIREMENTS) + "\n")
        with open(os.path.join(tmp, ".gitattributes"), "w") as f:
            f.write("*.sqlite3 filter=lfs diff=lfs merge=lfs -text\n"
                    "*.bin filter=lfs diff=lfs merge=lfs -text\n"
                    "chunks.json filter=lfs diff=lfs merge=lfs -text\n")

        api = HfApi(token=os.environ["HF_TOKEN"])
        api.upload_folder(folder_path=tmp, repo_id=repo_id, repo_type="space",
                          commit_message="Deploy Phoenix RAG bot")
    print(f"הועלה. הכתובת: https://huggingface.co/spaces/{repo_id}")


if __name__ == "__main__":
    main()

"""
שלב 5 - ממשק הצ'אט. הפעלה:  streamlit run app.py

המפתח של Gemini נקרא מהקובץ .env (בהרצה מקומית), או מה-Secrets של
Streamlit Community Cloud (בהרצה בענן).
"""
import os

import streamlit as st

try:
    if "GEMINI_API_KEY" in st.secrets and not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass  # אין קובץ secrets - מריצים מקומית עם .env

import rag  # noqa: E402  (אחרי שהמפתח הוגדר)

st.set_page_config(page_title="הבוט של אתר הפניקס", page_icon="💬", layout="centered")

st.markdown("""
<style>
  html, body, [class*="css"], .stMarkdown, .stChatMessage, .stTextInput, textarea {
      direction: rtl; text-align: right; }
  .stChatMessage { flex-direction: row-reverse; }
  .src a { text-decoration: none; }
  .src { font-size: 0.85rem; opacity: 0.85; margin-top: 0.4rem; }
  .badge { display: inline-block; font-size: 0.75rem; padding: 1px 8px; border-radius: 10px;
           margin-bottom: 4px; background: rgba(128,128,128,0.15); }
</style>
""", unsafe_allow_html=True)

st.title("💬 הבוט של אתר הפניקס")
st.caption("עונה רק מתוך המידע שבאתר fnx.co.il, עם קישור למקור. "
           "על פוליסה או תביעה אישית - פונים לשירות הלקוחות.")

BADGES = {"answered": "✅ נמצא באתר", "not_found": "ℹ️ לא מופיע באתר",
          "personal": "👤 שאלה אישית"}
EXAMPLES = ["יש לי נזילה בבית, איך אני מגישה תביעה?",
            "מה ההשתתפות העצמית בביטוח לכלב?",
            "מה ההבדל בין ביטוח מקיף לביטוח צד ג'?"]


@st.cache_resource(show_spinner="טוען את האינדקס...")
def init():
    rag.load_index()
    return True


init()

if "messages" not in st.session_state:
    st.session_state.messages = []   # כל הודעה: role, content, ועבור הבוט גם status/sources


def render_bot(msg):
    st.markdown(f'<span class="badge">{BADGES.get(msg["status"], "")}</span>',
                unsafe_allow_html=True)
    st.markdown(msg["content"])
    if msg.get("sources"):
        links = " · ".join(f'<a href="{s["url"]}" target="_blank">{s["title"]}</a>'
                           for s in msg["sources"])
        st.markdown(f'<div class="src">📎 המקור: {links}</div>', unsafe_allow_html=True)


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        render_bot(m) if m["role"] == "assistant" else st.markdown(m["content"])

if not st.session_state.messages:
    st.write("אפשר להתחיל משאלה לדוגמה:")
    cols = st.columns(len(EXAMPLES))
    for col, ex in zip(cols, EXAMPLES):
        if col.button(ex, use_container_width=True):
            st.session_state.pending = ex
            st.rerun()

question = st.chat_input("מה תרצי לדעת?") or st.session_state.pop("pending", None)

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    history = []
    msgs = st.session_state.messages[:-1]
    for q, a in zip(msgs[::2], msgs[1::2]):
        history.append((q["content"], a["content"]))

    with st.chat_message("assistant"):
        with st.spinner("מחפש באתר..."):
            try:
                r = rag.ask(question, history)
                msg = {"role": "assistant", "content": r["answer"],
                       "status": r["status"], "sources": r["sources"]}
            except Exception as e:
                msg = {"role": "assistant", "status": "not_found", "sources": [],
                       "content": "מצטער, הייתה תקלה זמנית בחיבור למודל. נסו שוב בעוד רגע."}
                print("error:", e)
        render_bot(msg)
    st.session_state.messages.append(msg)

if st.session_state.messages:
    if st.button("🗑️ שיחה חדשה"):
        st.session_state.messages = []
        st.rerun()

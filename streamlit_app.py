import streamlit as st
import requests
import pandas as pd
import json
import uuid
from sqlalchemy import create_engine, text

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Asisten Keuangan UKM", page_icon="💬", layout="wide")

# ─── Session State Init ─────────────────────────────────────────────────────────
def _init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

_init_state()
# ───────────────────────────────────────────────────────────────────────────────

USER_ID = "29b17d18-c122-4b9f-8b1f-265e7b797e87"


# --- Database Setup ---
@st.cache_resource
def get_db_engine():
    url = (
        f"postgresql+psycopg://{st.secrets['DB_USER']}:{st.secrets['DB_PASS']}"
        f"@{st.secrets['DB_HOST']}:{st.secrets['DB_PORT']}/{st.secrets['DB_NAME']}"
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=2,
        max_overflow=1,
        pool_timeout=10,
    )


@st.cache_data(ttl=60)
def fetch_transactions(limit: int = 100) -> pd.DataFrame:
    try:
        engine = get_db_engine()
        query = text("""
            SELECT date, type, amount, account_name, category_name, description
            FROM public.transactions
            WHERE is_deleted = FALSE
            ORDER BY date DESC
            LIMIT :limit
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn, params={"limit": limit})
    except Exception as e:
        st.error(f"Gagal ambil data: {e}")
        return pd.DataFrame()


# ─── Agent Call ─────────────────────────────────────────────────────────────────
def call_agent(message: str, session_id: str) -> str:
    url = f"{st.secrets['BACKEND_HOST']}/agents/asisten-keuangan-ukm/runs"
    dependencies = json.dumps({
        "user_timezone": "Asia/Jakarta"
    })

    try:
        resp = requests.post(
            url,
            files={
                "message":      (None, message),
                "session_id":   (None, session_id),
                "user_id":      (None, USER_ID),
                "stream":       (None, "false"),
                # "dependencies": (None, dependencies),
            },
            timeout=100,
        )
        if resp.status_code == 200:
            return resp.json().get("content", "No response")
        st.error(f"Status {resp.status_code}: {resp.text[:300]}")
        return f"⚠️ Error {resp.status_code}."
    except requests.Timeout:
        st.error("Request timeout — agent terlalu lama merespon.")
        return "⚠️ Agent timeout."
    except Exception as e:
        st.error(f"Exception saat call agent: {e}")
        return "⚠️ Agent tidak merespon."


# ─── Main ────────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["💬 Chat", "🗄️ Database"])

with tab1:
    st.subheader("💬 Asisten Keuangan UKM")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Tulis pesan..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Memproses..."):
                reply = call_agent(prompt, st.session_state.session_id)
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})

with tab2:
    st.subheader("🗄️ Database: `transactions`")

    if st.button("🔄 Refresh"):
        fetch_transactions.clear()
        st.rerun()

    df = fetch_transactions(limit=500)
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        col1, col2 = st.columns(2)
        col1.metric("Pemasukan", f"Rp {df[df['type']=='INCOME']['amount'].sum():,.0f}")
        col2.metric("Pengeluaran", f"Rp {df[df['type']=='EXPENSE']['amount'].sum():,.0f}")
    else:
        st.info("Data kosong.")
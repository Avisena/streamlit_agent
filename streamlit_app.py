import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Asisten Keuangan UKM", page_icon="💬", layout="wide")

# ─── Session State Init — HARUS dipanggil sebelum sidebar/UI lain dirender ──────
def _init_state():
    if "sessions" not in st.session_state:
        st.session_state.sessions = {}
    if "current_session" not in st.session_state:
        st.session_state.current_session = None
    if "session_counter" not in st.session_state:
        st.session_state.session_counter = 1

_init_state()
# ───────────────────────────────────────────────────────────────────────────────

USER_ID = "29b17d18-c122-4b9f-8b1f-265e7b797e87"
SESSION_ID = "66617d18-c122-4b9f-8b1f-265e7b797666"

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
    try:
        resp = requests.post(
            url,
            files={
                "message":    (None, message),
                "session_id": (None, SESSION_ID),
                "user_id":    (None, USER_ID),
                "stream":     (None, "false"),
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


# ─── Session Helpers ─────────────────────────────────────────────────────────────
def create_session():
    sid = str(st.session_state.session_counter)
    st.session_state.session_counter += 1
    st.session_state.sessions[sid] = {
        "id": sid,
        "name": f"Chat {sid}",
        "messages": [],
        "created_at": datetime.now().strftime("%d %b, %H:%M"),
    }
    st.session_state.current_session = sid


# ─── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💬 Sesi Chat")

    if st.button("➕ Sesi Baru", use_container_width=True, type="primary"):
        create_session()
        st.rerun()

    st.divider()

    for sid, sesh in list(st.session_state.sessions.items()):
        is_active = st.session_state.current_session == sid
        if st.button(
            sesh["name"],
            key=f"btn_{sid}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.current_session = sid
            st.rerun()


# ─── Main ────────────────────────────────────────────────────────────────────────
if st.session_state.current_session is None:
    st.title("👋 Pilih atau buat sesi di sidebar")
else:
    sesh = st.session_state.sessions[st.session_state.current_session]
    tab1, tab2 = st.tabs(["💬 Chat", "🗄️ Database"])

    with tab1:
        st.subheader(f"💬 {sesh['name']}")

        for msg in sesh["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Tulis pesan..."):
            sesh["messages"].append({"role": "user", "content": prompt})
            with st.spinner("Memproses..."):
                reply = call_agent(prompt, sesh["id"])
            sesh["messages"].append({"role": "assistant", "content": reply})
            st.rerun()

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

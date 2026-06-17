import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Asisten Keuangan UKM", page_icon="💬", layout="wide")

# ─── INI YANG HARUS DIPINDAH KE ATAS ───────────────────────────────────────────
def _init_state():
    if "sessions" not in st.session_state: st.session_state.sessions = {}
    if "current_session" not in st.session_state: st.session_state.current_session = None
    if "session_counter" not in st.session_state: st.session_state.session_counter = 1

_init_state() # <--- WAJIB DIPANGGIL DI SINI, SEBELUM SIDEBAR DI-RENDER
# ───────────────────────────────────────────────────────────────────────────────

# --- Database Setup ---
@st.cache_resource
def get_db_engine():
    url = f"postgresql+psycopg://{st.secrets['DB_USER']}:{st.secrets['DB_PASS']}@{st.secrets['DB_HOST']}:{st.secrets['DB_PORT']}/{st.secrets['DB_NAME']}"
    return create_engine(url, pool_pre_ping=True)

@st.cache_data(ttl=60)
def fetch_transactions(limit: int = 100):
    try:
        engine = get_db_engine()
        query = text("""
            SELECT date, type, amount, account_name, category_name, description
            FROM public.transactions
            ORDER BY date DESC
            LIMIT :limit
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn, params={"limit": limit})
    except:
        return pd.DataFrame()

# ─── Agent Call ─────────────────────────────────────────────────────────────────
def call_agent(message: str, session_id: str) -> str:
    url = f"{st.secrets['BACKEND_HOST']}/agents/asisten-keuangan-ukm/runs"
    try:
        resp = requests.post(
            url,
            files={"message": (None, message), "session_id": (None, session_id), "user_id": (None, "666"), "stream": (None, "false")},
            timeout=10
        )
        return resp.json().get("content", "No response") if resp.status_code == 200 else "Error."
    except:
        return "⚠️ Agent tidak merespon."
    
# ─── UI Helpers ─────────────────────────────────────────────────────────────────
def _init_state():
    if "sessions" not in st.session_state: st.session_state.sessions = {}
    if "current_session" not in st.session_state: st.session_state.current_session = None
    if "session_counter" not in st.session_state: st.session_state.session_counter = 1

def create_session():
    sid = str(st.session_state.session_counter)
    st.session_state.session_counter += 1
    st.session_state.sessions[sid] = {"id": sid, "name": f"Chat {sid}", "messages": [], "created_at": datetime.now().strftime("%d %b, %H:%M")}
    st.session_state.current_session = sid
    st.rerun()

# ─── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💬 Sesi Chat")
    if st.button("➕ Sesi Baru", use_container_width=True, type="primary"): create_session()
    for sid, sesh in list(st.session_state.sessions.items()):
        if st.button(sesh['name'], key=f"btn_{sid}", use_container_width=True):
            st.session_state.current_session = sid
            st.rerun()

# ─── Main ────────────────────────────────────────────────────────────────────────
_init_state()

if st.session_state.current_session:
    sesh = st.session_state.sessions[st.session_state.current_session]
    tab1, tab2 = st.tabs(["💬 Chat", "🗄️ Database"])
    
    with tab1:
        st.subheader(f"💬 {sesh['name']}")
        for msg in sesh["messages"]:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
        
        if prompt := st.chat_input("Tulis pesan..."):
            sesh["messages"].append({"role": "user", "content": prompt})
            with st.spinner("..."):
                reply = call_agent(prompt, sesh["id"])
                sesh["messages"].append({"role": "assistant", "content": reply})
            st.rerun()

    with tab2:
        st.subheader("🗄️ Database: `transactions`")
        if st.button("🔄 Refresh"): fetch_transactions.clear(); st.rerun()
        
        df = fetch_transactions(limit=500)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            col1, col2 = st.columns(2)
            col1.metric("Pemasukan", f"Rp {df[df['type']=='INCOME']['amount'].sum():,.0f}")
            col2.metric("Pengeluaran", f"Rp {df[df['type']=='EXPENSE']['amount'].sum():,.0f}")
        else:
            st.info("Data kosong.")
else:
    st.title("👋 Pilih sesi di sidebar")

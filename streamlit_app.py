import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Asisten Keuangan UKM",
    page_icon="💬",
    layout="wide",
)

@st.cache_resource
def get_db_engine():
    # URL disederhanakan
    url = f"mysql+pymysql://{st.secrets['DB_USER']}:{st.secrets['DB_PASS']}@{st.secrets['DB_HOST']}:{st.secrets['DB_PORT']}/{st.secrets['DB_NAME']}"
    # Langsung return engine tanpa parameter pool yang aneh-aneh
    return create_engine(url)

@st.cache_data(ttl=60)
def fetch_transactions(limit: int = 100) -> pd.DataFrame:
    try:
        engine = get_db_engine()
        # Sekarang :limit bisa digunakan di query
        query = text("""
            SELECT date, type, amount, account_name, category_name, description 
            FROM transactions 
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
    """Kirim pesan ke agent, return teks balasan."""
    url = f"{st.secrets['BACKEND_HOST']}/agents/asisten-keuangan-ukm/runs"
    try:
        resp = requests.post(
            url,
            files={
                "message":    (None, message),
                "session_id": (None, session_id),
                "user_id":    (None, "666"),
                "stream":     (None, "false"),
            },
            headers={"accept": "application/json"},
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("content") or data.get("message") or "Tidak ada balasan."
        return f"⚠️ Error {resp.status_code}: {resp.text[:200]}"
    except requests.Timeout:
        return "⚠️ Request timeout. Coba lagi."
    except Exception as e:
        return f"⚠️ {e}"


# ─── Session Helpers ─────────────────────────────────────────────────────────────
def _init_state():
    if "sessions" not in st.session_state:
        st.session_state.sessions = {}
    if "current_session" not in st.session_state:
        st.session_state.current_session = None
    if "session_counter" not in st.session_state:
        st.session_state.session_counter = 1


def create_session() -> str:
    sid = str(st.session_state.session_counter)
    st.session_state.session_counter += 1
    st.session_state.sessions[sid] = {
        "id":         sid,
        "name":       f"Chat {sid}",
        "messages":   [],
        "created_at": datetime.now().strftime("%d %b %Y, %H:%M"),
    }
    st.session_state.current_session = sid
    return sid


def delete_session(sid: str):
    st.session_state.sessions.pop(sid, None)
    if st.session_state.current_session == sid:
        remaining = list(st.session_state.sessions)
        st.session_state.current_session = remaining[-1] if remaining else None


# ─── Sidebar ─────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.title("💬 Sesi Chat")

        if st.button("➕ Sesi Baru", use_container_width=True, type="primary"):
            create_session()
            st.rerun()

        st.divider()

        for sid, sesh in list(st.session_state.sessions.items()):
            is_active = st.session_state.current_session == sid
            col_btn, col_del = st.columns([5, 1])

            with col_btn:
                if st.button(
                    f"{'▶ ' if is_active else ''}{sesh['name']}",
                    key=f"open_{sid}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state.current_session = sid
                    st.rerun()

            with col_del:
                if st.button("🗑", key=f"del_{sid}", help="Hapus sesi"):
                    delete_session(sid)
                    st.rerun()

            st.caption(sesh["created_at"])
            st.divider()


# ─── Chat Tab ────────────────────────────────────────────────────────────────────
def render_chat(sesh: dict):
    st.subheader(f"💬 {sesh['name']}")

    # Render riwayat pesan
    for msg in sesh["messages"]:
        avatar = "👤" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Input
    prompt = st.chat_input("Tulis pesan...")
    if not prompt:
        return

    # Tampilkan pesan user
    sesh["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Panggil agent
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Memproses..."):
            reply = call_agent(prompt, sesh["id"])
        st.markdown(reply)

    sesh["messages"].append({"role": "assistant", "content": reply})

    # ✅ Tidak clear cache di sini — biarkan TTL yang urus
    st.rerun()


# ─── Database Tab ────────────────────────────────────────────────────────────────
def render_database():
    st.subheader("🗄️ Database: `transactions`")

    col_refresh, col_limit, _ = st.columns([1, 2, 5])
    with col_refresh:
        if st.button("🔄 Refresh"):
            fetch_transactions.clear()
            st.rerun()
    with col_limit:
        limit = st.selectbox("Tampilkan", [100, 500, 1000, 5000], index=1, label_visibility="collapsed")

    df = fetch_transactions(limit=limit)

    if df.empty:
        st.info("Belum ada transaksi.")
        return

    # Metrics
    income  = df[df["type"] == "INCOME"]["amount"].sum()
    expense = df[df["type"] == "EXPENSE"]["amount"].sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Pemasukan",  f"Rp {income:,.0f}")
    m2.metric("💸 Pengeluaran", f"Rp {expense:,.0f}")
    m3.metric("📊 Saldo",       f"Rp {income - expense:,.0f}")
    m4.metric("🔢 Transaksi",   f"{len(df):,}")

    st.divider()

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "date":          st.column_config.DateColumn("Tanggal", format="DD MMM YYYY"),
            "amount":        st.column_config.NumberColumn("Nominal (Rp)", format="Rp %d"),
            "type":          st.column_config.TextColumn("Tipe"),
            "account_name":  st.column_config.TextColumn("Akun"),
            "category_name": st.column_config.TextColumn("Kategori"),
            "description":   st.column_config.TextColumn("Keterangan"),
        },
    )


# ─── Main ────────────────────────────────────────────────────────────────────────
def main():
    _init_state()
    render_sidebar()

    if st.session_state.current_session is None:
        st.title("👋 Asisten Keuangan UKM")
        st.write("Buat sesi baru di sidebar untuk mulai chat.")
        return

    sesh = st.session_state.sessions[st.session_state.current_session]
    tab_chat, tab_db = st.tabs(["💬 Chat", "🗄️ Database"])

    with tab_chat:
        render_chat(sesh)

    with tab_db:
        render_database()


if __name__ == "__main__":
    main()

import streamlit as st
import sqlite3
import pandas as pd

# ============================
# ✅ CONFIGURATION (EDIT HERE)
# ============================

USERS = [
    "Greenbelt 5",
    "SM Aura",
    "SM MOA",
    "Rockwell",
    "Aseana",
    "SM Makati",
    "Podium",
    "Rustans Shang",
    "Rustans Cebu",
    "Nustar Cebu"
]

SWITCH_LABELS = [
    "BB",
    "F&B",
    "Coffee",
    "Set Up",
    "Bouquet",
    "Photographer",
    "Engraver"
]

ITEM_LABELS = [
    "Drinks",
    "Food",
    "Photosleeves",
    "Coffee",
    "Flowers"
]

# ============================
# DATABASE
# ============================

DB_NAME = "dashboard.db"

st.markdown("""
    <style>
    .table-container {
        overflow-x: auto;
        white-space: nowrap;
    }
    .row {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
    }
    .cell {
        min-width: 120px;
        margin-right: 10px;
    }
    </style>
""", unsafe_allow_html=True)

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS switches (
            user TEXT,
            switch INTEGER,
            state INTEGER,
            PRIMARY KEY (user, switch)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS consumption (
            user TEXT,
            item INTEGER,
            percent INTEGER,
            PRIMARY KEY (user, item)
        )
    """)

    for user in USERS:
        for s in range(len(SWITCH_LABELS)):
            c.execute("""
                INSERT OR IGNORE INTO switches VALUES (?, ?, ?)
            """, (user, s, 0))

        for i in range(len(ITEM_LABELS)):
            c.execute("""
                INSERT OR IGNORE INTO consumption VALUES (?, ?, ?)
            """, (user, i, 0))

    conn.commit()
    conn.close()

def update_switch(user, switch, value):
    conn = get_connection()
    conn.execute(
        "UPDATE switches SET state=? WHERE user=? AND switch=?",
        (value, user, switch)
    )
    conn.commit()
    conn.close()

def get_switch_data():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM switches", conn)
    conn.close()
    return df

def update_consumption(user, item, value):
    conn = get_connection()
    conn.execute(
        "UPDATE consumption SET percent=? WHERE user=? AND item=?",
        (value, user, item)
    )
    conn.commit()
    conn.close()

def get_consumption_data():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM consumption", conn)
    conn.close()
    return df

# ============================
# INIT
# ============================

init_db()

st.set_page_config(layout="wide")
st.title("🟠 BB Dashboard")

tab1, tab2 = st.tabs(["🔘 Supplier", "📦 Consumption"])

# ============================
# 🔘 SUPPLIER TAB
# ============================
with tab1:
    st.subheader("Supplier Tracking")
    st.info("📱 Rotate phone to landscape for best experience")

    df = get_switch_data()
    pivot = df.pivot(index="user", columns="switch", values="state")

    # Ensure correct structure
    pivot = pivot.reindex(columns=range(len(SWITCH_LABELS)), fill_value=0)

    st.markdown('<div class="scroll-table">', unsafe_allow_html=True)

    # Header
    header = st.columns(len(SWITCH_LABELS) + 1, gap="small")
    header[0].write("**Store**")
    for i, label in enumerate(SWITCH_LABELS):
        header[i+1].write(f"**{label}**")

    # Rows
    for user in USERS:
        cols = st.columns(len(SWITCH_LABELS) + 1, gap="small")
        cols[0].write(user)

        for i in range(len(SWITCH_LABELS)):
            val = pivot.loc[user, i]

            new_val = cols[i+1].checkbox(
                "",
                value=bool(val),
                key=f"{user}_switch_{i}",
                label_visibility="collapsed"
            )

            if new_val != bool(val):
                update_switch(user, i, int(new_val))
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ============================
# 📦 CONSUMPTION TAB (SCROLLABLE TABLE)
# ============================
with tab2:
    st.subheader("Consumption (%)")
    st.info("📱 Rotate phone to landscape for best experience")

    df = get_consumption_data()
    pivot = df.pivot(index="user", columns="item", values="percent")

    pivot = pivot.reindex(columns=range(len(ITEM_LABELS)), fill_value=0)

    st.markdown('<div class="scroll-table">', unsafe_allow_html=True)

    # Header
    header = st.columns(len(ITEM_LABELS) + 1, gap="small")
    header[0].write("**Store**")
    for i, label in enumerate(ITEM_LABELS):
        header[i+1].write(f"**{label} (%)**")

    # Rows
    for user in USERS:
        cols = st.columns(len(ITEM_LABELS) + 1, gap="small")
        cols[0].write(user)

        for i in range(len(ITEM_LABELS)):
            current_val = int(pivot.loc[user, i])

            new_val = cols[i+1].number_input(
                "",
                min_value=0,
                max_value=100,
                value=current_val,
                step=1,
                key=f"{user}_item_{i}",
                label_visibility="collapsed"
            )

            if new_val != current_val:
                update_consumption(user, i, new_val)
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
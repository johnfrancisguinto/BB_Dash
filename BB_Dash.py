import streamlit as st
import sqlite3
import pandas as pd
import json

# ============================
# DB SETUP
# ============================

DB_NAME = "dashboard.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS Supplier (
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

    c.execute("""
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ============================
# CONFIG FUNCTIONS
# ============================

def get_config(key, default):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT value FROM config WHERE key=?", (key,))
    result = cur.fetchone()
    conn.close()

    return json.loads(result[0]) if result else default


def set_config(key, value):
    conn = get_connection()
    conn.execute(
        "REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, json.dumps(value))
    )
    conn.commit()
    conn.close()


# ============================
# LOAD CONFIG
# ============================

USERS = get_config("users", ["User1", "User2"])
Supplier_labels = get_config("Supplier", ["Switch1", "Switch2"])
ITEM_LABELS = get_config("items", ["Item1", "Item2"])

# ============================
# ENSURE DB MATCHES CONFIG
# ============================

def sync_db():
    conn = get_connection()
    c = conn.cursor()

    for user in USERS:
        for i in range(len(Supplier_labels)):
            c.execute(
                "INSERT OR IGNORE INTO Supplier VALUES (?, ?, ?)",
                (user, i, 0)
            )

        for i in range(len(ITEM_LABELS)):
            c.execute(
                "INSERT OR IGNORE INTO consumption VALUES (?, ?, ?)",
                (user, i, 0)
            )

    conn.commit()
    conn.close()

sync_db()

# ============================
# DATA FUNCTIONS
# ============================

def get_switch_data():
    return pd.read_sql("SELECT * FROM Supplier", get_connection())

def update_switch(user, switch, value):
    conn = get_connection()
    conn.execute(
        "UPDATE Supplier SET state=? WHERE user=? AND switch=?",
        (value, user, switch)
    )
    conn.commit()
    conn.close()

def get_consumption_data():
    return pd.read_sql("SELECT * FROM consumption", get_connection())

def update_consumption(user, item, value):
    conn = get_connection()
    conn.execute(
        "UPDATE consumption SET percent=? WHERE user=? AND item=?",
        (value, user, item)
    )
    conn.commit()
    conn.close()

# ============================
# PAGE CONFIG
# ============================

st.set_page_config(layout="wide")

st.markdown("""
<style>
.scroll-table {
    overflow-x: auto;
    white-space: nowrap;
    padding-bottom: 10px;
}
div[data-testid="column"] {
    min-width: 90px !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🟠BB Dashboard")

tab1, tab2, tab3 = st.tabs(["🥂 Supplier", "😋 Consumption", "⚙️ Admin"])

# ============================
# TAB 1: Supplier
# ============================

with tab1:
    st.subheader("Supplier Tracking")
    st.info("📱 Rotate phone for better view")

    df = get_switch_data()
    pivot = df.pivot(index="user", columns="switch", values="state")
    pivot = pivot.reindex(columns=range(len(Supplier_labels)), fill_value=0)

    st.markdown('<div class="scroll-table">', unsafe_allow_html=True)

    header = st.columns(len(Supplier_labels) + 1, gap="small")
    header[0].write("**Store**")
    for i, label in enumerate(Supplier_labels):
        header[i+1].write(f"**{label}**")

    for user in USERS:
        cols = st.columns(len(Supplier_labels) + 1, gap="small")
        cols[0].write(user)

        for i in range(len(Supplier_labels)):
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
# TAB 2: CONSUMPTION
# ============================

with tab2:
    st.subheader("Consumption (%)")
    st.info("📱 Rotate phone for better view")

    df = get_consumption_data()
    pivot = df.pivot(index="user", columns="item", values="percent")
    pivot = pivot.reindex(columns=range(len(ITEM_LABELS)), fill_value=0)

    st.markdown('<div class="scroll-table">', unsafe_allow_html=True)

    header = st.columns(len(ITEM_LABELS) + 1, gap="small")
    header[0].write("**Store**")
    for i, label in enumerate(ITEM_LABELS):
        header[i+1].write(f"**{label} (%)**")

    for user in USERS:
        cols = st.columns(len(ITEM_LABELS) + 1, gap="small")
        cols[0].write(user)

        for i in range(len(ITEM_LABELS)):
            val = int(pivot.loc[user, i])

            new_val = cols[i+1].number_input(
                "",
                min_value=0,
                max_value=100,
                value=val,
                key=f"{user}_item_{i}",
                label_visibility="collapsed"
            )

            if new_val != val:
                update_consumption(user, i, new_val)
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ============================
# TAB 3: ADMIN
# ============================

with tab3:
    st.subheader("Admin Panel")

    password = st.text_input("Enter Admin Password", type="password")

    if password == "admin123":
        st.success("Access granted")

        # USERS
        st.markdown("### 👤 Users")
        users_text = st.text_area(
            "Edit users (one per line)",
            "\n".join(USERS)
        )

        if st.button("Save Users"):
            set_config("users", users_text.split("\n"))
            st.rerun()

        # Supplier
        st.markdown("### 🥂 Supplier")
        Supplier_text = st.text_area(
            "Edit Supplier",
            "\n".join(Supplier_labels)
        )

        if st.button("Save Supplier"):
            set_config("Supplier", Supplier_text.split("\n"))
            st.rerun()

        # ITEMS
        st.markdown("### 📦 Items")
        items_text = st.text_area(
            "Edit items",
            "\n".join(ITEM_LABELS)
        )

        if st.button("Save Items"):
            set_config("items", items_text.split("\n"))
            st.rerun()

    else:
        st.warning("Enter password to unlock admin panel")

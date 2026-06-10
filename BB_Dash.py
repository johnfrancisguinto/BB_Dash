import streamlit as st
import pandas as pd
import os
from supabase import create_client

# ============================
# SUPABASE SETUP
# ============================

SUPABASE_URL = os.getenv("https://myukobnhgwldsxynflha.supabase.co")
SUPABASE_KEY = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im15dWtvYm5oZ3dsZHN4eW5mbGhhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEwODkxODgsImV4cCI6MjA5NjY2NTE4OH0.50Wq-iEdzbJbsMx2KkmnrnTc0UMb8t1J7s0TSUFup98")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================
# CONFIG FUNCTIONS
# ============================

def get_config(key, default):
    res = supabase.table("config").select("*").eq("key", key).execute()
    if res.data:
        return res.data[0]["value"]
    return default

def set_config(key, value):
    supabase.table("config").upsert({
        "key": key,
        "value": value
    }).execute()

# ============================
# LOAD CONFIG
# ============================

STORES = get_config("stores", ["Store1", "Store2"])
SUPPLIER_LABELS = get_config("suppliers", ["Supplier1", "Supplier2"])
ITEM_LABELS = get_config("items", ["Item1", "Item2"])

# ============================
# SYNC DATABASE
# ============================

def sync_db():
    for store in STORES:
        for i in range(len(SUPPLIER_LABELS)):
            supabase.table("switches").upsert({
                "store": store,
                "supplier": i,
                "state": 0
            }).execute()

        for i in range(len(ITEM_LABELS)):
            supabase.table("consumption").upsert({
                "store": store,
                "item": i,
                "percent": 0
            }).execute()

sync_db()

# ============================
# DATA FUNCTIONS
# ============================

def get_switch_data():
    res = supabase.table("switches").select("*").execute()
    return pd.DataFrame(res.data)

def update_switch(store, supplier, value):
    supabase.table("switches").update({
        "state": value
    }).eq("store", store).eq("supplier", supplier).execute()

def get_consumption_data():
    res = supabase.table("consumption").select("*").execute()
    return pd.DataFrame(res.data)

def update_consumption(store, item, value):
    supabase.table("consumption").update({
        "percent": value
    }).eq("store", store).eq("item", item).execute()

# ============================
# UI CONFIG
# ============================

st.set_page_config(layout="wide")

st.markdown("""
<style>
.scroll-table {
    overflow-x: auto;
    white-space: nowrap;
}
div[data-testid="column"] {
    min-width: 90px !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🟠BB Dashboard")

tab1, tab2, tab3 = st.tabs(["🏭 Suppliers", "📦 Consumption", "⚙️ Admin"])

# ============================
# TAB 1: STORE x SUPPLIER
# ============================

with tab1:
    st.subheader("Supplier Tracking")
    st.info("📱 Rotate phone for best experience")

    df = get_switch_data()

    if not df.empty:
        pivot = df.pivot(index="store", columns="supplier", values="state")
    else:
        pivot = pd.DataFrame()

    pivot = pivot.reindex(columns=range(len(SUPPLIER_LABELS)), fill_value=0)

    st.markdown('<div class="scroll-table">', unsafe_allow_html=True)

    header = st.columns(len(SUPPLIER_LABELS) + 1)
    header[0].write("Store")

    for i, label in enumerate(SUPPLIER_LABELS):
        header[i+1].write(label)

    for store in STORES:
        cols = st.columns(len(SUPPLIER_LABELS) + 1)
        cols[0].write(store)

        for i in range(len(SUPPLIER_LABELS)):
            val = False
            if not pivot.empty and store in pivot.index:
                val = bool(pivot.loc[store, i])

            new_val = cols[i+1].checkbox(
                f"{store}_{i}",
                value=val,
                key=f"{store}_supplier_{i}",
                label_visibility="collapsed"
            )

            if new_val != val:
                update_switch(store, i, int(new_val))
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ============================
# TAB 2: CONSUMPTION
# ============================

with tab2:
    st.subheader("Consumption (%)")
    st.info("📱 Rotate phone for best experience")

    df = get_consumption_data()

    if not df.empty:
        pivot = df.pivot(index="store", columns="item", values="percent")
    else:
        pivot = pd.DataFrame()

    pivot = pivot.reindex(columns=range(len(ITEM_LABELS)), fill_value=0)

    st.markdown('<div class="scroll-table">', unsafe_allow_html=True)

    header = st.columns(len(ITEM_LABELS) + 1)
    header[0].write("Store")

    for i, label in enumerate(ITEM_LABELS):
        header[i+1].write(f"{label} (%)")

    for store in STORES:
        cols = st.columns(len(ITEM_LABELS) + 1)
        cols[0].write(store)

        for i in range(len(ITEM_LABELS)):
            val = 0
            if not pivot.empty and store in pivot.index:
                val = int(pivot.loc[store, i])

            new_val = cols[i+1].number_input(
                f"{store}_item_{i}",
                min_value=0,
                max_value=100,
                value=val,
                key=f"{store}_item_{i}",
                label_visibility="collapsed"
            )

            if new_val != val:
                update_consumption(store, i, new_val)
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ============================
# TAB 3: ADMIN
# ============================

with tab3:
    st.subheader("Admin Panel")

    password = st.text_input("Admin Password", type="password")

    if password == "admin123":
        st.success("Access granted")

        stores_text = st.text_area("Stores (one per line)", "\n".join(STORES))
        if st.button("Save Stores"):
            set_config("stores", stores_text.split("\n"))
            st.rerun()

        suppliers_text = st.text_area("Suppliers (columns)", "\n".join(SUPPLIER_LABELS))
        if st.button("Save Suppliers"):
            set_config("suppliers", suppliers_text.split("\n"))
            st.rerun()

        items_text = st.text_area("Items", "\n".join(ITEM_LABELS))
        if st.button("Save Items"):
            set_config("items", items_text.split("\n"))
            st.rerun()

    else:
        st.warning("Enter admin password")

import streamlit as st
import pandas as pd
import os
from supabase import create_client

# ============================
# SUPABASE SETUP
# ============================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Supabase environment variables missing")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================
# CONFIG FUNCTIONS
# ============================

def get_config(key, default):
    res = supabase.table("config").select("*").eq("key", key).execute()
    return res.data[0]["value"] if res.data else default

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
# SAFE SYNC
# ============================

def sync_db():
    existing = supabase.table("switches").select("store,supplier").execute()
    existing_pairs = {(r["store"], r["supplier"]) for r in existing.data}

    for store in STORES:
        for i in range(len(SUPPLIER_LABELS)):
            if (store, i) not in existing_pairs:
                supabase.table("switches").insert({
                    "store": store,
                    "supplier": i,
                    "state": 0
                }).execute()

    existing = supabase.table("consumption").select("store,item").execute()
    existing_pairs = {(r["store"], r["item"]) for r in existing.data}

    for store in STORES:
        for i in range(len(ITEM_LABELS)):
            if (store, i) not in existing_pairs:
                supabase.table("consumption").insert({
                    "store": store,
                    "item": i,
                    "percent": 0
                }).execute()

if "initialized" not in st.session_state:
    sync_db()
    st.session_state.initialized = True

# ============================
# DATA FUNCTIONS
# ============================

def get_switch_data():
    res = supabase.table("switches").select("*").execute()
    return pd.DataFrame(res.data)

def update_switch(store, supplier, value):
    supabase.table("switches")\
        .update({"state": value})\
        .eq("store", store)\
        .eq("supplier", supplier)\
        .execute()

def get_consumption_data():
    res = supabase.table("consumption").select("*").execute()
    return pd.DataFrame(res.data)

def update_consumption(store, item, value):
    supabase.table("consumption")\
        .update({"percent": value})\
        .eq("store", store)\
        .eq("item", item)\
        .execute()

# ============================
# UNSAVED CHECK HELPER
# ============================

def has_unsaved_changes(changes_dict, pivot, is_bool=False):
    for (store, i), new_val in changes_dict.items():
        if store in pivot.index:
            current_val = pivot.loc[store, i]
            current_val = bool(current_val) if is_bool else int(current_val)
            if new_val != current_val:
                return True
    return False

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

st.title("🟠 BB Dashboard")

tab1, tab2, tab3 = st.tabs(["🏭 Suppliers", "📦 Consumption", "⚙️ Admin"])

# ============================
# TAB 1: SWITCHES
# ============================

with tab1:
    st.subheader("Supplier Tracking")

    df = get_switch_data()
    pivot = df.pivot(index="store", columns="supplier", values="state") if not df.empty else pd.DataFrame()
    pivot = pivot.reindex(columns=range(len(SUPPLIER_LABELS)), fill_value=0)

    if "switch_changes" not in st.session_state:
        st.session_state.switch_changes = {}

    st.markdown('<div class="scroll-table">', unsafe_allow_html=True)

    header = st.columns(len(SUPPLIER_LABELS) + 1)
    header[0].write("Store")

    for i, label in enumerate(SUPPLIER_LABELS):
        header[i+1].write(label)

    for store in STORES:
        cols = st.columns(len(SUPPLIER_LABELS) + 1)
        cols[0].write(store)

        for i in range(len(SUPPLIER_LABELS)):
            val = bool(pivot.loc[store, i]) if store in pivot.index else False
            key = f"sw_{store}_{i}"

            new_val = cols[i+1].checkbox(
                key,
                value=val,
                key=key,
                label_visibility="collapsed"
            )

            st.session_state.switch_changes[(store, i)] = int(new_val)

    st.markdown('</div>', unsafe_allow_html=True)

    unsaved = has_unsaved_changes(st.session_state.switch_changes, pivot, is_bool=True)
    if unsaved:
        st.warning("⚠️ You have unsaved switch changes")

    if st.button("💾 Save Switch Changes"):
        for (store, i), value in st.session_state.switch_changes.items():
            update_switch(store, i, value)

        st.session_state.switch_changes = {}
        st.success("✅ Switches updated!")

# ============================
# TAB 2: CONSUMPTION
# ============================

with tab2:
    st.subheader("Consumption (%)")

    df = get_consumption_data()
    pivot = df.pivot(index="store", columns="item", values="percent") if not df.empty else pd.DataFrame()
    pivot = pivot.reindex(columns=range(len(ITEM_LABELS)), fill_value=0)

    if "consumption_changes" not in st.session_state:
        st.session_state.consumption_changes = {}

    st.markdown('<div class="scroll-table">', unsafe_allow_html=True)

    header = st.columns(len(ITEM_LABELS) + 1)
    header[0].write("Store")

    for i, label in enumerate(ITEM_LABELS):
        header[i+1].write(f"{label} (%)")

    for store in STORES:
        cols = st.columns(len(ITEM_LABELS) + 1)
        cols[0].write(store)

        for i in range(len(ITEM_LABELS)):
            val = int(pivot.loc[store, i]) if store in pivot.index else 0
            key = f"con_{store}_{i}"

            new_val = cols[i+1].number_input(
                key,
                min_value=0,
                max_value=100,
                value=val,
                key=key,
                label_visibility="collapsed"
            )

            st.session_state.consumption_changes[(store, i)] = int(new_val)

    st.markdown('</div>', unsafe_allow_html=True)

    unsaved = has_unsaved_changes(st.session_state.consumption_changes, pivot)
    if unsaved:
        st.warning("⚠️ You have unsaved consumption changes")

    if st.button("💾 Save Consumption Changes"):
        for (store, i), value in st.session_state.consumption_changes.items():
            update_consumption(store, i, value)

        st.session_state.consumption_changes = {}
        st.success("✅ Consumption updated!")

# ============================
# TAB 3: ADMIN
# ============================

with tab3:
    st.subheader("Admin Panel")

    password = st.text_input("Admin Password", type="password")

    if password == "admin123":
        st.success("Access granted")

        stores_text = st.text_area("Stores", "\n".join(STORES))
        if st.button("Save Stores"):
            set_config("stores", stores_text.split("\n"))

        suppliers_text = st.text_area("Suppliers", "\n".join(SUPPLIER_LABELS))
        if st.button("Save Suppliers"):
            set_config("suppliers", suppliers_text.split("\n"))

        items_text = st.text_area("Items", "\n".join(ITEM_LABELS))
        if st.button("Save Items"):
            set_config("items", items_text.split("\n"))

    else:
        st.warning("Enter admin password")

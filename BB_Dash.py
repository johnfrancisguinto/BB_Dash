import streamlit as st
import pandas as pd
import os
import time
from supabase import create_client
from datetime import datetime

# ============================
# SUPABASE
# ============================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Supabase environment variables missing")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================
# CONFIG
# ============================

def get_config(key, default):
    res = supabase.table("config").select("*").eq("key", key).execute()
    return res.data[0]["value"] if res.data else default

def set_config(key, value):
    supabase.table("config").upsert({
        "key": key,
        "value": value
    }).execute()

STORES = get_config("stores", ["Store1","Store2"])
SUPPLIER_LABELS = get_config("suppliers", ["Supplier1","Supplier2"])
ITEM_LABELS = get_config("items", ["Item1","Item2"])

# ============================
# SYNC
# ============================

def sync_db():
    existing = supabase.table("switches").select("store,supplier").execute()
    existing_pairs = {(r["store"], r["supplier"]) for r in existing.data}

    for store in STORES:
        for i in range(len(SUPPLIER_LABELS)):
            if (store, i) not in existing_pairs:
                supabase.table("switches").insert({
                    "store": store, "supplier": i, "state": 0
                }).execute()

    existing = supabase.table("consumption").select("store,item").execute()
    existing_pairs = {(r["store"], r["item"]) for r in existing.data}

    for store in STORES:
        for i in range(len(ITEM_LABELS)):
            if (store, i) not in existing_pairs:
                supabase.table("consumption").insert({
                    "store": store, "item": i, "percent": 0
                }).execute()

if "init" not in st.session_state:
    sync_db()
    st.session_state.init = True

# ============================
# DATA
# ============================

def get_supplier():
    return pd.DataFrame(supabase.table("switches").select("*").execute().data)

def get_consumption():
    return pd.DataFrame(supabase.table("consumption").select("*").execute().data)

def update_supplier(store, supplier, value):
    supabase.table("switches").update({
        "state": value,
        "updated_by": store,
        "updated_at": "now()"
    }).eq("store", store).eq("supplier", supplier).execute()

def update_consumption(store, item, value):
    supabase.table("consumption").update({
        "percent": value,
        "updated_by": store,
        "updated_at": "now()"
    }).eq("store", store).eq("item", item).execute()

# ============================
# AUTO SAVE LOGIC
# ============================

def auto_save(buffer, pivot, update_fn, delay=2):
    now = time.time()

    if "last_change_time" not in st.session_state:
        st.session_state.last_change_time = now

    changed = False

    for (store,i), new_val in buffer.items():
        if store in pivot.index:
            current_val = pivot.loc[store,i]
            if isinstance(new_val,bool):
                current_val = bool(current_val)
            else:
                current_val = int(current_val)

            if new_val != current_val:
                changed = True

    if changed:
        st.session_state.last_change_time = now
        st.warning("⚠️ Unsaved changes... auto-saving soon")

    if changed and (now - st.session_state.last_change_time > delay):
        for (store,i), val in buffer.items():
            update_fn(store, i, val)

        buffer.clear()
        st.success("✅ Auto-saved")

# ============================
# UI
# ============================

st.set_page_config(layout="wide")
st.title("🟠 BB Dashboard")

tab1, tab2, tab3 = st.tabs(["🏭 Suppliers","📦 Consumption","⚙️ Admin"])

# ============================
# SUPPLIERS TAB
# ============================

with tab1:

    df = get_supplier()
    pivot = df.pivot(index="store", columns="supplier", values="state") if not df.empty else pd.DataFrame()
    pivot = pivot.reindex(columns=range(len(SUPPLIER_LABELS)), fill_value=0)

    if "sup_buffer" not in st.session_state:
        st.session_state.sup_buffer = {}

    for store in STORES:
        cols = st.columns(len(SUPPLIER_LABELS)+1)
        cols[0].write(store)

        for i in range(len(SUPPLIER_LABELS)):
            val = bool(pivot.loc[store,i]) if store in pivot.index else False
            new_val = cols[i+1].checkbox(
                f"s_{store}_{i}",
                value=val,
                key=f"s_{store}_{i}"
            )

            st.session_state.sup_buffer[(store,i)] = int(new_val)

        # timestamp
        if not df.empty:
            row = df[df["store"]==store].iloc[0]
            if "updated_at" in row and row["updated_at"]:
                t = datetime.fromisoformat(row["updated_at"])
                cols[0].caption(f"🕒 {row['updated_by']} @ {t.strftime('%H:%M:%S')}")

    auto_save(st.session_state.sup_buffer, pivot, update_supplier)

# ============================
# CONSUMPTION TAB
# ============================

with tab2:

    df = get_consumption()
    pivot = df.pivot(index="store", columns="item", values="percent") if not df.empty else pd.DataFrame()
    pivot = pivot.reindex(columns=range(len(ITEM_LABELS)), fill_value=0)

    if "con_buffer" not in st.session_state:
        st.session_state.con_buffer = {}

    for store in STORES:
        cols = st.columns(len(ITEM_LABELS)+1)
        cols[0].write(store)

        for i in range(len(ITEM_LABELS)):
            val = int(pivot.loc[store,i]) if store in pivot.index else 0
            new_val = cols[i+1].number_input(
                f"c_{store}_{i}",
                0,100,val,
                key=f"c_{store}_{i}"
            )

            st.session_state.con_buffer[(store,i)] = int(new_val)

        if not df.empty:
            row = df[df["store"]==store].iloc[0]
            if "updated_at" in row and row["updated_at"]:
                t = datetime.fromisoformat(row["updated_at"])
                cols[0].caption(f"🕒 {row['updated_by']} @ {t.strftime('%H:%M:%S')}")

    auto_save(st.session_state.con_buffer, pivot, update_consumption)

# ============================
# ADMIN
# ============================

with tab3:
    pw = st.text_input("Admin Password", type="password")

    if pw=="admin123":
        st.success("Access granted")

        if st.button("Save Stores"):
            set_config("stores", STORES)

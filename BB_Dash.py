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
    st.error("❌ Missing Supabase env")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================
# CONFIG
# ============================

def get_config(key, default):
    res = supabase.table("config").select("*").eq("key", key).execute()
    return res.data[0]["value"] if res.data else default

def set_config(key, value):
    supabase.table("config").upsert({"key": key, "value": value}).execute()

# ============================
# LAST UPDATE (GLOBAL)
# ============================

def set_last_update(store):
    set_config("last_update", {
        "store": store,
        "time": datetime.now().isoformat()
    })

def get_last_update():
    return get_config("last_update", {})

# ============================
# LOAD CONFIG
# ============================

STORES = get_config("stores", ["Store1","Store2"])
SUPPLIERS = get_config("suppliers", ["Supplier1","Supplier2"])
ITEMS = get_config("items", ["Item1","Item2"])

# ============================
# SYNC
# ============================

def sync_db():
    existing = supabase.table("switches").select("store,supplier").execute()
    pairs = {(r["store"], r["supplier"]) for r in existing.data}

    for store in STORES:
        for i in range(len(SUPPLIERS)):
            if (store,i) not in pairs:
                supabase.table("switches").insert({
                    "store": store, "supplier": i, "state": 0
                }).execute()

    existing = supabase.table("consumption").select("store,item").execute()
    pairs = {(r["store"], r["item"]) for r in existing.data}

    for store in STORES:
        for i in range(len(ITEMS)):
            if (store,i) not in pairs:
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

def update_supplier(store, i, val):
    supabase.table("switches").update({"state": val})\
        .eq("store", store).eq("supplier", i).execute()
    set_last_update(store)

def update_consumption(store, i, val):
    supabase.table("consumption").update({"percent": val})\
        .eq("store", store).eq("item", i).execute()
    set_last_update(store)

# ============================
# AUTO SAVE
# ============================

def auto_save(buffer, pivot, update_fn):

    changed = False

    for (store,i), v in buffer.items():
        if store in pivot.index:
            cur = pivot.loc[store,i]
            cur = int(cur) if not isinstance(v,bool) else bool(cur)
            if v != cur:
                changed = True
                break

    if changed and "timer" not in st.session_state:
        st.session_state.timer = time.time()

    if changed:
        st.warning("⚠️ Unsaved changes...")

    if changed and time.time() - st.session_state.timer > 2:

        with st.spinner("🔄 Saving..."):
            for (s,i), v in buffer.items():
                update_fn(s,i,v)

        buffer.clear()
        del st.session_state["timer"]
        st.success("✅ Auto-saved")

# ============================
# UI
# ============================

st.set_page_config(layout="wide")
st.title("🟠 BB Dashboard")

tab1, tab2, tab3 = st.tabs(["🏭 Suppliers","📦 Consumption","⚙️ Admin"])

# ============================
# TAB 1: SUPPLIERS
# ============================

with tab1:

    df = get_supplier()
    pivot = df.pivot(index="store", columns="supplier", values="state") if not df.empty else pd.DataFrame()
    pivot = pivot.reindex(columns=range(len(SUPPLIERS)), fill_value=0)

    if "sup_buf" not in st.session_state:
        st.session_state.sup_buf = {}

    # ✅ HEADER
    header = st.columns(len(SUPPLIERS)+1)
    header[0].write("Store")

    for i, label in enumerate(SUPPLIERS):
        header[i+1].write(label)

    # ✅ TABLE
    for store in STORES:
        cols = st.columns(len(SUPPLIERS)+1)
        cols[0].write(store)

        for i in range(len(SUPPLIERS)):
            val = bool(pivot.loc[store,i]) if store in pivot.index else False

            new = cols[i+1].checkbox(
                f"sup_{store}_{i}",
                value=val,
                label_visibility="collapsed"
            )

            st.session_state.sup_buf[(store,i)] = int(new)

    auto_save(st.session_state.sup_buf, pivot, update_supplier)

    # ✅ GLOBAL LABEL
    last = get_last_update()
    if last:
        t = datetime.fromisoformat(last["time"])
        st.info(f"🕒 Last updated by {last['store']} @ {t.strftime('%b %d %I:%M:%S %p')}")

# ============================
# TAB 2: CONSUMPTION
# ============================

with tab2:

    df = get_consumption()
    pivot = df.pivot(index="store", columns="item", values="percent") if not df.empty else pd.DataFrame()
    pivot = pivot.reindex(columns=range(len(ITEMS)), fill_value=0)

    if "con_buf" not in st.session_state:
        st.session_state.con_buf = {}

    # ✅ HEADER
    header = st.columns(len(ITEMS)+1)
    header[0].write("Store")

    for i, label in enumerate(ITEMS):
        header[i+1].write(f"{label} (%)")

    # ✅ TABLE
    for store in STORES:
        cols = st.columns(len(ITEMS)+1)
        cols[0].write(store)

        for i in range(len(ITEMS)):
            val = int(pivot.loc[store,i]) if store in pivot.index else 0

            new = cols[i+1].number_input(
                f"con_{store}_{i}",
                0,100,val,
                label_visibility="collapsed"
            )

            st.session_state.con_buf[(store,i)] = int(new)

    auto_save(st.session_state.con_buf, pivot, update_consumption)

    # ✅ GLOBAL LABEL
    last = get_last_update()
    if last:
        t = datetime.fromisoformat(last["time"])
        st.info(f"🕒 Last updated by {last['store']} @ {t.strftime('%b %d %I:%M:%S %p')}")

# ============================
# TAB 3: ADMIN
# ============================

with tab3:
    pw = st.text_input("Admin password", type="password")

    if pw == "admin123":
        st.success("Access granted")

        stores_text = st.text_area("Stores", "\n".join(STORES))
        if st.button("Save Stores"):
            set_config("stores", stores_text.split("\n"))

        suppliers_text = st.text_area("Suppliers", "\n".join(SUPPLIERS))
        if st.button("Save Suppliers"):
            set_config("suppliers", suppliers_text.split("\n"))

        items_text = st.text_area("Items", "\n".join(ITEMS))
        if st.button("Save Items"):
            set_config("items", items_text.split("\n"))

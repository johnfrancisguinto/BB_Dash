import streamlit as st
import pandas as pd
import os
from supabase import create_client
from datetime import datetime
import pytz

# ============================
# SUPABASE
# ============================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

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
# LAST UPDATE
# ============================

def set_last_update(store):
    set_config("last_update", {
        "store": store,
        "time": datetime.utcnow().isoformat()
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

    header = st.columns(len(SUPPLIERS)+1)
    header[0].write("Store")

    for i,label in enumerate(SUPPLIERS):
        header[i+1].write(label)

    changed = False
    values = {}

    for store in STORES:
        cols = st.columns(len(SUPPLIERS)+1)
        cols[0].write(store)

        for i in range(len(SUPPLIERS)):
            val = int(pivot.loc[store,i]) if store in pivot.index else 0

            key = f"sup_{store}_{i}"

            new = cols[i+1].checkbox(
                key,
                value=bool(val),
                label_visibility="collapsed"
            )

            values[(store,i)] = int(new)

            if new != val:
                changed = True

    if changed:
        st.warning("⚠️ You have unsaved supplier changes")

    if st.button("💾 Save Supplier Changes"):
        for (store,i), val in values.items():
            update_supplier(store,i,val)

        st.success("✅ Saved")

    # ✅ PH TIME
    last = get_last_update()
    if last:
        utc = datetime.fromisoformat(last["time"])
        ph = pytz.timezone("Asia/Manila")
        t = utc.astimezone(ph)
        st.info(f"🕒 Last updated by {last['store']} @ {t.strftime('%b %d %I:%M:%S %p')}")

# ============================
# TAB 2: CONSUMPTION
# ============================

with tab2:

    df = get_consumption()
    pivot = df.pivot(index="store", columns="item", values="percent") if not df.empty else pd.DataFrame()
    pivot = pivot.reindex(columns=range(len(ITEMS)), fill_value=0)

    header = st.columns(len(ITEMS)+1)
    header[0].write("Store")

    for i,label in enumerate(ITEMS):
        header[i+1].write(f"{label} (%)")

    changed = False
    values = {}

    for store in STORES:
        cols = st.columns(len(ITEMS)+1)
        cols[0].write(store)

        for i in range(len(ITEMS)):
            val = int(pivot.loc[store,i]) if store in pivot.index else 0

            key = f"con_{store}_{i}"

            new = cols[i+1].number_input(
                key,
                0,100,val,
                label_visibility="collapsed"
            )

            values[(store,i)] = int(new)

            if new != val:
                changed = True

    if changed:
        st.warning("⚠️ You have unsaved consumption changes")

    if st.button("💾 Save Consumption Changes"):
        for (store,i), val in values.items():
            update_consumption(store,i,val)

        st.success("✅ Saved")

    # ✅ PH TIME
    last = get_last_update()
    if last:
        utc = datetime.fromisoformat(last["time"])
        ph = pytz.timezone("Asia/Manila")
        t = utc.astimezone(ph)
        st.info(f"🕒 Last updated by {last['store']} @ {t.strftime('%b %d %I:%M:%S %p')}")

# ============================
# ADMIN
# ============================

with tab3:
    st.subheader("Admin Panel")

    password = st.text_input("Admin password", type="password")

    if password == "admin123":
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

    else:
        st.warning("Enter admin password")

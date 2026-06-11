import streamlit as st
import pandas as pd
import os
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
# LAST UPDATE (FIXED)
# ============================

def set_last_update(store):
    set_config("last_update", {
        "store": store,
        "time": datetime.now().isoformat()
    })

def get_last_update():
    return get_config("last_update", {})

# ============================
# ACTIVITY LOG
# ============================

def log_activity(store, typ, old, new):
    supabase.table("activity_log").insert({
        "store": store,
        "field_type": typ,
        "old_value": str(old),
        "new_value": str(new)
    }).execute()

def get_activity():
    res = supabase.table("activity_log")\
        .select("*")\
        .order("created_at", desc=True)\
        .limit(50)\
        .execute()

    df = pd.DataFrame(res.data)

    if df.empty:
        return df

    # ✅ Clean columns
    df = df[["store", "field_type", "old_value", "new_value", "created_at"]]

    # ✅ Replace supplier 0/1 with icons
    df["old_value"] = df.apply(
        lambda x: "✅" if x["old_value"] == "1" and x["field_type"]=="supplier"
        else "❌" if x["old_value"] == "0" and x["field_type"]=="supplier"
        else x["old_value"], axis=1
    )

    df["new_value"] = df.apply(
        lambda x: "✅" if x["new_value"] == "1" and x["field_type"]=="supplier"
        else "❌" if x["new_value"] == "0" and x["field_type"]=="supplier"
        else x["new_value"], axis=1
    )

    return df

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

# ✅ FIXED: only update/log when value actually changes
def update_supplier(store, i, new, old):
    if new != old:
        log_activity(store, "supplier", old, new)
        supabase.table("switches").update({"state": new})\
            .eq("store", store).eq("supplier", i).execute()
        set_last_update(store)

def update_consumption(store, i, new, old):
    if new != old:
        log_activity(store, "consumption", old, new)
        supabase.table("consumption").update({"percent": new})\
            .eq("store", store).eq("item", i).execute()
        set_last_update(store)

# ============================
# UI
# ============================

st.set_page_config(layout="wide")
st.title("🟠 BB Dashboard")

tab1, tab2, tab3, tab4 = st.tabs(
    ["🏭 Suppliers","📦 Consumption","⚙️ Admin","📜 Activity"]
)

# ============================
# TAB 1: SUPPLIERS
# ============================

with tab1:

    df = get_supplier()
    pivot = df.pivot(index="store", columns="supplier", values="state") if not df.empty else pd.DataFrame()
    pivot = pivot.reindex(columns=range(len(SUPPLIERS)), fill_value=0)

    if "sup_buf" not in st.session_state:
        st.session_state.sup_buf = {}

    header = st.columns(len(SUPPLIERS)+1)
    header[0].write("Store")

    for i, label in enumerate(SUPPLIERS):
        header[i+1].write(label)

    unsaved = False

    for store in STORES:
        cols = st.columns(len(SUPPLIERS)+1)
        cols[0].write(store)

        for i in range(len(SUPPLIERS)):
            val = int(pivot.loc[store,i]) if store in pivot.index else 0

            new = cols[i+1].checkbox(
                f"{store}_{i}",
                value=bool(val),
                label_visibility="collapsed"
            )

            st.session_state.sup_buf[(store,i)] = int(new)

            if new != val:
                unsaved = True

    if unsaved:
        st.warning("⚠️ Unsaved supplier changes")

    if st.button("💾 Save Supplier Changes"):
        for (store,i), val in st.session_state.sup_buf.items():
            old = int(pivot.loc[store,i]) if store in pivot.index else 0
            update_supplier(store,i,val,old)

        st.success("✅ Saved")

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

    header = st.columns(len(ITEMS)+1)
    header[0].write("Store")

    for i, label in enumerate(ITEMS):
        header[i+1].write(f"{label} (%)")

    unsaved = False

    for store in STORES:
        cols = st.columns(len(ITEMS)+1)
        cols[0].write(store)

        for i in range(len(ITEMS)):
            val = int(pivot.loc[store,i]) if store in pivot.index else 0

            new = cols[i+1].number_input(
                f"{store}_{i}",
                0,100,val,
                label_visibility="collapsed"
            )

            st.session_state.con_buf[(store,i)] = int(new)

            if new != val:
                unsaved = True

    if unsaved:
        st.warning("⚠️ Unsaved consumption changes")

    if st.button("💾 Save Consumption Changes"):
        for (store,i), val in st.session_state.con_buf.items():
            old = int(pivot.loc[store,i]) if store in pivot.index else 0
            update_consumption(store,i,val,old)

        st.success("✅ Saved")

    last = get_last_update()
    if last:
        t = datetime.fromisoformat(last["time"])
        st.info(f"🕒 Last updated by {last['store']} @ {t.strftime('%b %d %I:%M:%S %p')}")

# ============================
# TAB 4: ACTIVITY
# ============================

with tab4:

    st.subheader("Activity History")

    df = get_activity()

    if df.empty:
        st.info("No activity yet")
    else:
        st.dataframe(df, use_container_width=True)

# ============================
# ADMIN
# ============================

with tab3:
    pw = st.text_input("Admin password", type="password")

    if pw == "admin123":
        st.success("Access granted")

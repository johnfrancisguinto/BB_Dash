import streamlit as st
import pandas as pd
import os
from supabase import create_client
from datetime import datetime
import pytz

# ============================
# SUPABASE SETUP
# ============================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Missing Supabase env")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================
# CONFIG FUNCTIONS
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

    df = df[["store","field_type","old_value","new_value","created_at"]]

    # supplier icons
    df["old_value"] = df.apply(
        lambda x: "✅" if x["old_value"]=="1" and x["field_type"]=="supplier"
        else "❌" if x["old_value"]=="0" and x["field_type"]=="supplier"
        else x["old_value"], axis=1)

    df["new_value"] = df.apply(
        lambda x: "✅" if x["new_value"]=="1" and x["field_type"]=="supplier"
        else "❌" if x["new_value"]=="0" and x["field_type"]=="supplier"
        else x["new_value"], axis=1)

    return df

# ============================
# LOAD CONFIG
# ============================

STORES = get_config("stores", ["Store1","Store2"])
SUPPLIERS = get_config("suppliers", ["Supplier1","Supplier2"])
ITEMS = get_config("items", ["Item1","Item2"])

STORE_SUPPLIERS = get_config("store_suppliers", {})
STORE_ITEMS = get_config("store_items", {})

# ============================
# DATA
# ============================

def get_supplier():
    return pd.DataFrame(supabase.table("switches").select("*").execute().data)

def get_consumption():
    return pd.DataFrame(supabase.table("consumption").select("*").execute().data)

def update_supplier(store, i, new, old):
    if new != old:
        log_activity(store,"supplier",old,new)
        supabase.table("switches").update({"state":new})\
            .eq("store",store).eq("supplier",i).execute()
        set_last_update(store)

def update_consumption(store, i, new, old):
    if new != old:
        log_activity(store,"consumption",old,new)
        supabase.table("consumption").update({"percent":new})\
            .eq("store",store).eq("item",i).execute()
        set_last_update(store)

# ============================
# UI
# ============================

st.set_page_config(layout="wide")
st.title("🟠 BB Dashboard")

tab1, tab2, tab3, tab4 = st.tabs(
    ["🏭 Suppliers","📦 Consumption","📜 Activity","⚙️ Admin"]
)

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

    values = {}

    for store in STORES:
        cols = st.columns(len(SUPPLIERS)+1)
        cols[0].write(store)

        allowed = STORE_SUPPLIERS.get(store, list(range(len(SUPPLIERS))))

        for i in range(len(SUPPLIERS)):
            val = int(pivot.loc[store,i]) if store in pivot.index else 0

            if i in allowed:
                new = cols[i+1].checkbox(
                    f"sup_{store}_{i}",
                    value=bool(val),
                    label_visibility="collapsed"
                )
                values[(store,i)] = int(new)
            else:
                cols[i+1].checkbox(
                    f"disabled_sup_{store}_{i}",
                    value=False,
                    disabled=True,
                    label_visibility="collapsed"
                )

    if st.button("💾 Save Supplier Changes"):
        for (store,i), val in values.items():
            old = int(pivot.loc[store,i]) if store in pivot.index else 0
            update_supplier(store,i,val,old)

        st.success("✅ Saved")

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

    values = {}

    for store in STORES:
        cols = st.columns(len(ITEMS)+1)
        cols[0].write(store)

        allowed = STORE_ITEMS.get(store, list(range(len(ITEMS))))

        for i in range(len(ITEMS)):
            val = int(pivot.loc[store,i]) if store in pivot.index else 0

            if i in allowed:
                new = cols[i+1].number_input(
                    f"con_{store}_{i}",
                    min_value=0,
                    max_value=100,
                    value=val,
                    label_visibility="collapsed"
                )
                values[(store,i)] = int(new)
            else:
                cols[i+1].number_input(
                    f"disabled_con_{store}_{i}",
                    min_value=0,
                    max_value=100,
                    value=0,
                    disabled=True,
                    label_visibility="collapsed"
                )

    if st.button("💾 Save Consumption Changes"):
        for (store,i), val in values.items():
            old = int(pivot.loc[store,i]) if store in pivot.index else 0
            update_consumption(store,i,val,old)

        st.success("✅ Saved")

    # ✅ PH TIME
    last = get_last_update()
    if last:
        utc = datetime.fromisoformat(last["time"])
        ph = pytz.timezone("Asia/Manila")
        t = utc.astimezone(ph)
        st.info(f"🕒 Last updated by {last['store']} @ {t.strftime('%b %d %I:%M:%S %p')}")

# ============================
# TAB 3: ACTIVITY
# ============================

with tab3:

    st.subheader("Activity History")

    df = get_activity()

    if df.empty:
        st.info("No activity yet")
    else:
        st.dataframe(df, use_container_width=True)

# ============================
# TAB 4: ADMIN
# ============================

with tab4:

    password = st.text_input("Admin password", type="password")

    if password == "admin123":
        st.success("Access granted")

        # existing configs
        stores_text = st.text_area("Stores", "\n".join(STORES))
        if st.button("Save Stores"):
            set_config("stores", stores_text.split("\n"))

        suppliers_text = st.text_area("Suppliers", "\n".join(SUPPLIERS))
        if st.button("Save Suppliers"):
            set_config("suppliers", suppliers_text.split("\n"))

        items_text = st.text_area("Items", "\n".join(ITEMS))
        if st.button("Save Items"):
            set_config("items", items_text.split("\n"))

        st.divider()

        # supplier mapping
        st.subheader("Supplier Access Per Store")

        supplier_map = {}

        for store in STORES:
            st.write(f"**{store}**")
            cols = st.columns(len(SUPPLIERS))

            selected = []
            for i, supplier in enumerate(SUPPLIERS):
                val = cols[i].checkbox(
                    supplier,
                    value=i in STORE_SUPPLIERS.get(store, []),
                    key=f"sup_map_{store}_{i}"
                )
                if val:
                    selected.append(i)

            supplier_map[store] = selected

        if st.button("💾 Save Supplier Mapping"):
            set_config("store_suppliers", supplier_map)
            st.success("✅ Supplier mapping saved")

        st.divider()

        # item mapping
        st.subheader("Item Access Per Store")

        item_map = {}

        for store in STORES:
            st.write(f"**{store}**")
            cols = st.columns(len(ITEMS))

            selected = []
            for i, item in enumerate(ITEMS):
                val = cols[i].checkbox(
                    item,
                    value=i in STORE_ITEMS.get(store, []),
                    key=f"item_map_{store}_{i}"
                )
                if val:
                    selected.append(i)

            item_map[store] = selected

        if st.button("💾 Save Item Mapping"):
            set_config("store_items", item_map)
            st.success("✅ Item mapping saved")

    else:
        st.warning("Enter admin password")

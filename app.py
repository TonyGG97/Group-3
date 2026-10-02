import pandas as pd
import streamlit as st

from config import GROUPS, ROSTER
from store import SQLiteStore, SheetsStore

st.set_page_config(page_title="Group 3 – Pick your station group", page_icon="📋", layout="centered")

GROUP = {g["n"]: g for g in GROUPS}
CAPS = {g["n"]: g["cap"] for g in GROUPS}


def secret(key, default=None):
    """st.secrets raises if no secrets file exists (e.g. running locally), so read it safely."""
    try:
        return st.secrets[key] if key in st.secrets else default
    except Exception:
        return default


@st.cache_resource
def get_store():
    creds, sheet_id = secret("gcp_service_account"), secret("sheet_id")
    if creds and sheet_id:
        return SheetsStore(creds, sheet_id, CAPS)
    return SQLiteStore()


store = get_store()
picks = store.all()
taken = {p["name"]: p["group"] for p in picks}
counts = {n: sum(1 for p in picks if p["group"] == n) for n in GROUP}

st.title("Pick your station group")
st.caption("Choose your name, then one group. Each person can submit once, and a group closes when it is full.")

if not store.durable:
    st.warning("Test mode: picks are saved to a local file and will be lost when the app restarts. "
               "Connect a Google Sheet (see README) before sharing the link.")


def label(n):
    g = GROUP[n]
    left = g["cap"] - counts[n]
    return f"Group {n} · {', '.join(g['stations'])} · Leader: {g['leader']} · {left} spot{'s' if left != 1 else ''} left"


# ---------- already submitted in this browser session ----------
done = st.session_state.get("done")
if done:
    g = GROUP[done["group"]]
    st.success(f"**{done['name']}**, you're in **Group {g['n']}**. You can't submit again.")
    st.write(f"Stations: {', '.join(g['stations'])}")
    st.write(f"Group leader: {g['leader']}")
else:
    available_names = [n for n in ROSTER if n not in taken]
    open_groups = [n for n in GROUP if counts[n] < GROUP[n]["cap"]]

    if not available_names:
        st.info("Everyone on the list has already submitted.")
    elif not open_groups:
        st.error("All groups are full.")
    else:
        name = st.selectbox("1. Your name", available_names, index=None, placeholder="Select your name…")
        grp = st.radio("2. Choose a group", open_groups, index=None, format_func=label)

        full = [n for n in GROUP if n not in open_groups]
        if full:
            st.caption("Full: " + ", ".join(f"Group {n}" for n in full))

        if name and grp:
            if not st.session_state.get("confirm"):
                if st.button("Submit my pick", type="primary", use_container_width=True):
                    st.session_state["confirm"] = True
                    st.rerun()
            else:
                st.warning(f"Confirm: **{name}** → **Group {grp}**. This can't be changed afterwards.")
                c1, c2 = st.columns(2)
                if c1.button("Go back", use_container_width=True):
                    st.session_state["confirm"] = False
                    st.rerun()
                if c2.button("Yes, confirm", type="primary", use_container_width=True):
                    ok, code = store.add(name, grp, GROUP[grp]["cap"])
                    st.session_state["confirm"] = False
                    if ok:
                        st.session_state["done"] = {"name": name, "group": grp}
                    elif code == "already":
                        st.session_state["flash"] = f"{name} has already been submitted. If that wasn't you, tell the organiser."
                    elif code == "full":
                        st.session_state["flash"] = f"Group {grp} just filled up. Please choose another group."
                    else:
                        st.session_state["flash"] = "Couldn't save your pick. Please try again."
                    st.rerun()
        else:
            st.button("Submit my pick", disabled=True, use_container_width=True)

        if st.session_state.get("flash"):
            st.error(st.session_state.pop("flash"))

# ---------- overview ----------
st.divider()
st.subheader(f"Groups so far ({len(picks)} of {len(ROSTER)} have picked)")
for n, g in GROUP.items():
    members = sorted(p["name"] for p in picks if p["group"] == n)
    st.markdown(f"**Group {n}** · {counts[n]}/{g['cap']} · {', '.join(g['stations'])}")
    st.progress(counts[n] / g["cap"])
    st.caption(", ".join(members) if members else "No one yet")

# ---------- organiser panel ----------
with st.sidebar:
    st.header("Organiser")
    admin_pw = secret("admin_password")
    pw = st.text_input("Password", type="password")
    if admin_pw and pw and pw == admin_pw:
        pending = [n for n in ROSTER if n not in taken]
        st.write(f"Still to submit ({len(pending)}):")
        st.caption(", ".join(pending) if pending else "Everyone has submitted.")

        rows = []
        for n in ROSTER:
            g = GROUP.get(taken.get(n))
            rows.append({"Member": n, "Group": f"Group {g['n']}" if g else "", "Leader": g["leader"] if g else "",
                         "Stations": ", ".join(g["stations"]) if g else ""})
        df = pd.DataFrame(rows)
        st.download_button("Download CSV", df.to_csv(index=False).encode(), "Group_3_selections.csv", "text/csv")

        st.divider()
        st.write("Reset a person (lets them submit again):")
        who = st.selectbox("Person", sorted(taken), index=None, placeholder="Select…") if taken else None
        if who and st.button(f"Reset {who}"):
            store.delete(who)
            st.rerun()
    elif pw:
        st.error("Wrong password")
    elif not admin_pw:
        st.caption("Set `admin_password` in the app secrets to enable this panel.")

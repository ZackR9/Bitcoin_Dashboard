import streamlit as st

st.set_page_config(page_title="Portfolio Dashboard", page_icon="📊", layout="wide")

pages = st.navigation([
    st.Page("views/dashboard.py", title="Dashboard", icon="📊", default=True),
    st.Page("views/investment.py", title="Investment", icon="🔎"),
    st.Page("views/data.py", title="Manage Data", icon="🗂️"),
    st.Page("views/tax.py", title="Tax", icon="📋"),
])
pages.run()

# Run: streamlit run app.py  (or: docker compose up -d)

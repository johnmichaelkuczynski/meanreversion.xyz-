"""Two separate public workspaces; Mean Reversion is the default page."""
import streamlit as st

from clean_presentation import apply_clean_presentation
from mean_reversion_workspace import render_mean_reversion_workspace


st.set_page_config(page_title="Mean Reversion", layout="wide")
apply_clean_presentation()

page = st.navigation(
    [
        st.Page(render_mean_reversion_workspace, title="1 · Mean Reversion", default=True),
        st.Page("app.py", title="2 · SOXL", url_path="soxl"),
    ],
    position="top",
)
page.run()

"""Two separate public workspaces; Mean Reversion is the default page."""
import streamlit as st

from clean_presentation import apply_clean_presentation
from zhi_branding import render_zhi_branding
from auth import render_google_login
from site_gate import refresh_site_access


st.set_page_config(page_title="Mean Reversion", layout="wide")
apply_clean_presentation()

branding, account = st.columns([4, 2], vertical_alignment="center")
with branding:
    render_zhi_branding()
with account:
    render_google_login()
refresh_site_access()

# Everyone can open the workspace. Each renderer withholds paid results.
from mean_reversion_workspace import render_mean_reversion_workspace

page = st.navigation(
    [
        st.Page(render_mean_reversion_workspace, title="1 · Mean Reversion", default=True),
        st.Page("app.py", title="2 · SOXL", url_path="soxl"),
    ],
    position="top",
)
page.run()

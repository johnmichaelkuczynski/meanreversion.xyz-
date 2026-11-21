"""Two separate public workspaces; Mean Reversion is the default page."""
import streamlit as st

from clean_presentation import apply_clean_presentation
from zhi_branding import render_zhi_branding
from auth import render_google_login


st.set_page_config(page_title="Mean Reversion", layout="wide")
apply_clean_presentation()

branding, account = st.columns([4, 2], vertical_alignment="center")
with branding:
    render_zhi_branding()
with account:
    render_google_login()
if st.query_params.get("checkout") in {"success", "cancelled"}:
    # Preserve Stripe's optional purchase-return handling; it never gates the app.
    from account_header import _handle_checkout_return
    _handle_checkout_return()

# Sign-in and payment are optional. Every visitor receives the complete workspaces.
from mean_reversion_workspace import render_mean_reversion_workspace

page = st.navigation(
    [
        st.Page(render_mean_reversion_workspace, title="1 · Mean Reversion", default=True),
        st.Page("app.py", title="2 · SOXL", url_path="soxl"),
    ],
    position="top",
)
page.run()

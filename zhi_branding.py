"""Compact, linked ZHI identity shared by the application's pages."""
import base64
from pathlib import Path

import streamlit as st


def render_zhi_branding():
    logo = Path(__file__).resolve().parent / "assets" / "zhi_uploaded_mark.png"
    encoded = base64.b64encode(logo.read_bytes()).decode("ascii")
    st.markdown(
        f"""
        <a href="https://zhisystems.ai" target="_blank" rel="noopener noreferrer"
           aria-label="ZHI SYSTEMS website (opens in a new tab)"
           style="display:inline-flex;flex-direction:column;align-items:center;
                  gap:4px;margin:24px 0 8px;color:#111;text-decoration:none;">
          <img src="data:image/png;base64,{encoded}" alt="ZHI logo"
               width="57" height="58" style="display:block;">
          <span style="font-size:14px;font-weight:700;letter-spacing:0.06em;">
            ZHI SYSTEMS
          </span>
        </a>
        """,
        unsafe_allow_html=True,
    )

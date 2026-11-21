"""Inline, sanitized preview components for the ZHI stock-analysis workspace."""
from html import escape

import streamlit as st


def _text(value, fallback="Unavailable"):
    """Convert a trusted preview field to safe, readable text."""
    if value is None:
        return fallback
    rendered = str(value).strip()
    return rendered if rendered else fallback


def _price(value):
    """Format the actual supplied latest price without deriving other metrics."""
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return _text(value)


def _styles():
    st.markdown(
        """
        <style>
        .zhi-preview-readout {
            color: #111;
            margin: 0.15rem 0 0.7rem;
            line-height: 1.14;
        }
        .zhi-preview-readout .zhi-preview-ticker {
            color: #111;
            font-size: clamp(2.35rem, 7vw, 4.5rem);
            font-weight: 900;
            letter-spacing: -0.055em;
            line-height: 0.98;
            overflow-wrap: anywhere;
        }
        .zhi-preview-readout .zhi-preview-company {
            color: #111;
            font-size: clamp(1.1rem, 2.4vw, 1.55rem);
            font-weight: 750;
            line-height: 1.2;
            margin-top: 0.12rem;
            overflow-wrap: anywhere;
        }
        .zhi-preview-readout .zhi-preview-price {
            color: #111;
            font-size: clamp(1.45rem, 3.2vw, 2rem);
            font-weight: 850;
            letter-spacing: -0.035em;
            line-height: 1.15;
            margin-top: 0.48rem;
            overflow-wrap: anywhere;
        }
        .zhi-preview-readout .zhi-preview-fact {
            color: #111;
            font-size: clamp(1.12rem, 2.5vw, 1.55rem);
            font-weight: 800;
            letter-spacing: -0.025em;
            line-height: 1.22;
            margin-top: 0.27rem;
            overflow-wrap: anywhere;
        }
        .zhi-preview-readout .zhi-preview-through {
            color: #565656;
            font-size: 0.88rem;
            font-weight: 600;
            margin-top: 0.16rem;
        }
        .zhi-preview-redactions {
            border-top: 1px solid #d7d3ca;
            margin: 0.9rem 0 1rem;
            padding-top: 0.7rem;
        }
        .zhi-preview-redactions .zhi-preview-explainer {
            color: #45433f;
            font-size: 0.94rem;
            line-height: 1.45;
            margin: 0 0 0.6rem;
            max-width: 60rem;
        }
        .zhi-preview-redaction {
            align-items: center;
            border-bottom: 1px solid #e4e0d8;
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem 1rem;
            justify-content: space-between;
            padding: 0.56rem 0;
        }
        .zhi-preview-redaction-label {
            color: #171717;
            font-size: clamp(1rem, 2vw, 1.2rem);
            font-weight: 750;
            overflow-wrap: anywhere;
        }
        .zhi-preview-redaction-status {
            color: #625b4e;
            font-size: 0.79rem;
            font-weight: 800;
            letter-spacing: 0.075em;
            white-space: nowrap;
        }
        @media (max-width: 480px) {
            .zhi-preview-redaction {
                align-items: flex-start;
                flex-direction: column;
                gap: 0.18rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_preview_readout(preview: dict) -> None:
    """Show only the real, categorical facts present in a sanitized preview."""
    _styles()
    symbol = escape(_text(preview.get("symbol"), "Ticker unavailable"))
    company = escape(_text(preview.get("company"), "Company name unavailable"))
    price = escape(_price(preview.get("last_price")))
    through = escape(_text(preview.get("through"), "Date unavailable"))
    verdict = escape(_text(preview.get("verdict")))
    pull = escape(_text(preview.get("pull_strength")))
    trend = escape(_text(preview.get("trend")))

    st.markdown(
        f"""
        <section class="zhi-preview-readout" aria-label="Stock analysis preview">
          <div class="zhi-preview-ticker">TICKER: {symbol}</div>
          <div class="zhi-preview-company">Company: {company}</div>
          <div class="zhi-preview-price">Latest price: {price}</div>
          <div class="zhi-preview-through">Through {through}</div>
          <div class="zhi-preview-fact">Verdict: {verdict}</div>
          <div class="zhi-preview-fact">Pull: {pull}</div>
          <div class="zhi-preview-fact">Trend: {trend}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    render_redacted_sections(
        ["Steel hands", "Paper hands", "Exact growth", "Distance from trend"],
        key="preview_readout",
    )


def render_redacted_sections(labels: list[str], key: str) -> None:
    """Render supplied preview-only result labels as visibly redacted rows."""
    del key  # Kept in the public signature for callers' stable component keys.
    _styles()
    rows = "".join(
        (
            '<div class="zhi-preview-redaction">'
            f'<span class="zhi-preview-redaction-label">{escape(_text(label))}</span>'
            '<span class="zhi-preview-redaction-status">REDACTED</span>'
            "</div>"
        )
        for label in labels
    )
    st.markdown(
        '<section class="zhi-preview-redactions" aria-label="Redacted results">'
        '<p class="zhi-preview-explainer">'
        "Full results require Google sign-in and payment."
        "</p>"
        f"{rows}</section>",
        unsafe_allow_html=True,
    )

"""Server-side result redaction shared by public stock and SOXL previews."""
import math

import plotly.graph_objects as go
import streamlit as st

from preview_ui import render_preview_readout, render_redacted_sections


def preview_payload(history, analysis=None, company=""):
    """Whitelist only free fields. Never forward a full model to the browser."""
    pairs = [
        (str(day), float(value))
        for day, value in zip(history.get("dates", []), history.get("prices", []))
        if value is not None and math.isfinite(float(value)) and float(value) > 0
    ][-90:]
    analysis = analysis or {}
    has_mean = bool(analysis.get("has_mean"))
    return {
        "symbol": str(history.get("symbol", "")),
        "company": str(company or "Company name unavailable"),
        "last_price": pairs[-1][1] if pairs else None,
        "through": pairs[-1][0] if pairs else "",
        "verdict": str(analysis.get("verdict", "Analysis unavailable")),
        "pull_strength": str(analysis.get("pull_strength", "Unavailable")) if has_mean else "Insufficient history",
        "trend": ("UP" if analysis.get("slope_pct", 0) > 0 else "NOT UP") if has_mean else "Insufficient history",
        "dates": [p[0] for p in pairs],
        "prices": [p[1] for p in pairs],
    }


def preview_figure(preview):
    """A recent-price-only chart: no model, predictions, hidden traces or scores."""
    figure = go.Figure(go.Scatter(
        x=preview["dates"], y=preview["prices"], mode="lines",
        name=f"{preview['symbol']} · recent price",
        line={"color": "#283d3a", "width": 2.5},
        hovertemplate="%{x}<br>Price: $%{y:,.2f}<extra></extra>",
    ))
    figure.update_layout(
        height=350, margin={"l": 35, "r": 20, "t": 25, "b": 35},
        xaxis_title="Date", yaxis_title="Price (USD)", dragmode="pan",
        showlegend=False,
    )
    return figure


def render_preview_chart(preview, key):
    st.plotly_chart(preview_figure(preview), width="stretch", key=key,
                    config={"displaylogo": False})
    st.caption(
        "Limited preview: latest 90 available closing prices only. Full history, "
        "trend lines, projections, and price probabilities are redacted."
    )
    render_redacted_sections(["Full trend graph and price probabilities"], key + "_graph")


def render_soxl_preview(data):
    """Render the existing SOXL workspace's public subset, not its paid modules."""
    from mean_reversion_winner import analyze_winner
    from site_gate import render_unlock_prompt
    history = {
        "symbol": "SOXL",
        "dates": [str(day.date()) for day in data.index],
        "prices": [float(value) for value in data["Close"]],
    }
    try:
        analysis = analyze_winner(history)
    except Exception:
        analysis = None
    preview = preview_payload(history, analysis, "SOXL · semiconductor leveraged ETF")
    render_preview_readout(preview)
    labels = [
        "Chart & Probabilities", "Vol Surface", "Call Risk/Reward",
        "SOXL-QQQ Dislocation", "Strategy Builder", "Backtest",
        "Area Research", "Diagnostic", "Options Projection",
    ]
    tabs = st.tabs(labels)
    with tabs[0]:
        render_preview_chart(preview, "soxl_public_chart")
    for tab, label in zip(tabs[1:], labels[1:]):
        with tab:
            render_redacted_sections([label], "soxl_" + label)
    render_unlock_prompt("soxl")

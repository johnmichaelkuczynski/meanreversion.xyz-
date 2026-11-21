"""Redact paid outputs without replacing the existing analysis interface."""
from mean_reversion_channels import CHANNELS


def redacted_channel_rows(selected):
    """Preserve the existing three-color panel, never its paid target values."""
    day = selected.isoformat() if hasattr(selected, "isoformat") else str(selected)
    return [
        {"kind": kind, "label": label, "date": day,
         "target_price": "REDACTED", "hit_probability": None,
         "probability_text": "REDACTED"}
        for kind, label, _color in CHANNELS
    ]


def historical_channel(model):
    """Only historical channel geometry is public; no forecast samples."""
    keep = [
        i for i, day in enumerate(model["line_dates"])
        if day <= model["last_date"]
    ]
    result = {
        "last_date": model["last_date"],
        "line_dates": [model["line_dates"][i] for i in keep],
        "lines": {kind: [values[i] for i in keep]
                  for kind, values in model["lines"].items()},
    }
    zone = model.get("lower_buy_zone", [])
    if zone:
        result["lower_buy_zone"] = [zone[i] for i in keep]
    return result


def render_soxl_preview(data):
    """Use the original readout and channel panel, not a replacement sparkline."""
    from datetime import date
    import streamlit as st
    from mean_reversion_winner import analyze_winner
    from mean_reversion_workspace import _cached_channel, _make_figure
    from mean_reversion_chart import render_channel_chart
    from mean_reversion_readout import render_stock_readout
    from preview_ui import render_redacted_sections
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
    last = date.fromisoformat(history["dates"][-1])
    model = _cached_channel(history, last.isoformat())
    render_stock_readout(
        history, "DIREXION DAILY SEMICONDUCTOR BULL 3X SHARES",
        analysis, None, channel=model, redacted=True,
    )
    labels = [
        "Chart & Probabilities", "Vol Surface", "Call Risk/Reward",
        "SOXL-QQQ Dislocation", "Strategy Builder", "Backtest",
        "Area Research", "Diagnostic", "Options Projection",
    ]
    tabs = st.tabs(labels)
    with tabs[0]:
        rows = redacted_channel_rows(last)
        render_channel_chart(
            _make_figure(history, [], model, rows, redacted=True),
            history, model, rows, last, redacted=True,
        )
    for tab, label in zip(tabs[1:], labels[1:]):
        with tab:
            render_redacted_sections([label], "soxl_" + label)
    render_unlock_prompt("soxl")

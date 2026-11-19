"""Declare the SOXL iframe from an importable module on multipage runs."""
import streamlit.components.v1 as components


def declare_soxl_chart(directory, version):
    # Streamlit's page-script namespace is not an importable Python module.
    # Component registration inspects its caller, so keep it in this module.
    return components.declare_component(
        f"chart_draw_{version}", path=str(directory)
    )

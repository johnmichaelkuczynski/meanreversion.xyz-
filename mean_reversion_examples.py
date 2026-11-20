"""Illustrated, perspective-based examples for the Mean Reversion workspace."""

from pathlib import Path

import streamlit as st


_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "mean_reversion"

# These are illustrative user-provided rank orders, not a live score ranking.
RANKING_1_ORDER = [7, 8, 2, 1, 10, 3, 9, 5, 6, 11, 4, 13, 12]
RANKING_2_ORDER = [3, 9, 10, 8, 2, 1, 7, 11, 5, 6, 4, 13, 12]

DRAWING_LABELS = {
    1: "Rising mean · larger swings · slower cycle",
    2: "Rising mean · larger swings · faster cycle",
    3: "Rising mean · close-to-mean movement",
    4: "Flat mean · close-to-mean movement",
    5: "Flat mean · regular swings",
    6: "Declining mean",
    7: "SOXL",
    8: "TQQQ",
    9: "QQQ",
    10: "SOXX",
    11: "Disney",
    12: "GRML",
    13: "ACTG",
}

DESCRIPTIONS = {
    1: "A steeply rising mean with unusually large swings and a slower cycle; a patient options trader may value waiting for a deep dip, while accepting that the setup can take longer to develop.",
    2: "A similar steep rise and large swings on a shorter cycle. The quicker rhythm may offer more frequent dip-and-recovery setups for a patient swing trader.",
    3: "A steeply rising mean with price staying close to it. It suggests strong growth and mean pull, but few deep excursions to exploit as a dip buyer.",
    4: "A flat line hugged closely by price. With little growth and little excursion, it offers neither a compelling growth path nor much swing-trading edge.",
    5: "A flat mean with clear, regular swings. The rhythm may suit a trader who can work the range, but the illustration does not show a growing long-term mean.",
    6: "A declining mean. A deep dip may look tempting to a swing trader, but the broader direction is down rather than growing.",
    7: "SOXL has the steepest illustrated rise and the biggest swings, with clear dips. A skilled options trader who can wait patiently may see opportunity in those deep pullbacks; the same swings can feel punishing to other investors.",
    8: "TQQQ also pairs a rising path with pronounced movement. Its swings can create dip entries for a patient trader, while making the ride less comfortable for a smoother-growth investor.",
    9: "QQQ combines moderate growth with a strong pull toward its mean. It represents a comparatively balanced growth-and-reversion pattern in these illustrations.",
    10: "SOXX shows a rising mean with more edge and volatility than the smoother example. Its growth may appeal to both perspectives, though the larger moves require more tolerance.",
    11: "Disney's illustration wanders for years with weak pull toward a mean. It may be a slower-growth holding, but does not show a clear reversion pattern to trade.",
    12: "GRML has no established mean in this illustration, so there is not a stable reference line from which to assess pull or a dip-buying setup.",
    13: "ACTG is illustrated as a boom, a bust, and then a long flatline. A temporary surge is not sustained growth or a dependable return to a rising mean.",
}

# Perspective-specific significance keeps each drawing's placement meaningful.
RANKING_1_DESCRIPTIONS = {
    7: "First for this perspective: steepest rise, biggest swings, and clear dips. The potential setup depends on waiting for deep pullbacks without chasing or panicking.",
    8: "Pronounced swings around a rising path can create dip opportunities for a patient trader, though the wait and volatility still matter.",
    2: "Large swings with a faster cycle make the illustrated dips arrive more often than in drawing 1, while retaining a steep rising mean.",
    1: "The steep rise and huge swings may suit a patient options approach, but its slower cycle means waiting longer for a deep entry.",
    10: "A rising path with more volatility than a smooth-growth profile gives swing traders room to watch for pullbacks.",
    3: "Strong growth and close tracking of the mean are attractive qualities, but the few deep dips leave less to exploit as a dip buyer.",
    9: "Moderate growth and strong mean pull offer a more measured mix, with less dramatic dip opportunities than the top-ranked examples.",
    5: "Clear, regular swings can be tradable even without mean growth; the case here is the range, not long-term appreciation.",
    6: "Only deep dips may be worth considering for a swing trade, because the underlying mean is declining.",
    11: "Weak pull and years of wandering make repeatable mean-reversion entries less apparent in this illustration.",
    4: "A flat mean closely followed by price leaves little growth and little swing distance to trade.",
    13: "A boom followed by a bust and a long flatline is not a dependable dip-and-return pattern around a rising mean.",
    12: "Without an established mean, the illustration provides no stable reference for identifying a reversion trade.",
}

RANKING_2_DESCRIPTIONS = {
    3: "First for this perspective: a steeply rising mean with a smooth path that stays close. It illustrates growth without large departures from trend.",
    9: "Moderate growth and strong mean pull offer a comparatively measured path for an investor who values steadier movement.",
    10: "SOXX still has a rising mean, but its edgier, more volatile movement makes it less smooth than the leaders above.",
    8: "TQQQ's rising path is accompanied by substantial swings. Those moves can feel like bad news to an investor prioritizing a smoother ride.",
    2: "A steep rise is offset by large swings; the faster cycle may also make the movement more noticeable.",
    1: "The rising mean is paired with huge, slower-cycle swings, requiring patience through potentially uncomfortable departures.",
    7: "SOXL combines the steepest illustrated rise with the biggest swings. That volatility is a substantial mismatch for a smoother-growth preference.",
    11: "Disney suggests slow growth with weak mean pull and long periods of wandering, rather than a smooth, clearly reverting path.",
    5: "Regular swings may be orderly, but the flat mean does not illustrate long-term growth.",
    6: "A declining mean conflicts with a steady-growth objective, even if a deep dip may attract a trader.",
    4: "Price hugs a flat mean: little volatility, but also little illustrated growth.",
    13: "The boom, bust, and long flatline combine an uneven ride with no sustained growth around a rising mean.",
    12: "There is no established mean to anchor a steady-growth or mean-reversion interpretation.",
}

IMAGE_PATHS = {
    drawing: next(
        (str(path) for path in _ASSET_DIR.glob(f"drawing{drawing}.png")),
        None,
    )
    for drawing in range(1, 14)
}


def _render_ranking(title, audience, order, descriptions):
    st.subheader(title)
    st.caption(audience)
    # A scrollable, always-open region keeps the full ranking available without
    # letting the examples overwhelm the existing research workspace.
    with st.container(height=760, border=True):
        for rank, drawing in enumerate(order, start=1):
            with st.container(border=True):
                image_col, text_col = st.columns([1, 1.45], vertical_alignment="center")
                with image_col:
                    image_path = IMAGE_PATHS[drawing]
                    if image_path:
                        st.image(image_path, use_container_width=True)
                    else:
                        st.caption(f"Drawing {drawing} image was not supplied.")
                with text_col:
                    st.markdown(f"**{rank}. Drawing {drawing} · {DRAWING_LABELS[drawing]}**")
                    st.write(descriptions[drawing])


def render_illustrated_rankings():
    """Show the two illustrative perspectives and their drawing significance."""
    st.header("Same stock, different investor")
    st.write(
        "Pull toward the mean is not a crossing count. Growth, swing size, and an "
        "investor's tolerance for those swings all matter: a stock may suit a patient "
        "swing trader while feeling too volatile to a smoother-growth investor."
    )
    st.caption(
        "These user-provided rankings are illustrative perspectives, not the live "
        "computed score order. The workspace's scores and calculations are unchanged."
    )
    st.caption("Drawings 6, 7, and 8 were not supplied; their ranked descriptions are included below.")
    _render_ranking(
        "Ranking 1 · Most money to be made",
        "Assumes skill, patience for deep dips, and the discipline not to panic, chase, or doubt the setup.",
        RANKING_1_ORDER,
        RANKING_1_DESCRIPTIONS,
    )
    _render_ranking(
        "Ranking 2 · Steady growth without the whipsaw",
        "For an investor who sees large swings in SOXL or TQQQ as bad news, even when the mean is rising.",
        RANKING_2_ORDER,
        RANKING_2_DESCRIPTIONS,
    )

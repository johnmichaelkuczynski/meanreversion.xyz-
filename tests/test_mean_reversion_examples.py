from pathlib import Path

from streamlit.testing.v1 import AppTest

from mean_reversion_examples import (
    IMAGE_PATHS, RANKING_1_DESCRIPTIONS, RANKING_1_ORDER,
    RANKING_2_DESCRIPTIONS, RANKING_2_ORDER,
)


def test_both_orders_preserve_the_supplied_rankings():
    assert RANKING_1_ORDER == [7,8,2,1,10,3,9,5,6,11,4,13,12]
    assert RANKING_2_ORDER == [3,9,10,8,2,1,7,11,5,6,4,13,12]
    for order, descriptions in (
        (RANKING_1_ORDER, RANKING_1_DESCRIPTIONS),
        (RANKING_2_ORDER, RANKING_2_DESCRIPTIONS),
    ):
        assert set(order) == set(range(1,14)) == set(descriptions)
        assert all(len(descriptions[drawing]) > 50 for drawing in order)


def test_only_real_supplied_images_are_used():
    assert {n for n,path in IMAGE_PATHS.items() if path is None} == {6,7,8}
    assert len([p for p in IMAGE_PATHS.values() if p]) == 10
    assert all(Path(p).is_file() for p in IMAGE_PATHS.values() if p)


def test_each_ranking_renders_its_images_and_significance():
    app = AppTest.from_string(
        "from mean_reversion_examples import render_illustrated_rankings\n"
        "render_illustrated_rankings()",
        default_timeout=15,
    ).run()
    assert not app.exception
    assert len(app.subheader) == 2
    assert len(app.get("imgs")) == 20
    assert len([m for m in app.markdown if m.value.startswith("**")]) == 26
    notices = [c for c in app.caption if "image was not supplied" in c.value]
    assert len(notices) == 6
    source = Path("mean_reversion_workspace.py").read_text()
    assert source.index("st.plotly_chart(") < source.index("    render_illustrated_rankings()")

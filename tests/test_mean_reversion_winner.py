import numpy as np
import pandas as pd
import pytest

from mean_reversion_winner import (
    CONFIG, REFERENCE_SYMBOLS, analyze_winner, excursion_statistics,
    fit_winner_channel, normalize_scores,
)


def history(years=12, growth=.15, width=.2, symbol="TEST"):
    dates = pd.bdate_range("2000-01-03", periods=int(years * 252))
    t = np.asarray((dates - dates[0]).days) / 365.25
    prices = np.exp(3 + np.log1p(growth)*t + width*np.sin(t*2*np.pi))
    return {"symbol": symbol, "dates": dates.strftime("%Y-%m-%d").tolist(),
            "prices": prices.tolist()}


def test_exact_full_history_fit_and_scores():
    h = history()
    a = analyze_winner(h)
    t = np.asarray((pd.to_datetime(h["dates"]) - pd.Timestamp(h["dates"][0])).days)/365.25
    g, intercept = np.polyfit(t, np.log(h["prices"]), 1)
    assert a["slope"] == pytest.approx(g)
    assert a["intercept"] == pytest.approx(intercept)
    assert a["winner"]
    assert a["raw_scores"]["steel"] == pytest.approx(a["growth"]*a["pull"]*(1+a["swing"]))
    assert a["raw_scores"]["paper"] == pytest.approx(a["growth"]*a["pull"]/(1+3*a["swing"])**4)
    residual = np.log(h["prices"])-(intercept+g*t)
    smoothed = pd.Series(residual).rolling(20).mean().dropna()
    assert a["longest_excursion"] == pytest.approx(excursion_statistics(smoothed)[0])
    assert a["swing"] == pytest.approx(np.std(residual))
    assert a["position_pct"] == pytest.approx(np.expm1(residual[-1])*100)


def test_excursion_area_includes_open_boundary_and_zeros():
    area, years, peak = excursion_statistics([1,1,-2,-2,0,3,3,3])
    assert area == pytest.approx(9/252)
    assert years == pytest.approx(3/252)
    assert peak == pytest.approx(np.expm1(3)*100)
    assert excursion_statistics([0,0,0]) == (0,0,0)


def test_duration_and_largest_area_are_separate():
    area, years, _ = excursion_statistics([.1]*10+[-3]*2)
    assert area == pytest.approx(6/252)
    assert years == pytest.approx(10/252)


@pytest.mark.parametrize("growth,verdict,range_trade", [
    (.15,"WINNER",False), (0,"NOT A GROWTH STOCK",True),
    (-.05,"NOT A GROWTH STOCK",True), (-.2,"NOT A GROWTH STOCK",False),
])
def test_verdict_growth_threshold(growth,verdict,range_trade):
    a = analyze_winner(history(growth=growth, width=.01))
    assert a["verdict"] == verdict
    assert a["range_tradeable"] == range_trade
    if not a["winner"]:
        assert a["raw_scores"] == {"steel":0,"paper":0}


def test_short_history_overrides_all_other_verdicts():
    a = analyze_winner(history(years=4))
    assert a["verdict"] == "NO MEAN YET"
    assert not a["has_mean"] and not a["buy_zone"]


def test_large_long_excursions_fail_pull_gate_despite_growth():
    h = history(years=40, width=0)
    time = np.linspace(0, 4*np.pi, len(h["prices"]))
    h["prices"] = (np.array(h["prices"]) * np.exp(5*np.cos(time))).tolist()
    a = analyze_winner(h)
    assert a["growth"] > .05
    assert a["pull"] < .5
    assert a["verdict"] == "NO RELIABLE MEAN"
    assert a["raw_scores"] == {"steel":0,"paper":0}


def test_normalization_fixed_set_and_capping():
    a = analyze_winner(history())
    refs = {s:a for s in REFERENCE_SYMBOLS}
    assert normalize_scores(a,refs) == pytest.approx({"steel":100,"paper":100})
    with pytest.raises(ValueError,match="SPY"):
        normalize_scores(a,{s:a for s in REFERENCE_SYMBOLS[:-1]})
    high = {**a,"raw_scores":{"steel":1e6,"paper":1e6}}
    assert normalize_scores(high,refs) == {"steel":100,"paper":100}


def test_chart_mean_and_buy_zone_use_same_fit_and_future_date():
    h = history()
    a = analyze_winner(h)
    channel = fit_winner_channel(h,"2030-01-01")
    assert channel["line_dates"][-1] == "2030-01-01"
    assert channel["intercepts"]["median"] == a["intercept"]
    assert np.log(np.array(channel["lower_buy_zone"])/channel["lines"]["median"]) == pytest.approx(
        np.full(len(channel["line_dates"]),-.5*a["swing"]))
    assert set(channel["lines"]) == {"upper","median","lower"}
    assert CONFIG["pull_scale"] == 8

import numpy as np
import pandas as pd
import pytest

from mean_reversion_winner import CONFIG, analyze_winner, fit_winner_channel, rolling_trends
from mean_reversion_recovery import recovery_components, recovery_events
from mean_reversion_weights import weighted_fit, weighted_std

# Archived recovery utilities remain independently testable; they do not define
# the current excursion scorer's configuration or verdict.
RECOVERY_CONFIG = {
    "calendar_days": 365.25,
    "band_fraction": .10, "remaining_gap_fraction": .50, "maturity_years": 5,
    "minimum_mature_events": 3, "recovery_years": (5, 3, 1),
    "recovery_weights": (.90, .075, .025), "depth_scale": .50,
    "minimum_mature_downside_events": 3,
}


def history(years=25, growth=.15, width=.20, symbol="ANONYMOUS"):
    dates = pd.bdate_range("1980-01-01", periods=int(years*252))
    t = np.asarray((dates-dates[0]).days)/365.25
    return {"symbol": symbol, "dates": dates.strftime("%Y-%m-%d").tolist(),
            "prices": np.exp(3+np.log1p(growth)*t+width*np.sin(t*2*np.pi/2)).tolist()}


def test_rolling_predictions_match_direct_excluded_close_ols():
    h = history()
    dates, prices, indices, trends, slopes, intercepts, _ = rolling_trends(h)
    t = np.asarray((dates-dates[0]).days)/365.25
    for offset in (0, len(indices)//2, len(indices)-1):
        index = indices[offset]
        start = dates.searchsorted(dates[index]-pd.DateOffset(years=5))
        slope, intercept = np.polyfit(t[start:index], np.log(prices[start:index]), 1)
        assert slopes[offset] == pytest.approx(slope, abs=1e-9)
        assert intercepts[offset] == pytest.approx(intercept, abs=1e-9)
        assert trends[offset] == pytest.approx(intercept+slope*t[index], abs=1e-9)


def test_scored_close_and_future_prices_cannot_change_its_fit():
    h = history()
    dates, _, indices, trends, slopes, _, _ = rolling_trends(h)
    offset = len(indices)//2
    index = indices[offset]
    changed = {**h, "prices": list(h["prices"])}
    changed["prices"][index:] = (np.asarray(changed["prices"][index:])*4).tolist()
    other = rolling_trends(changed)
    assert other[3][offset] == pytest.approx(trends[offset], abs=1e-10)
    assert other[4][offset] == pytest.approx(slopes[offset], abs=1e-10)
    assert dates[indices[0]] >= dates[0]+pd.DateOffset(years=5)


def test_event_count_only_rearms_after_band_return():
    dates = pd.date_range("2000-01-01", periods=8)
    prices = np.array([120, 130, 125, 104, 80, 79, 100, 120])
    events = recovery_events(dates, prices, np.arange(8), np.full(8, np.log(100)),
                             np.zeros(8), RECOVERY_CONFIG)
    assert [e["opened"] for e in events] == ["2000-01-01", "2000-01-05", "2000-01-08"]
    assert events[0]["recovered_on"] == "2000-01-04"
    assert events[1]["recovered_on"] == "2000-01-07"


def test_unfinished_crash_is_included_in_excursion_area():
    h = history(years=22, growth=0, width=0)
    crash = 2520
    h["prices"][crash:] = [4.]*(len(h["prices"])-crash)
    a = analyze_winner(h)
    assert a["excursions"][-1]["ongoing"]
    assert a["excursions"][-1]["ended"] == h["dates"][-1]
    assert a["excursions"][-1]["size"] > 0
    assert a["longest_excursion"] == max(e["size"] for e in a["excursions"])


def test_same_mature_events_for_all_recovery_percentages_and_failures_count():
    def event(recovered, one=False, three=False, mature=True, depth=.4):
        return {"mature": mature, "direction": "downside", "recovered": recovered,
                "opening_depth": depth, "recovered_within": {"5": recovered, "3": three, "1": one}}
    events = [event(True, True, True), event(True, three=True), event(False),
              event(True, True, True, mature=False)]
    result = recovery_components(events, RECOVERY_CONFIG)
    assert result["mature_count"] == 3 and result["newer_count"] == 1
    assert result["recovery_fractions"] == pytest.approx({"5": 2/3, "3": 2/3, "1": 1/3})
    assert result["recovery_score"] == pytest.approx(100*(.9*2/3+.075*2/3+.025/3))
    assert result["depth_bonus"] == pytest.approx(.4/.5*2/3)
    assert recovery_components(events[:2], RECOVERY_CONFIG)["recovery_score"] is None
    assert recovery_components(events[:2], RECOVERY_CONFIG)["depth_bonus"] == 0


def test_weighted_pull_and_hand_scores_use_exact_formulas_and_one_verdict():
    a = analyze_winner(history())
    assert a["pull"] == pytest.approx(1/(1+a["longest_excursion"]/8))
    assert a["raw_scores"]["steel"] == pytest.approx(a["growth"]*a["pull"]*(1+a["swing"]))
    assert a["raw_scores"]["paper"] == pytest.approx(a["growth"]*a["pull"]/(1+3*a["swing"])**4)
    expected = a["growth"] >= .12 and a["pull"] >= .5
    assert a["winner"] == expected
    assert a["verdict"] == "WINNER"


def test_ticker_names_cannot_affect_results():
    a = analyze_winner(history(symbol="HIDDEN_A"))
    b = analyze_winner(history(symbol="MSFT"))
    assert a["raw_scores"] == b["raw_scores"]
    assert a["pull"] == b["pull"]
    assert a["slope_pct"] == b["slope_pct"]


def test_short_history_keeps_actual_prices_but_does_not_invent_prior_fit():
    h = history(years=4)
    a = analyze_winner(h)
    model = fit_winner_channel(h)
    assert not a["has_mean"]
    assert a["pull"] is None
    assert a["verdict"] == "NO MEAN YET — not a winner"
    assert a["scores"] == {"steel": 0., "paper": 0.}
    assert model["prices"] == h["prices"]


def test_plot_uses_historical_predictions_and_projects_latest_fit():
    h = history()
    a = analyze_winner(h)
    model = fit_winner_channel(h, "2030-01-01")
    assert model["line_dates"][:len(a["trend_dates"])] == a["trend_dates"]
    assert model["lines"]["median"][:len(a["trend_dates"])] == pytest.approx(a["trend_prices"])
    assert model["line_dates"][-1] == "2030-01-01"
    years = (pd.Timestamp("2030-01-01")-pd.Timestamp(a["origin"])).days/365.25
    assert model["lines"]["median"][-1] == pytest.approx(np.exp(a["intercept"]+a["slope"]*years))
    assert model["slope"] == pytest.approx(a["slope"])
    assert model["intercepts"]["median"] == pytest.approx(a["intercept"])


def test_fit_uses_sqrt_recency_weights_not_squared_or_unweighted_weights():
    h = history()
    # Add a regime change so an unweighted or incorrectly squared fit fails.
    dates = pd.to_datetime(h["dates"])
    t = np.asarray((dates-dates[0]).days)/365.25
    h["prices"] = (np.asarray(h["prices"])*np.exp(.015*t*t)).tolist()
    f = weighted_fit(h)
    w = .5**((t[-1]-t)/7)
    g, a = np.polyfit(t, np.log(h["prices"]), 1, w=np.sqrt(w))
    assert f["slope"] == pytest.approx(g, abs=1e-12)
    assert f["intercept"] == pytest.approx(a, abs=1e-12)
    assert abs(g-np.polyfit(t, np.log(h["prices"]), 1)[0]) > .01
    x = np.log(h["prices"])-a-g*t
    assert f["swing"] == pytest.approx(np.sqrt(np.average(x*x, weights=w)))
    r = np.diff(np.log(h["prices"]))
    expected_vol = np.sqrt(np.average((r-np.average(r, weights=w[1:]))**2, weights=w[1:])*252)
    assert f["volatility"] == pytest.approx(expected_vol)


def test_excursions_weight_area_and_include_open_ends():
    from mean_reversion_winner import weighted_excursions
    dates = pd.bdate_range("2000-01-01", periods=100)
    x = np.r_[np.ones(50), -np.ones(50)]
    weights = np.linspace(.1, 1., 100)
    events = weighted_excursions(x, weights, dates)
    smooth = pd.Series(x).rolling(20, min_periods=1).mean().to_numpy()
    assert sum(e["size"] for e in events) == pytest.approx(sum(abs(smooth)*weights)/252)
    assert len(events) == 2
    assert events[0]["side"] == "Above" and events[1]["side"] == "Below"
    assert not events[0]["ongoing"] and events[1]["ongoing"]


def test_twelve_percent_growth_threshold_is_shared_and_non_winners_score_zero():
    a = analyze_winner(history(growth=.086, width=0))
    assert a["slope_pct"] == pytest.approx(8.6)
    assert a["pull"] > .8
    assert a["verdict"] == "NOT A GROWTH STOCK — not a winner"
    assert not a["winner"]
    assert a["raw_scores"] == {"steel": 0., "paper": 0.}


def test_score_normalization_requires_the_complete_fixed_reference_set():
    from mean_reversion_winner import normalize_scores
    a = analyze_winner(history())
    references = [{**a, "symbol": s} for s in CONFIG["reference_symbols"]]
    assert normalize_scores(a, references) == {"steel": 100., "paper": 100.}
    assert normalize_scores(a, references[:-1]) == {"steel": None, "paper": None}


@pytest.mark.parametrize("field,values", [
    ("prices", [0, 2]), ("prices", [1, float("nan")]),
    ("dates", ["2000-01-01", "2000-01-01"]),
])
def test_invalid_prices_and_dates_fail_explicitly(field, values):
    h = {"symbol": "X", "dates": ["2000-01-01", "2000-01-02"], "prices": [1, 2]}
    with pytest.raises(ValueError):
        analyze_winner({**h, field: values})

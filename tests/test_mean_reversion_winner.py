import numpy as np
import pandas as pd
import pytest

from mean_reversion_winner import CONFIG, analyze_winner, fit_winner_channel, rolling_trends
from mean_reversion_recovery import recovery_components, recovery_events


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
                             np.zeros(8), CONFIG)
    assert [e["opened"] for e in events] == ["2000-01-01", "2000-01-05", "2000-01-08"]
    assert events[0]["recovered_on"] == "2000-01-04"
    assert events[1]["recovered_on"] == "2000-01-07"


def test_unrecovered_crash_does_not_get_credit_from_lower_later_fit():
    h = history(years=22, growth=0, width=0)
    crash = 2520
    h["prices"][crash:] = [4.]*(len(h["prices"])-crash)
    a = analyze_winner(h)
    event = next(e for e in a["mature_events"] if e["opened"] == h["dates"][crash])
    assert event["direction"] == "downside"
    assert event["recovered"] is False
    assert all(not recovered for recovered in event["recovered_within"].values())
    assert a["trend_prices"][-1] == pytest.approx(4.)


def test_same_mature_events_for_all_recovery_percentages_and_failures_count():
    def event(recovered, one=False, three=False, mature=True, depth=.4):
        return {"mature": mature, "direction": "downside", "recovered": recovered,
                "opening_depth": depth, "recovered_within": {"5": recovered, "3": three, "1": one}}
    events = [event(True, True, True), event(True, three=True), event(False),
              event(True, True, True, mature=False)]
    result = recovery_components(events, CONFIG)
    assert result["mature_count"] == 3 and result["newer_count"] == 1
    assert result["recovery_fractions"] == pytest.approx({"5": 2/3, "3": 2/3, "1": 1/3})
    assert result["recovery_score"] == pytest.approx(100*(.9*2/3+.075*2/3+.025/3))
    assert result["depth_bonus"] == pytest.approx(.4/.5*2/3)
    assert recovery_components(events[:2], CONFIG)["recovery_score"] is None
    assert recovery_components(events[:2], CONFIG)["depth_bonus"] == 0


def test_latest_scores_use_exact_absolute_formulas_and_one_shared_verdict():
    a = analyze_winner(history())
    assert a["mean_reversion_score"] == max(a["closeness_score"], a["recovery_score"])
    base = 100*np.sqrt(np.clip(a["median_growth"]/.35, 0, 1)*a["mean_reversion_score"]/100)
    assert a["scores"]["steel"] == pytest.approx(base*(.75+.25*a["depth_bonus"]))
    assert a["scores"]["paper"] == pytest.approx(
        base*(.70+.30*a["positive_year_fraction"])*(1-.65*a["drawdown_factor"]))
    expected = a["median_growth"] >= .05 and a["positive_year_fraction"] >= .60 and a["mean_reversion_score"] >= 60
    assert a["winner"] == expected
    assert a["verdict"] == ("WINNER" if expected else "NOT A WINNER")
    assert all(0 <= value <= 100 for value in a["scores"].values())


def test_ticker_names_cannot_affect_results_and_year_end_excludes_partial_year():
    a = analyze_winner(history(symbol="HIDDEN_A"))
    b = analyze_winner(history(symbol="MSFT"))
    assert a["scores"] == b["scores"]
    assert a["mean_reversion_score"] == b["mean_reversion_score"]
    assert max(map(int, a["year_end_slopes"])) < int(a["trend_dates"][-1][:4])


def test_short_history_keeps_actual_prices_but_does_not_invent_prior_fit():
    h = history(years=4)
    a = analyze_winner(h)
    model = fit_winner_channel(h)
    assert not a["has_mean"]
    assert a["mean_reversion_score"] is None
    assert a["scores"] == {"steel": None, "paper": None}
    assert model["prices"] == h["prices"] and model["line_dates"] == []


def test_plot_uses_historical_predictions_and_projects_latest_fit():
    h = history()
    a = analyze_winner(h)
    model = fit_winner_channel(h, "2030-01-01")
    assert model["line_dates"][:len(a["trend_dates"])] == a["trend_dates"]
    assert model["lines"]["median"][:len(a["trend_dates"])] == pytest.approx(a["trend_prices"])
    assert model["line_dates"][-1] == "2030-01-01"
    years = (pd.Timestamp("2030-01-01")-pd.Timestamp(a["origin"])).days/365.25
    assert model["lines"]["median"][-1] == pytest.approx(np.exp(a["intercept"]+a["slope"]*years))
    assert np.asarray(model["lower_buy_zone"])/model["lines"]["median"] == pytest.approx(.9)


@pytest.mark.parametrize("field,values", [
    ("prices", [0, 2]), ("prices", [1, float("nan")]),
    ("dates", ["2000-01-01", "2000-01-01"]),
])
def test_invalid_prices_and_dates_fail_explicitly(field, values):
    h = {"symbol": "X", "dates": ["2000-01-01", "2000-01-02"], "prices": [1, 2]}
    with pytest.raises(ValueError):
        analyze_winner({**h, field: values})

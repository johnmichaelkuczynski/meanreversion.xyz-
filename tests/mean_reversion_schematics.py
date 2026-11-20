"""Numerical approximations of the drawings, not digitized market histories.

All analyses receive the same neutral symbol. Shape IDs are attached only after
scoring; no calculation can use an expected ticker or rank.
"""
import numpy as np
import pandas as pd


def schematic_series():
    dates = pd.bdate_range("1980-01-01", "2026-11-18")
    t = np.asarray((dates-dates[0]).days)/365.25
    n = len(t)
    def series(number, logs, subset=None):
        selected_dates = dates if subset is None else dates[subset]
        return number, {"symbol": "HIDDEN", "dates": selected_dates.strftime("%Y-%m-%d").tolist(),
                        "prices": np.exp(logs).tolist(), "source": "anonymous schematic approximation"}
    baseline = 4.
    result = [
        series(1, baseline+.20*t+1.4*np.sin(2*np.pi*t/8)),
        series(2, baseline+.20*t+1.4*np.sin(2*np.pi*t/4)),
        series(3, baseline+.20*t+.02*np.sin(2*np.pi*t/8)),
        series(4, baseline+.02*np.sin(2*np.pi*t/8)),
        series(5, baseline+.35*np.sin(2*np.pi*(t-t[-1])/2-np.pi/2)),
        series(6, baseline-.08*t+.35*np.sin(2*np.pi*t/2)),
        series(7, baseline+.35*t+1.1*np.sin(2*np.pi*t/3)),
        series(8, baseline+.27*t+.7*np.sin(2*np.pi*t/3)),
        series(9, baseline+.12*t+.23*np.sin(2*np.pi*t/3)),
        series(10, baseline+.18*t+.4*np.sin(2*np.pi*t/3)),
        series(11, baseline+.04*t+1.2*np.sin(2*np.pi*t/28)),
    ]
    short = np.arange(n-630, n)
    short_time = t[short]-t[short[0]]
    result.append(series(12, baseline-.8*short_time+.3*np.sin(2*np.pi*short_time), short))
    boom_bust = baseline-.025*t+1.8*np.exp(-((t-15)/3)**2)-.65/(1+np.exp(-(t-24)))
    boom_bust += .03*np.sin(2*np.pi*t/2)
    result.append(series(13, boom_bust))
    return result


def qualified_flat_deep_dip():
    dates = pd.bdate_range("1980-01-01", "2026-11-18")
    prices = np.full(len(dates), 100.)
    for year in range(1987, 2020, 3):
        start = dates.searchsorted(pd.Timestamp(f"{year}-07-01"))
        prices[start:start+30] = 50
    prices[-20:] = 40
    return {"symbol": "HIDDEN", "dates": dates.strftime("%Y-%m-%d").tolist(),
            "prices": prices.tolist(), "source": "anonymous qualified deep-dip fixture"}

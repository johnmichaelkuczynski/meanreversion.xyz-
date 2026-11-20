"""Departure events evaluated only against their frozen opening-day trend."""
import numpy as np
import pandas as pd


def recovery_events(dates, prices, indices, trend_logs, slopes, config):
    logs = np.log(prices)
    events = []
    outside_episode = False
    for offset, index in enumerate(indices):
        opening_gap = float(logs[index] - trend_logs[offset])
        percent_gap = float(np.expm1(opening_gap))
        outside = abs(percent_gap) > config["band_fraction"]
        if not outside:
            outside_episode = False
            continue
        if outside_episode:
            continue
        outside_episode = True
        opening = dates[index]
        end = opening + pd.DateOffset(years=config["maturity_years"])
        stop = dates.searchsorted(end, side="right")
        following = np.arange(index + 1, stop)
        elapsed = np.asarray((dates[following] - opening).days, dtype=float) / config["calendar_days"]
        frozen = trend_logs[offset] + slopes[offset] * elapsed
        future_gap = logs[following] - frozen
        threshold = opening_gap * config["remaining_gap_fraction"]
        recovered = future_gap >= threshold if opening_gap < 0 else future_gap <= threshold
        matches = np.flatnonzero(recovered)
        recovery = dates[following[matches[0]]] if len(matches) else None
        events.append({
            "opened": opening.date().isoformat(),
            "direction": "downside" if opening_gap < 0 else "upside",
            "opening_gap_log": opening_gap,
            "opening_depth": abs(percent_gap),
            "frozen_trend_log": float(trend_logs[offset]),
            "frozen_slope": float(slopes[offset]),
            "mature": bool(dates[-1] >= end),
            "recovered": recovery is not None,
            "recovered_on": recovery.date().isoformat() if recovery is not None else None,
            "recovered_within": {
                str(year): bool(recovery is not None and recovery <= opening + pd.DateOffset(years=year))
                for year in config["recovery_years"]
            },
        })
    return events


def recovery_components(events, config):
    mature = [event for event in events if event["mature"]]
    newer = [event for event in events if not event["mature"]]
    enough = len(mature) >= config["minimum_mature_events"]
    fractions = {
        str(year): (sum(event["recovered_within"][str(year)] for event in mature) / len(mature)
                    if mature else None)
        for year in config["recovery_years"]
    }
    score = (100 * sum(weight * fractions[str(year)] for year, weight in
                       zip(config["recovery_years"], config["recovery_weights"]))
             if enough else None)
    downside = [event for event in mature if event["direction"] == "downside"]
    recovered_downside = [event for event in downside if event["recovered"]]
    fraction = len(recovered_downside) / len(downside) if downside else None
    median_depth = (float(np.median([event["opening_depth"] for event in recovered_downside]))
                    if recovered_downside else 0.)
    bonus = (min(1., median_depth / config["depth_scale"]) * fraction
             if len(downside) >= config["minimum_mature_downside_events"] else 0.)
    return {
        "mature_events": mature, "newer_events": newer,
        "mature_count": len(mature), "newer_count": len(newer),
        "recovery_fractions": fractions, "recovery_score": score,
        "downside_count": len(downside), "downside_recovery_fraction": fraction,
        "recovered_downside_median_depth": median_depth, "depth_bonus": float(bonus),
    }

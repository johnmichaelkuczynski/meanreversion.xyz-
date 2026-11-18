---
name: Mean reversion statistics
description: Interpretation of Hurst and half-life comparisons.
---

Use R/S on close-to-close log increments, not raw nonstationary price levels, when interpreting H near 0.5 as random-walk behavior. Show the unbounded raw finite-sample H estimate; clamp only the requested score.

**Why:** Applying ordinary R/S directly to price levels can mislabel a random walk as strongly persistent. Anti-persistence is not proof of price-level stationarity or profitability.

**How to apply:** Preserve that distinction in tooltips and future model integrations. Half-life from price-level change regression is a separate descriptive estimate, not a calibrated buy/sell signal.

The user's revised brief separates memory (Hurst) from drift (MA200 slope), then combines them in the K Metric. K is explicitly an unvalidated screening/ranking heuristic, not a proven edge or replacement for either input.

**Why:** The user corrected their earlier understanding of Hurst and explicitly required independent layers, including warnings for reversion around a falling mean.

**How to apply:** Preserve downside labels even when edge-only K is zero. Keep trend computation independent of the adjustable Hurst window; an MA200 comparison 60 sessions apart needs 260 closes.

Keep simulation evidence separate from the user's raw H-based score. A Gaussian random-walk sampling range is not an asset-specific confidence interval, and anti-persistence evidence does not validate price-level half-life.

**Why:** Short-window R/S has substantial finite-sample upward bias. Correcting the user's formula would change its meaning; a separate reference comparison conveys uncertainty without redefining it.

**How to apply:** Use exact usable sample counts for calibration; do not silently substitute a nearby window. Recalibrate whenever the estimator changes and disclose model assumptions and selection effects.

The log-trend / AR(1) Mean Reversion tool is a strictly independent addition,
not a replacement for Hurst, K, SOXL signals, hand-drawn channels, or the
existing projection probabilities. A failed reliability gate must not be
relaxed to produce trend lines or an attractive verdict.

**Why:** The user explicitly required a separate model and chart while
preserving every existing feature, default, provider, and key. Full-history
log-trend stationarity is a different claim from anti-persistent increments.

**How to apply:** Keep the two interpretations separate, use adjusted closes
for the new model, and label Monte Carlo touches as conditional model
estimates rather than empirically calibrated success rates.

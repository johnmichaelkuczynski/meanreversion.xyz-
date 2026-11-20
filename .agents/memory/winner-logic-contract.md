---
name: Mean Reversion scoring contract
description: User's seven-year recency weighting, excursion Pull, growth threshold, and illustrated rankings.
---

Page-one scoring must use full adjusted-close history with a seven-year recency
half-life, including the straight displayed mean. The user explicitly restored
excursion-area Pull and required a 12% annual growth threshold.

**Why:** The user identified unweighted MSFT/AAPL/COST/INTC slopes as evidence of
the wrong implementation and explicitly required weighted fitting, swing,
excursion sizes, volatility, and Pull instead of the rolling reversion score.

**How to apply:** Do not restore rolling five-year recovery scoring, cycle-count
gates, or unweighted OLS. Weight by `0.5 ** (age_in_years / 7)` and pass square
roots of those weights to polynomial fitting. Preserve fixed straight chart
lines and long future extension. The chart, displayed slope, and position must
refer to the same weighted fitted mean.

Show Pull strength (Strong / Moderate / Weak), Steel Hands and Paper Hands,
not the superseded “Mean-reverting: YES — score X/100” line.

**Why:** The user specifically required `PULL = 1 / (1 + L / 8)` and both
hand scores, with INTC labeled “NOT A GROWTH STOCK — not a winner.”

**How to apply:** Do not tune a ticker or change constants to force a ranking.
When validating, distinguish supplied expected values from computed results;
unavailable reference values and tolerances cannot be certified as matching.

Apply identical formulas to all securities and share one growth verdict across
Steel Hands and Paper Hands. The deep-dip flag is independent of that verdict.
Do not tune tickers, truncate history, or silently substitute a partial reference set.

**Why:** The excursion specification uses fixed-reference normalization. A missing
reference must not silently rescale every score.

**How to apply:** Keep thresholds and weights together. State smoothing endpoints,
weighted variance, excursion weighting, and normalization conventions explicitly
when the available specification does not resolve them. Do not present inferred
conventions as verified reference values.

Keep both illustrated rankings below the Mean Reversion graph with all thirteen
original drawings and perspective-specific significance. Their prescribed
orders are illustrations, not the live numerical ranking.

**Why:** The user explicitly requested the pictures and both rankings, then
supplied all thirteen originals. The external Docker deployment excludes raw
uploads, which previously made the pictures disappear after deployment.

**How to apply:** Bundle the originals as deployable app assets; verify images
in both rankings, not just workspace paths or ranking text. Never fabricate
replacement artwork or retune scores to reproduce the illustrated order.

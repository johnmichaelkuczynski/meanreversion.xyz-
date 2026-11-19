---
name: Winner scoring contract
description: User-defined excursion-area pull and the boundary between exact implementation and desired illustrative rankings.
---

Mean Reversion on page 1 uses the user's supplied full-history Tiingo adjusted-close
winner heuristic. Pull means distance-times-duration of smoothed residual excursions,
not crossings or completed round trips. Steel Hands rewards swings; Paper Hands
penalizes them. These are scores, not probabilities.

**Why:** The user explicitly rejected earlier cycle-count and half-life scoring and
provided replacement formulas. Their drawings are illustrations, not ticker-specific
overrides or authorization to force rankings.

**How to apply:** Preserve the supplied constants and full available histories. Never
tune constants, shorten histories, change normalization, or hardcode ticker outcomes
to obtain expected rankings. The supplied Paper Hands formula did not produce the
user's desired QQQ/SOXX-first, SOXL-last ordering on the initially evaluated histories;
report discrepancies rather than silently correcting them. The user specifically
requested reporting Disney's excursion area and pull if it qualifies as a winner.

Boundary and unfinished excursions count, so failure to return is not rewarded.
The largest-area excursion used for pull is not necessarily the longest-duration
excursion described in the duration readout.

**Why:** The brief includes the entire smoothed history, defines excursion size as
an area, and separately requests time-away information.

**How to apply:** Keep area and duration distinct, disclose these conventions in the
method details, and do not drop ongoing excursions. Preserve scores' fixed five-stock
reference set; missing reference data must not silently change the denominator.

Display both of the user's illustrative rankings below the Mean Reversion graph,
with the supplied drawings and an explanation of each drawing's significance for
that investor perspective.

**Why:** The user explicitly requested the pictures and both rankings in the app,
after previously supplying them as background only.

**How to apply:** Preserve their stated ranking orders independently of live scores.
Do not retune scores to match the illustrations or fabricate missing original images.

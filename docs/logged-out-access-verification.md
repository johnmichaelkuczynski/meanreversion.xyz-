# Logged-out browser acceptance verification

Date: November 21, 2026  
Application source tested: `6033826`

## Method

A fresh anonymous browser context opened the real `main.py` application in a
separate production-mode process. No authentication cookies, synthetic identities,
market-history fixtures, score overrides, or mocked access decisions were used.
The application used real market-derived data.

The separate process preserved the normal development server's automatic login.
Its temporary working directory also kept OAuth configuration separate from the
user's server. This was a local production-mode check, not a check of the external
Coolify deployment.

## Results

| Logged-out request | Observed result | Outcome |
| --- | --- | --- |
| SOXL on page 1 | Full analysis and channel chart; Steel hands 100.0, Paper hands 33.1, annualized slope +37.62%, position 62.9% below trend; no access panel or redaction. | Passed |
| QQQ on page 1 | Full analysis and channel chart; Steel hands 32.9, Paper hands 67.6, annualized slope +15.15%; numeric projected prices and probabilities. | Passed |
| AAPL on page 1 | Full analysis and channel chart; Steel hands 65.6, Paper hands 45.6, annualized slope +26.31%; numeric projected prices and probabilities. | Passed |
| MSFT on page 1 | Exactly one “Analyzing MSFT requires full access — $1,500” panel and one “Get full access” button; no analysis, chart iframe, or previous ticker results remained. | Passed |
| Direct `/soxl` | Exactly one “The SOXL page requires full access — $1,500” panel and one “Get full access” button; no SOXL price, diagnostics, daily signal, or chart. | Passed |

Each free ticker was explicitly entered into the first ticker input and submitted.
All three charts included actual prices and upper, mean, and lower trend lines.
No development-auto-login caption appeared in the anonymous browser context.
The SOXL readout region was observed, but its individual projected-price and
probability values were not separately extracted by the browser script.

## Scope and observations

- No app exceptions or market-data gaps were observed.
- Google login and Stripe Checkout were not exercised, and no payment was made.
  Native Google login was unavailable in the HTTP-only isolated process; the
  existing OAuth configuration requires an HTTPS callback origin.
- Two nested-path Streamlit probes returned 404 under `/soxl`; the page still
  rendered its correct access panel. No route changes were made.
- Paid-user and owner access were not part of this anonymous browser pass.
- No application code, calculations, charts, styling, OAuth settings, Stripe
  configuration, or persistent workspace/deployment environment values changed.
- The temporary test services were stopped after verification.

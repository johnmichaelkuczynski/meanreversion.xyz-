---
name: Page-one ticker access and permanent owner exemption
description: Free tickers, one clean purchase panel, no partial redaction, and permanent owner/development access.
---

Page 1 freely provides complete SOXL, QQQ and AAPL analyses, including comparisons,
to anonymous and signed-in visitors. Other user-requested tickers require paid
access before their data is loaded or their analysis rendered. Replace denied
results with one panel: “Analyzing [TICKER] requires full access — $1,500” and
one “Get full access” button. That action uses native Google sign-in if needed,
then automatically opens Checkout for the configured `STRIPE_PRICE_ID`.

**Why:** The user explicitly authorized this page-one restriction after first
requiring unrestricted access. They rejected all partial-result redaction.

**How to apply:** Show complete original results when allowed, or the single
panel when denied—never blurred charts, placeholders or scattered payment
notices. Preserve calculations, charts, layout, styling, Google OAuth settings,
Stripe objects, credentials, environment names and `/api/stripe/webhook`.
Do not infer authorization to change other pages from an unapproved draft.

Development remains automatically signed in and unrestricted. The owner must
always retain complete access in development and deployment, regardless of
present or future pricing or payment status.

**Why:** The user explicitly made permanent owner access a standing requirement.

**How to apply:** Check the case-insensitive, comma-separated `ADMIN_EMAILS`
allowlist against the verified Google identity before any payment operation.
Never hardcode an email, send the owner to checkout, or make owner access depend
on provider availability. Keep the existing durable payment verification for
non-owner buyers; an intent cookie or return-URL parameter is not payment proof.

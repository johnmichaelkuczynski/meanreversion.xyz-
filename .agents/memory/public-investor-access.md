---
name: Investor access and permanent owner exemption
description: Page-one free tickers, paid SOXL page, clean purchase panels, and permanent owner/development access.
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

Page 2 (`/soxl`) requires verified Google sign-in and paid access, with the
same owner/development exemption. Denied visitors see only “The SOXL page
requires full access — $1,500” and one “Get full access” button, before any
page content or market-data work.

**Why:** The user subsequently authorized the separate page-two restriction.
The free SOXL ticker on page one does not make page two free.

**How to apply:** Reuse the full-access entitlement and existing Google-to-Stripe
purchase continuation; never add partial-result redaction or alter page content
for allowed users.

Development remains automatically signed in and unrestricted. The owner must
always retain complete access in development and deployment, regardless of
present or future pricing or payment status.

**Why:** The user explicitly made permanent owner access a standing requirement.

**How to apply:** Check the case-insensitive, comma-separated `ADMIN_EMAILS`
allowlist against the verified Google identity before any payment operation.
Never hardcode an email, send the owner to checkout, or make owner access depend
on provider availability. Keep the existing durable payment verification for
non-owner buyers; an intent cookie or return-URL parameter is not payment proof.

Paid access belongs to the verified Google email captured by the server before
checkout, normalized for case and surrounding whitespace—not Stripe's editable
billing email. Preserve the identity binding as well.

**Why:** The user explicitly requested email-based, database-persisted access
from completed-payment webhooks. A payer may supply a different billing email.

**How to apply:** Require the configured price, live successful payment and
existing strict amount/charge checks before trusting a receipt. Legacy “paid”
rows did not necessarily complete those checks, so distinguish verified grants.
Keep refund revalidation, retain a verified grant during provider outages, and
do not cache negative access across asynchronous webhook completion. Paid
visitors should see their full results without access-status banners.

---
name: Public unrestricted app access
description: Complete app for everyone; optional Google and Stripe must not gate any feature.
---

Every visitor, signed in or not and paid or not, receives the complete app:
every page, feature, value, score, chart, projection and readout. No login walls,
payment gates, redaction, blur, placeholders, preview notices, automatic payment
verification notices or payment-status buttons may restrict or deface the app.

**Why:** The user explicitly removed ALL gating after rejecting both the
replacement preview and the redaction applied inside the original interface.
This supersedes the earlier public-partial-results and mandatory-payment rules.

**How to apply:** Preserve the original charts, readouts, calculations, layout
and styling. Do not reintroduce restricted output unless the user explicitly
changes this rule. Google login stays optional and unlocks nothing. Keep its
code/routes, Stripe integration, `/api/stripe/webhook`, and environment names
intact. Optional purchase confirmation must not gate any page or feature.

The comma-separated, case-insensitive `ADMIN_EMAILS` allowlist still identifies
the owner's exemption inside the preserved optional Stripe code. Never hardcode
an email in application code. All visitors already have full application access
regardless of that setting.

**Why:** The user explicitly kept Google and Stripe while removing all access
restrictions; the owner's existing financial exemption must not be removed.

**How to apply:** Do not modify Stripe products, prices, credentials, webhook
behavior or verified Google identity handling to implement public app access.

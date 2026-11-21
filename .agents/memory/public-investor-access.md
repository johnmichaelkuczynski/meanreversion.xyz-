---
name: Public redacted app access
description: No entry wall; visitors try partial results, paid users and admins see the full app.
---

Visitors must be able to open and try both actual app pages without Google
login or payment. Show real partial results, but redact full graphs, detailed
results and selected scores until the user signs in and pays.

**Why:** The user explicitly removed the entry/login wall and rejected
replacing the app with a welcome/readme page.

**How to apply:** Preserve the complete paid app, Google login, Stripe, and
existing verified purchases. Offer an inline unlock prompt within the working
app. Withhold paid values on the server; do not send full results to the browser
and merely blur them. Keep automatic development access unrestricted and
separate; it must never initiate live checkout.

Verified Google users on the comma-separated, case-insensitive `ADMIN_EMAILS`
environment allowlist are paid administrators everywhere. Do not hardcode any
administrator email in application code.

**Why:** The user requires administrators to bypass payment, never see a
paywall, and never enter Stripe checkout.

**How to apply:** Check the allowlist before billing, checkout creation,
checkout-return verification, feature gates, or quotas. Bind cached payment
results to the authenticated account, and do not let cached admin grants
survive removal from the allowlist. If administrator configuration is absent,
fail closed without offering checkout.

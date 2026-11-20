---
name: Production access policy
description: Google-and-payment entry wall, environment-configured admins, and development access.
---

Every production app page requires a verified Google login and verified paid
access. The public welcome page explains the product to ordinary investors;
it must not expose the actual analysis app before access is granted.

**Why:** The user explicitly replaced the earlier public-investor presentation
policy with a mandatory Google login and payment wall.

**How to apply:** Gate both app pages and all feature checks, not just selected
tabs. Preserve existing verified purchases and subscriptions. Keep automatic
development access separate; it must never initiate live checkout.

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

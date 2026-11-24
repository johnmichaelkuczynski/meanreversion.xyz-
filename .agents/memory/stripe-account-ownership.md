---
name: Stripe account ownership
description: Use the owner's Stripe keys directly without changing account settings, products, or prices.
---

Use only the owner's Stripe credentials stored in project Secrets. Do not
attach a Replit-managed Stripe connection, provision another account, or
substitute sandbox credentials.

**Why:** The user explicitly rejected the managed connection and required
their own Stripe keys. Provider readiness must be checked with real requests,
not inferred from the presence of environment variables.

**How to apply:** Keep credentials server-side and use existing account
configuration. Do not create or modify Stripe products, prices, webhooks, portal settings,
or account settings without specific permission. Approval to correct the
software product's tax category was a narrow exception, not general permission
to change the account or catalog. If required configuration is missing, report the exact
blocker instead of proposing to create it. App-initiated checkout/payment
operations must use the owner's credentials, never a managed connection.

Use only the exact Stripe price supplied by the user for this app. Do not
substitute other catalog prices or offer alternatives unless asked.

**Why:** The user explicitly rejected alternative prices and requires the
price ID they provided.

**How to apply:** Validate that configured price without changing Stripe
products or prices. A lookup failure is a configuration blocker, not permission
to select another offer.

Keep workspace and external Coolify payment verification separate.

**Why:** The user configures Coolify's runtime environment separately. A
workspace authentication or price-lookup failure does not establish what the
published server is using.

**How to apply:** Name the environment in every readiness report. Check that
the access-wall code reached GitHub and the published app before attributing
production behavior to credentials or requesting another replacement key.

Put sign-in/sign-out and Buy at the top of the page in normal document flow,
not in a fixed, floating, or sticky bar.

**Why:** The user explicitly said these controls are used rarely and should
not clutter the screen while scrolling.

**How to apply:** Keep them above the market snapshot and let them scroll away
normally. Do not interpret "at the top" as "always visible."

Respect the owner's existing Stripe Managed Payments configuration.

**Why:** Real Checkout requests revealed that Managed Payments is enabled by
default. It rejects explicit payment_method_types and requires an eligible tax
category on the existing product; a valid API key and price alone do not prove
checkout readiness.

**How to apply:** Verify actual session creation without submitting payment.
Do not disable Managed Payments, even per-session, or edit product tax settings
without permission. Preserve Stripe's tax calculation when validating totals;
base price and final charge can differ because of tax.

Preserve verified one-time purchasers when adding subscription support.
Subscription cancellation removes the subscription entitlement, not an
independent permanent purchase or owner access.

**Why:** The user is changing payment arrangements; adding webhooks is not
permission to take away purchases made under the previous offer.

**How to apply:** Keep entitlement sources independent, and require a verified
app checkout to link a subscription to an authenticated account. Never link
accounts by email alone.

Convert Stripe SDK resources explicitly to plain dictionaries before storing
or manipulating nested payloads.

**Why:** The installed SDK rejects `dict(event)` with TypeError despite older
Stripe examples treating resources as mappings.

**How to apply:** Use the SDK's `to_dict()` at provider boundaries; test signature
verification with actual SDK event objects rather than only mocked dictionaries.

Ignore signed events for other apps, unknown local billing objects, and unused
event types instead of queuing them or creating foreign customer/subscription rows.

**Why:** The Stripe account is shared, and unrelated deliveries were producing
retry errors in this app. The user explicitly required HTTP 200 for these events.

**How to apply:** Establish ownership from saved checkout attempts or verified
local account/subscription links. A first legitimate checkout can introduce a new
Stripe customer, so its already reserved, server-bound purchase is ownership
evidence. A failed database lookup is not proof of an unknown object: retain
retry behavior rather than silently losing a real payment during an outage.
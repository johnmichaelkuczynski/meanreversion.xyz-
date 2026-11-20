---
name: Deployment environment detection
description: Reliable distinction between Replit workspace previews and published deployments.
---

Use `REPLIT_DEPLOYMENT=1` as the authoritative signal that code is running in a published Replit deployment. Do not infer production from `REPLIT_CONTAINER`.

**Why:** A published VM can report `REPLIT_CONTAINER=repl`, which caused a development authentication bypass to activate on the public site.

**How to apply:** Any security boundary or production-only behavior must check
`REPLIT_DEPLOYMENT`. Workspace automatic sign-in also requires the server-managed
`REPLIT_DEV_DOMAIN`; an explicit production environment always disables it.

Google login requires verification of the actual Google authorization handoff,
not just the development bypass or mocked native-login calls.

**Why:** Google rejected the published app's callback even while development
access and local authentication tests passed.

**How to apply:** Google must authorize the app's exact HTTPS origin plus
`/oauth2callback` on the same client whose credentials the server uses.
Credentials alone cannot modify Google's allowed callbacks. Never substitute
another domain's callback to evade rejection: OAuth state and cookies belong
to the initiating origin. Report provider rejection as blocked, not complete.
Google authorization is separate from Schwab's market-data authorization.

Always sign in with a clearly identified development-only identity in workspace
preview sessions; never require Google login there or offer a development
Sign out action that can lock the user out.

**Why:** The user explicitly requires uninterrupted access while developing
and authorized preview-only automatic sign-in. This is not a Google identity.
The user's latest instruction requires being “ALWAYS LOGGED IN” in development,
superseding the earlier request for a usable development logout control.

**How to apply:** Keep the bypass server-controlled and disabled on published
deployments even if workspace markers remain. Do not infer a production login
requirement from this preview-only request. Reloads, fresh tabs, and stale development logout state
must not require reauthentication. This local identity must never be presented
as verified Google identity or silently receive production owner privileges.
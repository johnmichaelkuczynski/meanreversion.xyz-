---
name: Deployment environment detection
description: Reliable distinction between Replit workspace previews and published deployments.
---

Use `REPLIT_DEPLOYMENT=1` as the authoritative signal that code is running in a published Replit deployment. Do not infer production from `REPLIT_CONTAINER`.

**Why:** A published VM can report `REPLIT_CONTAINER=repl`, which caused a development authentication bypass to activate on the public site.

**How to apply:** Any security boundary or production-only behavior must check
`REPLIT_DEPLOYMENT`. Workspace automatic sign-in also requires the server-managed
`REPLIT_DEV_DOMAIN`; an explicit production environment always disables it.

Do not repair or reinstall Google login unless the user explicitly requests it
again.

**Why:** The user explicitly said to remove Google login, not fix it.

**How to apply:** Keep the app public and preserve development access. This
instruction does not request removal of Schwab's separate market-data
authorization.

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
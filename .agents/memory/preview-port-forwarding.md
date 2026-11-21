---
name: Preview port forwarding
description: Distinguish the public preview URL from the app's internal listening port.
---

Verify the exact address selected in Preview, including any explicit port,
as well as the normal HTTPS development hostname. Whether `:5000` is reachable
depends on the current external port mapping; it is not universally invalid.

**Why:** During a reported preview outage, the normal HTTPS hostname returned
200 while the user's selected `:5000` address returned 502. Correcting the
external mapping made both respond. Merely checking a different working address
and telling the user to change theirs repeatedly did not resolve their preview.

**How to apply:** Check both the actual failing URL and the canonical forwarded
URL before declaring the preview restored. A server's HTTP 200 alone is not
evidence that the page actually renders; inspect the visible page as well.

Public HTTP success is not sufficient for Streamlit: validate the live
WebSocket connection and receipt of rendered page messages through the same
public authority, including its port.

**Why:** The external proxy can remove the port from Host while the browser's
Origin retains it. This produced repeated WebSocket 403s with healthy HTTP 200s
and prevented the app from rendering.

**How to apply:** Preserve validated public authority through both proxy layers.
Keep unrelated origins rejected and preserve cookies/XSRF protections; do not
solve the mismatch by disabling origin checks globally.

Do not show a chart recovery/reopen overlay or ask the user to reopen a chart.
A disconnect must not cover content that has already loaded.

**Why:** The user explicitly rejected the recovery card and its manual reopen
action after it obscured a successfully rendered Mean Reversion page.

**How to apply:** Leave connection recovery to Streamlit without a custom
blocking prompt, forced reload, or navigation that could discard chart state.
Remove legacy recovery cards in already-open pages as well as new sessions.

Browser console snapshots can include disconnected, abandoned testing tabs.
Attribute failures to a full request authority and active page before concluding
the user's app is down.

**Why:** Stopped local fixtures generated continuous connection errors while
the exact external preview accepted ticker input and updated charts normally.

**How to apply:** Separate fixture-origin errors from the real preview. A fresh
successful session still does not prove the user's existing tab recovered.

Use HTTP request/status evidence for intermediate redirect hops, not just
committed browser-frame URLs or the final cookie jar.

**Why:** Successful purchase-start and checkout-departure HTTP 302 responses did
not appear as committed frames; departure intentionally cleared the intent
cookie before the final navigation.

**How to apply:** Verify the redirect chain at the HTTP layer before diagnosing
missing intent or skipped authentication from final browser state alone.

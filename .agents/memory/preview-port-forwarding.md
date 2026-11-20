---
name: Preview port forwarding
description: Distinguish the public preview URL from the app's internal listening port.
---

Use the normal HTTPS development hostname without an explicit `:5000` suffix
when linking to the running app. The app listens internally on 5000, which is
forwarded to the default external web port.

**Why:** During a reported preview outage, the normal HTTPS hostname returned
200 and rendered the SOXL chart, while the same hostname with `:5000` returned
502. A healthy internal server does not make every external port reachable.

**How to apply:** Check both the actual failing URL and the canonical forwarded
URL before restarting or editing a healthy application.

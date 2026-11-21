---
name: PostgreSQL transaction-pool session state
description: Isolated database tests must apply search paths within every transaction.
---

Never rely on a session-level search path surviving a commit when using the
project's PostgreSQL connection pool. Use transaction-local settings inside
every transaction that needs a nondefault schema.

**Why:** An isolated fulfillment test created its tables successfully but later
connections intermittently reported missing tables. Applying the schema inside
each transaction made the real database test reliable.

**How to apply:** Keep synthetic billing events and receipts in a random private
schema, set its search path transaction-locally before queries, and remove only
that schema afterward. Do not test synthetic grants in the live application
tables or let the real payment worker consume fixture events.

# Runtime environment variables

Set values in Coolify's application environment. Do not commit secret values.
The server starts without optional integrations configured; only the related
feature is unavailable until its variables are supplied.

## Server

| Variable | Required | Purpose |
| --- | --- | --- |
| `PORT` | No | Public HTTP port; defaults to `5000`. The gateway listens on `0.0.0.0`. |
| `APP_ENV` | No | Set to `production` for indexable SEO responses. Automatic development access requires the server-managed workspace marker and is disabled in production. Docker sets `production`. |
| `PUBLIC_APP_URL` | Recommended for Google login | Public HTTPS origin without a path, query or fragment. When unset, Google login uses the current site's origin. |
| `SOXL_DISABLE_WORKER` | No | Set to `1` to disable the market-refresh workers. |

## Database and visitor counter

| Variable | Required | Purpose |
| --- | --- | --- |
| `NEON_DATABASE_URL` | Recommended | This app's PostgreSQL connection string. It takes priority for all app data, including market state, visitor counts, diagnostics, and Schwab OAuth tokens. Set it to this app's dedicated Neon database to keep data isolated from other apps. |
| `DATABASE_URL` | Optional fallback | PostgreSQL connection URL used only when `NEON_DATABASE_URL` is not set. All web replicas and workers for this app must resolve to the same database. |
| `SESSION_SECRET` | Required for Google login | Persistent secret signing Google-auth cookies and anonymous visitor identifiers. |

## Market data

| Variable | Required | Purpose |
| --- | --- | --- |
| `EODHD_API_KEY` | Optional | EODHD historical market data. |
| `POLYGON_API_KEY` | Optional | Polygon options-chain and options-history data. |
| `SCHWAB_CLIENT_ID` | Required for SOXL quotes | Your Schwab developer app's client ID. SOXL current quotes use Schwab exclusively after owner authorization. Also enables Schwab benchmark quotes and SOXL options chains. |
| `SCHWAB_CLIENT_SECRET` | With Schwab | Server-side Schwab client secret for token exchange and refresh, and OAuth-state cookie signing. Never entered in a browser form or exposed in page content or logs. |
| `SCHWAB_REDIRECT_URI` | With Schwab | Must exactly match the developer portal callback; defaults to `https://soxl.ai/auth/schwab/callback`. Start authorization at `/auth/schwab/connect` on that same domain. |

Schwab setup uses your own keys, not a Replit connector. Deploy this code and set
the keys on the server serving `soxl.ai`, then open
`https://soxl.ai/auth/schwab/connect`. This immediately redirects to Schwab's
OAuth login and consent page; there is no local form or secret-entry step.
The callback verifies OAuth state, exchanges the code, privately stores tokens,
and redirects to `/`, where the price display requests the Schwab SOXL quote.
Other hosts redirect to the configured callback host before starting OAuth so
the secure state cookie returns to the same host.
Credentials are read at request time with surrounding whitespace trimmed.
After changing Coolify environment settings, recreate/redeploy the container so
it receives the new environment.

Behind Coolify's HTTPS proxy, keep the public host `soxl.ai` intact. OAuth uses a
host-only, Secure, HttpOnly, SameSite=Lax state cookie scoped to
`/auth/schwab`; the cookie remains Secure even when internal proxy traffic is
HTTP. All replicas must use the same Schwab secret. Invalid callbacks log the
fixed reason `oauth_state_invalid` and cookie/protocol booleans, never secrets,
authorization codes, state values, or cookies.
Anyone who can reach the connect route can initiate Schwab consent; a completed
authorization replaces this server's shared market-data connection. There is no
local owner-password check and no public app login wall.
The public app has no login requirement. `/api/schwab/status` reports only
sanitized connection state, never tokens or account data. Access tokens refresh
automatically; Schwab ordinarily requires renewed owner authorization after
approximately seven days. SOXL current quotes have no fallback provider or
historical-close substitute: failures are displayed as errors. The quote request
uses `symbols=SOXL&fields=quote,extended`; outside weekday 9:30 a.m.–4 p.m.
New York time it requires `extended.lastPrice` and `extended.tradeTime`,
otherwise `quote.lastPrice` and `quote.tradeTime`. Historical analysis data is
unchanged. Existing benchmark sources and Polygon options remain fallbacks;
the integration never calls trading or account endpoints. Preserve the token
database across redeployments. Access tokens, refresh tokens, and both expiry
times live only in PostgreSQL, never an application file or process cache.
The database user needs permission to create/use `public.schwab_oauth_tokens`;
the table is initialized lazily on the first storage access. A transaction-scoped
PostgreSQL advisory lock serializes refreshes across workers/replicas, including
through a transaction-pooling proxy. Access tokens refresh before a market API
call when they have five minutes or less remaining. Rotating the refresh token
does not extend the original seven-day consent deadline. Temporary provider or
database failures display availability errors and preserve authorization;
only absent, expired or provider-rejected refresh credentials request consent.
Old token files are no longer read. After the first deployment of database
storage, authorize once at `/auth/schwab/connect` if the database has no token
record yet. Later restarts reuse the same database record. To share authorization
with a development preview, it too must resolve to that same selected database
URL and Schwab client ID; a different database deliberately remains a separate
connection.

## AI and text-quality providers

| Variable | Required | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Optional | Anthropic strategy generation and diagnostic checks. |
| `ANTHROPIC_BASE_URL` | No | Optional Anthropic-compatible API base URL. |
| `OPENAI_API_KEY` | Optional | OpenAI-powered app and diagnostic features. |
| `OPENAI_BASE_URL` | No | Optional OpenAI-compatible API base URL. |
| `R1_ANTHROPIC_MODEL` | No | Anthropic model selected by the system diagnostic; defaults to `claude-sonnet-4-5`. |
| `GPTZERO_API_KEY` | Optional | GPTZero text-quality diagnostic. |

## Direct Google login

Google login uses your own credentials, not Clerk. Set these in the environment
of the server actually serving the published app (Coolify credentials are
separate from workspace secrets). Register the exact HTTPS origin plus
`/oauth2callback` under **Authorized redirect URIs** on that same Google OAuth
client. JavaScript origins alone do not authorize the callback. Credential
changes require the server to receive its updated environment.

The workspace remains automatically signed in with a development identity.
That is not evidence of a successful Google-account login.

| Variable | Required | Purpose |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID` | Yes | Your Google OAuth web client ID. |
| `GOOGLE_CLIENT_SECRET` | Yes | The secret for that same client. |

## Application access and administrator exemption

On page 1, SOXL, QQQ and AAPL are fully available without sign-in or payment,
including comparisons. Other tickers require verified paid access and otherwise
show one clean $1,500 purchase panel instead of running or displaying analysis.
Its button continues through native Google sign-in to Stripe Checkout for the
existing `STRIPE_PRICE_ID`. Allowed results are never redacted or blurred.
Page 2 retains its existing access behavior. Google OAuth settings, Stripe
objects, routes and environment variable names remain unchanged.

Set `ADMIN_EMAILS` to the comma-separated administrator email allowlist in the
actual server's environment. Matching ignores case and surrounding whitespace.
Only authenticated, verified Google identities qualify for the owner exemption
inside optional billing operations; no administrator address is built into
application code. Matching owners have full access before any payment check.

Set this variable in Coolify as well as the workspace when deploying there:
workspace environment settings do not configure an external server. A missing
administrator allowlist does not affect the three free tickers; configure it
correctly to preserve the owner's exemption for all other tickers and payments.

Development previews remain automatically signed in and do not charge users.
Optional purchase records remain tied to the authenticated account, not URL parameters.
The configured `STRIPE_PRICE_ID` must be an existing price accessible with the
configured Stripe account key. This change does not create or alter Stripe
products, prices or webhooks.

## Legacy Stripe configuration


| Variable | Required | Purpose |
| --- | --- | --- |
| `STRIPE_SECRET_KEY` | Optional | Stripe API access for checkout and event processing. |
| `STRIPE_WEBHOOK_SECRET` | Optional | Verifies signed requests to `POST /api/stripe/webhook`. |
| `STRIPE_PRICE_ID` | Optional | Stripe price used by the legacy checkout flow. |

## Tests only

| Variable | Purpose |
| --- | --- |
| `SOXL_TEST_BASE_URL` | Base URL for live browser tests; defaults to `http://127.0.0.1:5000/`. |
| `CHROMIUM_PATH` | Optional path to a locally installed Chromium executable for live browser tests. |
| `WEBHOOK_DB_TEST` | Explicit opt-in for the webhook database integration test. |
| `PROBE_PORT` | Optional isolated port used by the cold-start probe. |
| `SESSION_TEST_PORT` | Optional port used by the chart-session browser test. |
| `PRICE_SCENARIO_TEST_PORT` | Optional port used by the price-scenario browser test. |
| `WAIT_FOR_COMPONENT_UPGRADE` | Set to `1` when the chart benchmark test should wait for a component upgrade. |

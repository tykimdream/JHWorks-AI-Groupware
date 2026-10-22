# pikan.dev domain release preparation

Target: groupware.pikan.dev, with Vercel DNS and Firebase Hosting forwarding to the existing Seoul Cloud Run service. Supabase remains the database.

## First implementation and acceptance criteria

Private authenticated API responses must not be stored by a browser or shared CDN, including denied, validation and unhandled error responses. Verify real login/session/logout with Firebase's __session cookie, HTTPS and the exact custom Origin; reject the portfolio origin and stale legacy cookies.

The existing private Cloud Run release must remain fail-closed. DNS, public IAM, billing and live cookie settings are not changed by this unit.

## Alternatives and constraints

- Cloud Run direct domain mapping does not support asia-northeast3 and remains Preview.
- A Google external load balancer introduces fixed hourly charges; compare before adopting it.
- Firebase Hosting supports Seoul rewrites but strips cookies other than __session and imposes a 60-second timeout. Hosting is an entrypoint only, not a database migration.
- Current no-cost Hosting allowance is 10 GB storage and 10 GB/month transfer. Blaze requires billing; overages and Cloud Run/Registry/Secret usage remain billable. The existing 5,000/10,000 KRW notifications are not hard caps.
- Conservative no-store for dynamic authenticated responses avoids cross-user leakage. Public static asset caching can be considered separately after authentication and the actual proxy path are verified.

Sources:
https://vercel.com/docs/domains/managing-dns-records
https://docs.cloud.google.com/run/docs/mapping-custom-domains
https://firebase.google.com/docs/hosting/cloud-run
https://firebase.google.com/docs/hosting/manage-cache#using_cookies
https://firebase.google.com/docs/hosting/usage-quotas-pricing

## Ordered release gates

1. Cache and cookie regression tests, existing API checks and PR CI.
2. Prepare a pinned Hosting configuration and local validation; no live deploy.
3. Obtain approval for Firebase project/Hosting creation and any new billing/IAM scope before applying it.
4. Prepare public demo isolation and server-side request limits; keep AI disabled.
5. Obtain action-time approval for public access/DNS changes with the exact target and reviewed behavior.
6. Verify HTTPS, login/logout, private response headers, CSRF, anonymous access boundaries, quotas and billing on the real domain.

Live Firebase, CDN cookie forwarding, DNS records and certificate provisioning are not yet verified. Shared private fixture credentials are never published. The initial private staging workflow must not be rerun against its populated data.

## Cache/cookie implementation evidence

Seven HTTP regression cases initially failed before the cache boundary change. The API middleware now emits Cache-Control: private, no-store, and the outer unhandled-error handler does the same because its response bypasses the middleware return path.

The default private staging cookie is unchanged. A fresh Python process starts with JHWORKS_SESSION_COOKIE_NAME=__session, uses only a synthetic local SQLite fixture, verifies HTTPS/HttpOnly/SameSite, exact custom Origin, rejected portfolio Origin without session loss, rejected legacy cookie, logout and 401. This is not a live Firebase/CDN test.

The full API suite passed after implementation. Ruff and strict mypy results are checked before the PR is submitted. PostgreSQL integration cases remain CI-owned; no external database was used by these tests.

Local result: 257 passed / 7 skipped in 35.21 seconds; Ruff passed; strict mypy 119 source files passed. The seven skipped PostgreSQL tests are verified in PR CI rather than claimed as locally executed.

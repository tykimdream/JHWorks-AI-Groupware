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

## Static HTTPS milestone (prepared, not deployed)

The first public milestone is a static holding page on groupware.pikan.dev.
This separates DNS/certificate verification from exposing the application and database.
It is not the completed interactive demo. No rewrite can reach Cloud Run in this configuration.

Reviewed inputs:
- deploy/firebase/firebase.json: one existing-project site, public/index.html and styles.css only.
- .firebaserc binds jhworks-staging-tykimdream explicitly.
- No Firebase SDK, JavaScript, analytics, remote fonts, authentication or database integration.
- CSP prohibits scripts, frames and forms; all responses use private, no-store.
- python -m app.ops.firebase_hosting --config ../../deploy/firebase/firebase.json
  runs from apps/api, performs an offline plan only and rejects other targets,
  dynamic routes, extra files (including hidden secrets), symlinks and uploads above 32 KiB.
- This validator checks deployment inputs, not HTML safety or a cloud spend cap.
  The exact files must still be reviewed at the deployment commit.
- New validator tests and cache/cookie tests: 16 passed in 5.15 seconds.
  Ruff passed; strict mypy app/tests passed (121 source files).
- Desktop preview was inspected in the actual browser. Mobile and deployed HTTPS/header
  checks remain pending; no WCAG compliance claim is made.

### Next approval boundary and operational procedure

Firebase Console confirms that the existing GCP project is eligible for adding Firebase.
It warns that this addition cannot be undone, billing and project IAM are shared,
and deleting the Firebase project would delete the existing GCP project too.
Never delete the project as a Hosting rollback.

Before applying: obtain approval to enable Firebase on this specific project,
create one Hosting site and its managed service identities, use the existing billing
account (Blaze), and publish only this reviewed static holding page.
Disable optional Analytics/Gemini products; do not create Firestore/Auth/Storage,
new databases, load balancers or new billing accounts.
Existing Cloud Run IAM, Secrets and database access stay unchanged.

The approximately 2.9 KiB page is expected to fit the Hosting no-cost allowance
at low traffic, but usage beyond allowances is billable. Existing 5,000/10,000 KRW
alerts are notifications rather than spending caps. Verify live quotas and plan first.
A static Holding release must use --only hosting with the explicit project and
reviewed config; do not use a generic multi-product firebase deploy.

After creating Hosting, inspect the exact domain verification instructions.
Change only records for groupware.pikan.dev in Vercel DNS, preserve root/portfolio
and nameserver records, and confirm certificate issuance before calling this milestone
complete. Record old DNS values and Hosting release ID for rollback.
Rollback uses the previous Hosting release or the recorded subdomain DNS values,
never deletion of the Firebase/GCP project.

### Remaining application gates

Public demo isolation, anonymous/login throttling and resource limits must be tested
before any Cloud Run public IAM or live __session/origin change.
The existing private release workflow intentionally rejects public IAM and must not
be weakened. Choose a separate reviewed public-demo release path.
Then verify real CDN cookie forwarding, CSRF, login/logout, no-store,
unauthorized access, max instances and billing on the final domain.

Full local API result for this unit: 266 passed / 7 skipped in 36.68 seconds; PostgreSQL integration cases are delegated to CI. JUnit: artifacts/cloud-run/firebase-preflight-tests.xml (ignored local evidence).

# ONER

Backend for ONER, an online filmmaking course platform for Russian speaking Central Asia (Kyrgyzstan, Kazakhstan, Uzbekistan).
I built the backend with FastAPI, PostgreSQL, SQLModel and Alembic. The Next.js frontend is in `web/`.

<p align="center">
  <img src="https://bekzat.dev/static/oner-architecture.svg" width="100%" alt="Animated ONER architecture: checkout, signed FreedomPay webhook, entitlement granted once, DRM video for owners only">
</p>

> This public repo starts from a snapshot of the code. The day by day development history is in a private repo.

The whole product is one rule: **you watch a lesson only if you own it.**
Access is decided on the server from an `entitlements` table. Never by the client, never on a payment redirect, only after a verified payment webhook.

I built the backend first, test first, and locked down the buy, own, watch flow before any frontend existed.

## Admin panel

Everything a student sees is made in the admin panel. It is the only way to write content, and every admin route checks the role on the server.

- **Courses**: create a course with "What you'll learn" and "Requirements", then modules and lessons inside it. Drafts stay hidden until they are published. A course that someone already bought can not be deleted.
- **Video**: upload a lesson video straight from the browser to Kinescope. The old video stays live until Kinescope finishes processing the new one, then it is swapped in. Videos that no lesson uses are deleted.
- **Materials**: files upload straight from the browser to Cloudflare R2 with a signed upload URL, so big files never go through the API. A storage sweep removes uploads that nothing points to.
- **Accounts**: find a user by email, and see every course they own and every payment they tried. Change their role, set a new password, or disable the account.
- **Purchases**: full payment history, with filters by email, course and status. Pending rows are abandoned checkouts.
- **Refunds**: the money goes back in FreedomPay's merchant cabinet. Then the admin records the refund here and decides if the course is taken away too.
- **Manual access**: give someone a course, or take it away. Giving the same course twice is safe, it returns the same entitlement.

### R2 bucket CORS

Admin uploads PUT straight from the browser to R2, so the bucket needs its own CORS rule allowing `PUT` from the admin page's origin. `CORS_ORIGINS` doesn't cover it; that request never touches the API.

### Sweeping R2

Files no material points at (an upload the admin never recorded, or a delete whose R2 call failed) cost storage until they're removed. Run the sweep on a schedule, e.g. a daily Railway cron:
```
## Test

```bash
uv run pytest                       # full suite
uv run pytest --cov=app             # with coverage
```

Tests mock all external services (FreedomPay, Kinescope, R2), CI never hits a real API. GitHub Actions runs the suite on every push.

## How it works

- **Auth**: roll-your-own JWT (OAuth2 password flow, argon2 hashing).
- **Catalog**: public browses published courses; drafts stay admin-only. Unpublishing hides a course from the catalog and checkout, but its owners keep access.
- **Entitlements**: the access core. `has_access(user, course)` gates every lesson, video token, and material download.
- **Payments**: `POST /checkout` builds a FreedomPay hosted-page link; a signature-verified, idempotent webhook is the *only* thing that grants access. A second payment for something already paid is rejected when FreedomPay allows it, and logged for a manual refund when it doesn't. `GET /me/purchases/{id}` tells the checkout return page how the payment ended.
- **Video**: owners get a short-lived Kinescope DRM token; non-owners get 403. Admins upload straight from the browser to Kinescope; a new video replaces the old one only once Kinescope has finished processing it, and videos no lesson uses are deleted.
- **Materials**: time-limited R2 signed URLs, gated by ownership. Titles are listed on the course page; the files are not.
- **Admin**: the only write path for content: courses with "What you'll learn" and "Requirements", modules and lessons with descriptions, and material uploads that PUT straight to R2. A purchased course can't be deleted. Admins also find accounts by email, see what an account bought, and change its role, set its password, or disable it. A refund is made in FreedomPay's merchant cabinet and recorded with `POST /admin/purchases/{id}/refund`, where the admin decides whether the course goes too; `DELETE /admin/entitlements` takes a course away on its own.
- **Storage**: deleting content deletes its R2 files; a sweep removes uploads no material points at.
- **Ops**: JSON logs on stdout, one line per request, every line tagged with its `X-Request-ID`. CORS allows only `CORS_ORIGINS`.

## Stack

FastAPI · SQLModel · Alembic · Postgres · pydantic-settings · pytest + httpx · Docker Compose · GitHub Actions

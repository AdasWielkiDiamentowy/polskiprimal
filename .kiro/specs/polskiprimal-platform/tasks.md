# Implementation Plan — polskiprimal.pl (Phase 1, Option A)

Ship-early ordering: tasks 1–5 get a public, deployable content site live (R1, R2, R3,
R10). Tasks 6–10 add accounts, supplier publishing, calendar, and reservations without
taking the site offline. Each task builds on the previous and ends in working, integrated
code.

- [x] 1. Scaffold the FastAPI project and one-command run
  - Create project structure: `app/` (main, config, routers, services, models, storage,
    templates, static), `tests/`, `pyproject.toml`/`requirements.txt`.
  - Add FastAPI app factory, settings via pydantic-settings reading env/`.env`, and a
    `/health` endpoint returning 200.
  - Add base Jinja2 layout + Tailwind setup + HTMX/Alpine includes and a homepage that
    renders static placeholder content.
  - Add `.env.example` and make the app start even when payment/DB vars are absent.
  - _Requirements: 1.1, 1.5, 10.4, 10.6_

- [x] 2. Define the StorageBackend interface and in-memory fake
  - Implement the abstract `StorageBackend` (get_json, put_json, list, delete, try_reserve)
    and the `NotFound` exception and `ReserveResult` type.
  - Implement an in-memory fake backend for tests/dev.
  - Write the shared contract test suite that any backend must pass; run it against the fake.
  - _Requirements: 2.2, 2.3, 2.5_

- [x] 3. Implement S3StorageBackend and backend selection
  - Implement `S3StorageBackend` (boto3) for get/put/list/delete, mapping missing keys to
    `NotFound`; implement Phase 1 `try_reserve` that records a `requested` reservation
    without decrementing quantity.
  - Wire `STORAGE_BACKEND` config to select the implementation; read S3 bucket/region/creds
    from env; support `S3_ENDPOINT_URL` for local MinIO.
  - Run the shared contract suite against `S3StorageBackend` via MinIO.
  - _Requirements: 2.1, 2.2, 2.4, 2.5, 2.6, 8.2_

- [x] 4. Define Pydantic models and content service
  - Add models: User, Category, BlogPost, AvailabilitySlot, Reservation, ThemeConfig.
  - Implement `content_service`: assemble the multi-level category tree from `_index`,
    list topics, load a post, render Markdown body, and exclude drafts from public views.
  - Unit-test tree assembly and draft filtering against the in-memory fake.
  - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6_

- [x] 5. Public content pages, theming, 404 and "coming soon" (first launch milestone)
  - Build public routes/templates: homepage with recent posts, category view, blog list,
    blog detail — all reading via the StorageBackend.
  - Implement `theme_service` loading `config/theme.json` and inject CSS variables into the
    layout; map Tailwind tokens to the variables; ensure responsive layout.
  - Add a reusable "Wkrótce / Coming soon" partial for unfinished areas and a global 404
    page for missing content.
  - Seed a few sample JSON content objects so the site renders real pages.
  - _Requirements: 1.2, 1.3, 3.2, 3.3, 3.4, 3.7, 9.1, 9.2, 9.3, 9.4_

- [x] 6. Deployment: Docker, Caddy, HTTPS, deploy guide (go live)
  - Write the Dockerfile (build Tailwind, run uvicorn) and `docker-compose.yml` with `app`,
    `caddy`, and optional `minio` services; verify `docker compose up` serves the site.
  - Write the Caddyfile for reverse proxy with automatic Let's Encrypt HTTPS in prod and
    plain HTTP locally.
  - Write `DEPLOY.md`: DNS A/CNAME setup, required env vars, one-command launch, and
    GitHub clone-and-run notes for co-workers.
  - _Requirements: 1.1, 1.4, 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 7. Authentication engine
  - Implement `auth_service`: register (passlib/bcrypt hashing), login (verify + issue JWT),
    logout; maintain `users/_index_by_email.json`.
  - Set JWT in an HttpOnly cookie; mark Secure + SameSite when `APP_ENV=prod`; generic error
    on invalid login.
  - Add login/register/logout routes and templates.
  - Unit-test password hashing and JWT issue/verify.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [ ] 8. Role-based access control
  - Add `current_user` dependency (decode cookie) and a `require_role(role)` dependency
    factory enforcing roles server-side.
  - Protect supplier and admin route groups; redirect/401/403 for unauthorized access.
  - Integration-test consumer-denied-supplier and non-admin-denied-admin cases.
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 9. Supplier dashboard and availability publishing
  - Implement `calendar_service` supplier CRUD: create/edit/delete AvailabilitySlot with
    location, date, time window, product, quantity+unit, optional price/notes; persist as
    JSON and update the month index.
  - Build the supplier dashboard showing only that supplier's own slots.
  - Add an admin-controlled "Verified Farmer" flag reflected on slots.
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 10. Public calendar and reservation requests
  - Implement the public calendar view grouped by date/location with filters (product,
    location, date) using the month index; show product, quantity, market, time window,
    supplier, and Verified Farmer status.
  - Implement `reservation_service`: consumer submits a request via `try_reserve` (status
    `requested`, no auto-decrement); supplier confirms/declines; reject missing/expired slots.
  - Use HTMX for filter updates and reservation submission; integration-test the request→
    confirm flow and the unchanged `try_reserve` call site (Option B/C readiness).
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

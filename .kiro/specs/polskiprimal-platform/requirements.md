# Requirements Document

# Requirements — polskiprimal.pl Platform (Phase 1, Option A)

## Introduction

polskiprimal.pl is a Polish healthy-food / farm-to-table web platform. It publishes
editorial content (ingredient catalogues, quality analyses, healthy shopping lists,
primal/keto guides, herbs & recipes, sugar-addiction help) and connects local farmers
(suppliers) with consumers through a produce-availability calendar and reservation
requests.

This spec covers **Phase 1 (Option A)**: a FastAPI application rendering Jinja2 + HTMX +
Alpine.js + Tailwind, with **Amazon S3 as the only storage backend (no database)**. All
data is stored as JSON objects in S3, accessed exclusively through an abstract
`StorageBackend` interface so that a DynamoDB backend (Option B) or a
PostgreSQL + SQLAlchemy + Alembic backend (Option C) can be added later **without
rewriting feature code**.

The overriding priority is **fast launch**: the site must be publicly reachable over
HTTPS early so the team can start uploading real content while features are still being
built.

### Scope of Phase 1
- Public content site: homepage, multi-level categories, blog, static-ish pages.
- Content authored as JSON/Markdown in S3, editable by the team (also tracked in GitHub).
- User accounts with roles (consumer, supplier, admin), secure auth.
- Supplier dashboard to publish produce availability to a calendar.
- Public calendar view and consumer reservation **requests** (farmer confirms).
- Deployable via Docker + Caddy with automatic HTTPS, launchable with one command.

### Out of scope for Phase 1 (environment prepared, built later)
- Instant, atomic, no-oversell reservation locking (needs Option B/C).
- Online payments / prepayment (BLIK, Przelewy24) — enabled with Option B/C.
- Relational database and migrations.

---

## Requirements

### Requirement 1: Fast public launch
**User Story:** As the site owner, I want the website publicly reachable over HTTPS as early
as possible, so that I can upload the first real content while the rest is still in progress.

#### Acceptance Criteria
1. WHEN the project is started with a single documented command (e.g. `docker compose up`) THEN the system SHALL serve the site over HTTP locally without requiring a database.
2. THE system SHALL render a working homepage, at least one category view, and a blog list using only content read from the storage backend.
3. WHERE a feature area is not yet implemented, THE system SHALL display a clear "in progress / coming soon" indication instead of an error.
4. WHEN deployed to a host with a domain THEN the system SHALL serve all traffic over HTTPS with an automatically provisioned certificate.
5. THE system SHALL start successfully even when optional configuration (e.g. payment keys) is absent.

### Requirement 2: Storage abstraction (no rewrite path to Option B/C)
**User Story:** As the owner, I want all data stored in Amazon S3 with no database now, but
structured so I can later move reservations to DynamoDB or everything to PostgreSQL without
rewriting features.

#### Acceptance Criteria
1. THE system SHALL store all application data as JSON objects in Amazon S3.
2. THE system SHALL access storage only through an abstract `StorageBackend` interface, and SHALL NOT call S3/boto3 directly from routes, services, or templates.
3. THE `StorageBackend` interface SHALL provide at least: get JSON object, put JSON object, list objects by prefix, delete object, and a `try_reserve` operation.
4. WHEN a new backend (DynamoDB or PostgreSQL) is added THEN it SHALL be selectable via configuration without changing feature/route code.
5. IF a requested object does not exist THEN the backend SHALL signal "not found" in a consistent, catchable way (not an unhandled error).
6. THE storage configuration (bucket, region, credentials) SHALL be read from environment variables and SHALL NOT be hard-coded.

### Requirement 3: Content, categories, and blog
**User Story:** As a content author on the team, I want to publish multi-level categories
and blog posts by editing files, so that non-developers can keep the site fresh.

#### Acceptance Criteria
1. THE system SHALL support a hierarchical category model (Category → Subcategory → Chapter/Topic).
2. WHEN a visitor opens a category THEN the system SHALL list its subcategories and published topics.
3. THE system SHALL render topic/blog body content authored in Markdown.
4. THE blog SHALL present posts in reverse-chronological order and show recent updates on the homepage.
5. WHERE a post is marked as draft THEN the system SHALL NOT display it to the public.
6. THE content files SHALL be human-editable (JSON + Markdown) and suitable for editing via GitHub.
7. IF a category or post referenced by a URL does not exist THEN the system SHALL return a 404 page, not a server error.

### Requirement 4: Accounts and authentication
**User Story:** As a user, I want to register and log in securely, so that suppliers and admins
can access protected areas.

#### Acceptance Criteria
1. WHEN a user registers THEN the system SHALL store the password only as a bcrypt hash (passlib) and never in plaintext.
2. WHEN a user logs in with valid credentials THEN the system SHALL issue a JWT stored in a secure, HttpOnly cookie.
3. WHERE the deployment is production THEN the session cookie SHALL be marked Secure and SameSite.
4. WHEN a user logs out THEN the system SHALL invalidate the session cookie.
5. IF login credentials are invalid THEN the system SHALL reject the attempt without revealing which field was wrong.
6. THE system SHALL assign every user exactly one role: `consumer`, `supplier`, or `admin`.

### Requirement 5: Role-based access control
**User Story:** As the owner, I want strict separation between supplier, consumer, and admin
capabilities, so that users only access what their role allows.

#### Acceptance Criteria
1. WHEN an unauthenticated user requests a protected route THEN the system SHALL redirect to login or return 401/403.
2. WHERE a route requires the `supplier` role, THE system SHALL deny access to consumers and unauthenticated users.
3. WHERE a route requires the `admin` role, THE system SHALL deny access to all non-admin users.
4. THE role checks SHALL be enforced server-side via FastAPI dependencies/middleware, not only hidden in the UI.

### Requirement 6: Supplier availability publishing
**User Story:** As a supplier, I want to publish where and when I'll be at a market and how
much produce I have, so that consumers can see live availability.

#### Acceptance Criteria
1. WHEN a supplier creates an availability slot THEN the system SHALL capture market location, date, time window, product, quantity with unit, and optional price and notes.
2. THE system SHALL persist each slot as JSON in S3 via the StorageBackend.
3. WHEN a supplier edits or removes one of their slots THEN the system SHALL update or delete the corresponding object.
4. WHERE a supplier views the dashboard, THE system SHALL show only that supplier's own slots.
5. THE system SHALL associate every slot with a "Verified Farmer" flag controlled by an admin.

### Requirement 7: Public produce calendar
**User Story:** As a consumer, I want to browse a calendar of produce available at local
markets, so that I can plan what and where to buy.

#### Acceptance Criteria
1. WHEN a visitor opens the calendar THEN the system SHALL display upcoming availability slots grouped by date and/or market location.
2. THE system SHALL show per slot: product, quantity available, market, date/time window, supplier name, and Verified Farmer status.
3. WHERE filters are provided (product, location, date) THE system SHALL narrow the displayed slots accordingly.
4. THE calendar SHALL read exclusively through the StorageBackend and SHALL function with no database.

### Requirement 8: Reservation requests (request → confirm)
**User Story:** As a consumer, I want to request a reservation for a quantity of produce, and
as a supplier I want to confirm it, so that stock is arranged without unsafe automatic locking.

#### Acceptance Criteria
1. WHEN a consumer submits a reservation request for a slot THEN the system SHALL record it via the StorageBackend `try_reserve` operation with status `requested`.
2. THE system SHALL NOT automatically decrement slot quantity in Phase 1 (no atomic no-oversell guarantee on S3).
3. WHEN a supplier confirms or declines a request THEN the system SHALL update its status to `confirmed` or `declined`.
4. WHERE the owner later enables Option B/C, THE `try_reserve` call site SHALL remain unchanged while the implementation provides atomic, over-booking-proof reservation.
5. THE reservation request SHALL capture consumer contact/reference, slot reference, requested quantity, and timestamp.
6. IF a reservation references a missing or expired slot THEN the system SHALL reject it with a clear message.

### Requirement 9: Theming / UI configuration
**User Story:** As an admin, I want to adjust the site's colors and fonts from a config, so that
the look can evolve without code changes.

#### Acceptance Criteria
1. THE system SHALL drive key visual tokens (e.g. primary color, accent, font family) via CSS custom properties.
2. THE theme values SHALL be loaded from a JSON config stored via the StorageBackend.
3. WHEN the theme config changes THEN the system SHALL reflect the new values on next page render without code changes.
4. THE UI SHALL be responsive and mobile-friendly to support future PWA/mobile wrapping.

### Requirement 10: Deployment and operations
**User Story:** As the owner, I want a reproducible, one-command deployment with HTTPS, so that
I can launch quickly and let co-workers run and edit it via GitHub.

#### Acceptance Criteria
1. THE system SHALL provide a Dockerfile and docker-compose configuration that run the app and a Caddy (or Nginx) reverse proxy.
2. WHEN deployed with a configured domain THEN Caddy SHALL automatically provision and renew a Let's Encrypt certificate.
3. THE repository SHALL include a step-by-step guide for pointing DNS A/CNAME records to the server.
4. THE system SHALL read all secrets/config from environment variables (`.env` not committed), and SHALL document required variables.
5. THE project SHALL be structured and documented so co-workers can clone from GitHub and run it with the documented command.
6. THE system SHALL expose a health-check endpoint for uptime monitoring.

---

## Prioritization for fast launch

The following requirements are the minimum for a first public launch (ship first):
**R1, R2, R3, R10.** Accounts/roles (R4, R5), supplier publishing (R6), calendar (R7),
reservations (R8), and theming admin (R9) follow incrementally without taking the site
offline.

---

## Glossary
- **StorageBackend**: abstract interface for all persistence; Phase 1 uses `S3StorageBackend`.
- **S3StorageBackend**: the Phase 1 (Option A) implementation of `StorageBackend` storing JSON objects in Amazon S3 via boto3.
- **Option A / B / C**: storage phases — A = S3-only (current), B = S3 + DynamoDB for atomic reservations, C = PostgreSQL + SQLAlchemy + Alembic.
- **Supplier**: a farmer who publishes produce availability.
- **Consumer**: a visitor who browses content and sends reservation requests.
- **Admin**: manages content, categories, users, and theme.
- **AvailabilitySlot**: a supplier's offer at a market (location, time window, product, quantity).
- **Reservation request**: a consumer's request against a slot, confirmed manually by the supplier.
- **try_reserve**: the `StorageBackend` operation that records a reservation; in Option A it records a request, in Option B/C it performs atomic, no-oversell deduction.
- **Verified Farmer**: an admin-controlled trust flag indicating a supplier's cultivation methods have been vetted.

---

## Glossary

- **Option A:** The current Phase 1 build approach using FastAPI + Amazon S3 as the only storage backend, with no database.
- **Option B:** A future approach that keeps content/calendar in S3 but moves stock counters and reservations into DynamoDB for atomic, no-oversell reservations. Added as a new backend without rewriting feature code.
- **Option C:** A future approach that swaps in PostgreSQL + SQLAlchemy 2.0 (async) + Alembic for full relational storage. Added as a new backend without rewriting feature code.
- **StorageBackend:** The abstract storage interface that all data access goes through. Defines operations such as get/put JSON, list by prefix, delete, and `try_reserve`. Decouples feature code from the concrete storage implementation (S3, DynamoDB, or PostgreSQL).
- **S3StorageBackend:** The Option A concrete implementation of `StorageBackend` that reads and writes JSON objects in Amazon S3 using boto3.
- **try_reserve:** The `StorageBackend` operation for recording a reservation. In Option A it records a reservation request (request → confirm); in Option B/C it performs atomic, over-booking-proof stock deduction at the same call site.
- **Consumer:** A user role representing a visitor/customer who browses content, views the produce calendar, and submits reservation requests.
- **Supplier:** A user role representing a local farmer who publishes produce availability (slots) and confirms or declines reservation requests. Also referred to as a farmer.
- **Admin:** A user role with elevated privileges, including managing the "Verified Farmer" flag and theming configuration.
- **Verified Farmer:** An admin-controlled designation marking a supplier whose farm and cultivation methods have been vetted, shown on availability slots as a trust signal.
- **AvailabilitySlot:** A JSON record published by a supplier describing produce available at a specific market location, date, and time window, including product, quantity, unit, and optional price/notes.
- **ProductBatch:** A quantity of a specific product that a supplier makes available, associated with availability slots.
- **Reservation / Reservation Request:** A record capturing a consumer's request for a quantity of produce from a slot, with status `requested`, `confirmed`, or `declined`.
- **Category hierarchy:** The multi-level content structure of Category → Subcategory → Chapter/Topic used to organize editorial content.
- **BlogPost:** A JSON/Markdown content record presented in reverse-chronological order; may be marked as a draft to hide it from the public.
- **Theming engine:** The system that drives visual tokens (colors, fonts) via CSS custom properties, loaded from a JSON config stored via the `StorageBackend`.
- **HTMX:** A frontend library enabling dynamic, reactive page updates from the server without a heavy JavaScript framework.
- **Alpine.js:** A lightweight JavaScript framework for small client-side interactions, used alongside HTMX.
- **Jinja2:** The server-side templating engine used by FastAPI to render HTML pages.
- **Caddy:** The reverse proxy used in deployment to automatically provision and renew Let's Encrypt HTTPS certificates.
- **PWA:** Progressive Web App; a responsive web application packaging approach targeted for future mobile wrapping.
- **BLIK / Przelewy24:** Polish payment methods planned for a later phase (Option B/C), not part of Phase 1.

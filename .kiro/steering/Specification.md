---
inclusion: always
---
<!------------------------------------------------------------------------------------
   Add rules to this file or a short description and have Kiro refine them for you.
   
   Learn about inclusion modes: https://kiro.dev/docs/steering/#inclusion-modes
-------------------------------------------------------------------------------------> 
polskiprimal.pl is a website that will contain informations about:

Ingredients of the products on Polish market
When it comes to food analysis I want to create a catalogue of products from 3 biggest Polish markets - Biedronka, Lidl and Dino. In these catalogues I will not only provide informations about ingredients, but more in-depth analyses regarding whether a given ingredient might have lost,for example 90% of its nutritional content during production

Complex analysis of quality of the products, suppliers, artificial fertilizers they use and more
I will upload data about suppliers, what kind of fertilizers they use, how does it affect vegetables and fruits. Packed products will have descriptions about origin of ingredients and their effects on food quality

Healthy lists “ what to buy for 100 zł to eat healthy for a week in Dino “
Seasonal lists with things to buy in markets, their price and nutrition, lists for students, busy people, adventure food

Primal category - all the informations about primal diet
This will be developed by my friend 
Keto category - informations about Restaurants in Poland that does not use sugar or any sweeteners in their menu, informations what NOT to eat, glycemic index for products,
Everything about keto, especially verified Restaurants ( I will provide informations - which Restaurants are Keto-Firendly
Contact with the farmers, calendar with informations when they are in the local market, possibility to reserve for example 5 kilos of blueberries so that you do not risk shortage of product
Local Delivery and Farmers' Market Calendar:
Instead of just providing a phone number I will create a map or schedule showing when and where a farmer will be present at a local market (e.g., "Mr. Jan – Piaseczno Market, Saturday 7:00 AM–12:00 PM; fresh, pesticide-free strawberries").
Reservation/Prepayment System:
Customers often worry that by the time they arrive at the market, the best products will already be sold out. A reservation feature—potentially involving prepayment (e.g., "Reserve 5 kg of root vegetables for pickup on Saturday")—provides farmers with a reliable sales channel.
Verification and Transparency:
I will act as a guarantor of quality. Provide detailed profiles of the farms, descriptions of their cultivation methods (e.g., natural fertilization versus the use of chemicals), and a "Verified Farmer" designation.
Bulk orders

Categories about ancient herbs, ways of healing with the food and ancient recipes.
This will be developed by a beauty woman with these kind of knowledge



Links to trusted suppliers and websites with healthy food
I will test, order, and describe many websites where customers can buy healthy food. People often complain, that they do not trust websites with herbs, alternative medicine products and other.
Analysis and interviews with well-known doctors, as well as niche analyses.
This will be provided by a beautiful reporter

Sugar addiction - ways of overcoming it.
I will describe how to get out of addiction, which products may cause sugar craving, how to maintain healthy, what to do when your friends/family are eating pasta or pizza and you are hungry but there is no normal food, and many more tips.

These are several categories I will begin with. Website will be developed but these categories I will start with 

This site strives toward such a vision, but the number of categories and topics will surely increase































Technical stack
# Technical Specification & Architecture (Farm-to-Table Platform)

## 0. Current Build Direction (READ FIRST) — Option A: S3, No Database

**We are building Option A: FastAPI + Amazon S3 as the storage backend, with NO traditional database (no PostgreSQL, no Alembic) in the initial phase.**

All application data (farmer profiles, categories, blog posts, calendar availability, reservation requests) is stored as **JSON objects in Amazon S3**. FastAPI reads and writes these JSON files and renders them with Jinja2 + HTMX + Alpine.js + Tailwind.

**Why Option A now:** fast to launch, cheap, no server to run for storage, and the team can edit content directly. It fits the "UI + categories + blog first, engine later" plan.

**Known limit of Option A:** S3 has no locking or transactions, so it cannot safely guarantee instant, no-oversell reservations. Therefore reservations in Option A use a **"request → farmer confirms" model** (a human confirms stock), which avoids race conditions entirely and doubles as a trust feature.

### Future-proofing: path to Option B / Option C (NO rewrite required)
All storage access MUST go through a single abstract `StorageBackend` interface (e.g. `get_json`, `put_json`, `list`, `delete`, plus a `reserve_stock`/`try_reserve` method). Only an `S3StorageBackend` implementation exists now. Because every module depends on the interface and never on S3 directly, we can later add:

* **Option B:** keep content/calendar in S3, but move the stock counter + reservations into **DynamoDB** (serverless, atomic counters, conditional writes) to enable safe, instant, no-oversell reservations and prepayment. This is a new backend class only — no feature rewrite.
* **Option C:** swap in **PostgreSQL + SQLAlchemy 2.0 (async) + Alembic** when a full relational engine is wanted. Again, a new backend implementation behind the same interface.

**Rule for all code:** never call `boto3`/S3 directly from routes or templates. Always go through the `StorageBackend` interface so the backend can change without touching feature code.

## 1. Project Overview & Core Requirements
* **Goal:** A modern, scalable, Python-based farm-to-table web platform connecting local farmers (suppliers) with consumers.
* **Key Features:**
  * **Role-Based Access Control (RBAC):** Strict separation between Supplier and Consumer views and dashboards.
  * **Dual Calendar System:** Suppliers add where/when/how much produce they have at a market; consumers view live availability and send reservation requests. (Option A: request → farmer confirms. Instant no-oversell locking arrives with Option B/C.)
  * **Dynamic & Real-Time Content:** Built for fast initial deployment and continuous content updates.
  * **Theming / UI Configuration Engine:** Fully customizable design system to appeal to modern youth and general users, allowing easy style/theme switching.
  * **Categorized Content & Blog:** Multi-level category hierarchy with chapters/topics on healthy nutrition, plus a live blog feed showing recent updates and new drops.
  * **Payment Integration (later phase):** BLIK (via direct REST API integration), Przelewy24, and traditional bank transfers. Prepayment for reservations arrives with Option B/C (safe stock handling); Option A supports manual/offline payment arrangement.
  * **Mobile Scalability:** Designed with a responsive architecture ready to be wrapped into a mobile application (e.g., via Capacitor/React Native or PWA) in the future.

---

## 2. Technology Stack (Python-Centric)
* **Backend:** Python 3.11+ with **FastAPI** (asynchronous, high performance, automatic Swagger/OpenAPI documentation).
* **Frontend:** **HTMX** + **Tailwind CSS** + **Alpine.js** (rendered via **Jinja2** templates). Provides a modern, reactive single-page application (SPA) feel without the heavy overhead of React/Next.js, ensuring fast load times for everyday users.
* **Storage (Option A — current):** **Amazon S3** holding JSON objects, accessed only through an abstract `StorageBackend` interface (`S3StorageBackend` implementation). **No PostgreSQL / SQLAlchemy / Alembic yet.**
* **Storage (Option B/C — later, no rewrite):** add a `DynamoDBStorageBackend` (for safe reservations) and/or a **PostgreSQL + SQLAlchemy 2.0 (Async) + Alembic** backend behind the same interface.
* **Theming Engine:** Dynamic Tailwind CSS theme configuration stored as a JSON config in S3 (later movable to DB), injected via CSS variables (`--primary-color`, `--font-family`, etc.) for instant site styling changes.

---

## 3. Core Modules & Architecture Design

### A. User Management & Role Separation
* User records stored as JSON in S3 with a `role` field (`supplier`, `consumer`, `admin`).
* Middleware / Dependency injection in FastAPI to restrict routes based on roles (e.g., suppliers can manage their availability; consumers can browse and send reservation requests).

### B. Calendar & Reservation Engine (Option A)
* JSON objects in S3 model `ProductBatches`, `AvailabilitySlots`, and `Reservations` (same concepts as the future DB tables, so the data shape carries over).
* Suppliers write availability (market location, date/time window, product, quantity) into S3 JSON. Consumers read it to view the live calendar.
* **Reservations are requests the farmer confirms** (no instant stock deduction) to avoid S3 race conditions. The `StorageBackend` exposes a `try_reserve` method whose Option A implementation records a request; Option B/C implementations perform atomic, no-oversell deduction — same call site, no feature rewrite.

### C. Content, Blog & Multi-Level Categories
* Hierarchical category model (`Categories` -> `Subcategories` -> `Chapters/Topics`) stored as JSON in S3.
* Blog feed stored as JSON in S3 for chronological updates, tips, and healthy eating guides; the team edits content directly.

### D. Payments Integration (BLIK API & Przelewy24) — later phase
* **BLIK:** Direct REST API integration with the payment gateway to handle code generation and instant push/callback confirmation.
* **Przelewy24:** Webhook listeners (`/api/v1/payments/webhook`) to automatically update order statuses from `pending` to `paid`.
* Enabled together with Option B/C, when safe stock reservation + prepayment are available.

---

## 4. Infrastructure: How to Connect a Domain and Database

To make your application live and fully operational on the internet, follow these steps:

### Step 1: Storage Setup (Amazon S3 — Option A)
1. **Create an S3 Bucket:** In the AWS console create a private bucket (e.g. `polskiprimal-data`) in a nearby region (e.g. `eu-central-1`).
2. **Create IAM Credentials:** Create an IAM user/role with permission to read/write objects in that bucket only. You get an `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
3. **Configure Environment:** Store these safely in the backend's `.env` file:
   `S3_BUCKET=polskiprimal-data`
   `AWS_REGION=eu-central-1`
   `AWS_ACCESS_KEY_ID=...`
   `AWS_SECRET_ACCESS_KEY=...`
   The app accesses S3 only through the `StorageBackend` interface, so these settings are the single place storage is configured.
4. **(Later — Option B/C)** When safe reservations/prepayment are needed, add DynamoDB and/or a managed PostgreSQL provider (**Supabase**, **Neon**, **Render**) and set `DATABASE_URL` (`postgresql+asyncpg://user:password@hostname:5432/dbname`). No feature code changes — only a new storage backend.

### Step 2: Domain Setup & Deployment
1. **Deploy the App:** Host your FastAPI application on a cloud platform like **Render**, **Fly.io**, or a dedicated **VPS (Hetzner/DigitalOcean)** via Docker.
2. **Buy a Domain:** Purchase your domain from a registrar (e.g., OVH, Cyberfolks, Namecheap).
3. **Configure DNS Records:**
   * Create an **A Record** pointing your root domain (e.g., `yoursite.com`) to your server's public IP address.
   * Create a **CNAME Record** for `www` pointing to your root domain.
4. **SSL/TLS Certificate:** Use a reverse proxy like **Caddy** (which automatically provisions free SSL certificates via Let's Encrypt) or configure Certbot on Nginx to ensure your site runs securely over `HTTPS` (mandatory for handling payments and user data).










Steps
Step 1: Project Initialization & Structure (FastAPI + Tailwind)
Task for Kiro:
Create a Python-based project structure (FastAPI) using Jinja2 templates, HTMX, Alpine.js, and Tailwind CSS. Configure docker-compose.yml and Dockerfile so the application can be launched with a single command on any server.

Step 2: Storage Configuration & Models (Amazon S3 — Option A, NO database)
(At this stage we do NOT use a database. No PostgreSQL, no Alembic. We start with FastAPI + Amazon S3, plus a full user interface, categories and blog where the team types the content. PostgreSQL/DynamoDB become an option later — see Section 0, Option B/C — without a rewrite.)
Task for Kiro:
Configure an abstract `StorageBackend` interface and an `S3StorageBackend` implementation (using boto3) that stores/reads JSON objects in S3. Define the core data shapes as Pydantic models — User (role: supplier, consumer, admin), Product, Category (multi-level), BlogPost, and the calendar shapes ProductBatch / AvailabilitySlot / Reservation — serialized to JSON in S3. All reads/writes go through the interface so a DynamoDB or PostgreSQL+SQLAlchemy+Alembic backend can be added later without changing feature code.

Step 3: Security & Authentication Engine
Task for Kiro:
Implement a secure login and registration system. Passwords must be hashed using passlib (bcrypt), and sessions must rely on secure, encrypted HttpOnly cookies with JWT tokens. Add FastAPI middleware to verify user roles (protecting supplier dashboards).

Step 4: Modern Styling & Theming System (Aesthetics)
Task for Kiro:
Create a flexible styling system based on Tailwind CSS and CSS Custom Properties, allowing easy customization of colors and site design via a config file or admin panel. Design a modern, minimalist, and clean user interface (homepage, category view, blog section with recent updates).

Step 5: Reservation Calendar (Suppliers & Consumers) — Option A
Task for Kiro:
Implement a calendar module for supplier and consumer roles backed by S3 JSON (via the StorageBackend interface). Suppliers define available product batches (ProductBatches) and time slots (AvailabilitySlots) with market location, date/time window, product and quantity. Consumers browse the live calendar and send reservation requests which the farmer confirms (request → confirm model), since S3 cannot do atomic no-oversell locking. The `try_reserve` call sits behind the StorageBackend interface so that Option B (DynamoDB) or Option C (PostgreSQL) can later provide instant, atomic, over-booking-proof reservations and prepayment with no change to the calendar feature code.

Step 6: Production Deployment & Domain Setup Preparation
Task for Kiro:
Prepare the application for production deployment. Configure a Caddy (or Nginx) reverse proxy in Docker with automatic SSL certificate generation (Let's Encrypt) for your domain. Provide a step-by-step guide on how to point your domain registrar's DNS records to the server's public IP address.




Tips and important information.
Kiro creates architecture
My team creates valuable information for users.
That is why I want to store all the code and data in GitHub, so that my co-workers can also edit the code and text.

Things that will be done later, but you have to create an environment for them
Database, calendar, reservation machine.

Important. I want to create a whole website according to the Steps, but I want to launch the website as fast as possible so that I can upload first data. It means I want it to be instantl avaliable for other, even though It will be in progress.

UI - Polish




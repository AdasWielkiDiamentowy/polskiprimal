# Wdrożenie / Deployment — polskiprimal.pl

## Skrót po polsku

1. Wynajmij serwer (VPS, np. Hetzner/DigitalOcean) z Dockerem i otwórz porty **80** i **443**.
2. W panelu rejestratora domeny dodaj rekord **A** (`polskiprimal.pl` → IP serwera) oraz
   **CNAME** (`www` → `polskiprimal.pl`). Poczekaj na propagację DNS.
3. Skopiuj repozytorium z GitHuba, utwórz plik `.env` (patrz niżej) i ustaw
   `SITE_ADDRESS="polskiprimal.pl, www.polskiprimal.pl"`.
4. Uruchom jedną komendą: `docker compose up -d --build`.
5. Caddy samo pobierze i będzie odnawiać certyfikat HTTPS (Let's Encrypt).
6. Wgraj startową treść do S3: `docker compose exec app python -m app.seed`.

Lokalnie (bez domeny i bez konta AWS): `docker compose up --build`, strona działa pod
http://localhost z przykładowymi treściami z katalogu `content/`.

---

## 1. What you get

`docker compose up` starts:

| Service | Purpose | Reachable from |
|---------|---------|----------------|
| `app`   | FastAPI app (uvicorn), Tailwind CSS built into the image | private network only (port 8000) |
| `caddy` | Reverse proxy, automatic HTTPS (Let's Encrypt) in production, plain HTTP locally | ports 80/443 on the host |
| `minio` + `minio-init` | *Optional* local S3 (profile `minio`) | `127.0.0.1:9000` / console `127.0.0.1:9001` |

There is no database. Content and (later) accounts, calendar slots and reservations are JSON
objects in Amazon S3 (see `design.md` in `.kiro/specs/polskiprimal-platform/`).

## 2. Run it locally (any machine with Docker)

Requires Docker with Compose v2.24 or newer (`docker compose version`).

```bash
git clone <URL-of-the-github-repo> polskiprimal
cd polskiprimal
docker compose up --build
```

Open http://localhost (health check: http://localhost/health). With no `.env` the app uses
the **in-memory** backend pre-loaded with the starter content in `content/`; data is lost
when the container restarts. Stop with `Ctrl+C` (or `docker compose down`).

If port 80 is already in use, set `HTTP_PORT=8080` in `.env` and open http://localhost:8080.

### Local S3 with MinIO (optional)

Put this in `.env`, then start with the `minio` profile:

```dotenv
STORAGE_BACKEND=s3
S3_BUCKET=polskiprimal-data
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
S3_ENDPOINT_URL=http://minio:9000
```

```bash
docker compose --profile minio up --build
docker compose exec app python -m app.seed     # upload the starter content to MinIO
```

`minio-init` creates the bucket automatically. The MinIO console is at http://localhost:9001
(user/password `minioadmin` unless you set `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`).

## 3. Go live (production)

### 3.1 Server

- A Linux VPS (1 vCPU / 1 GB RAM is enough to start) with a public IPv4 address.
- Install Docker Engine + the Compose plugin: https://docs.docker.com/engine/install/
- Open firewall ports **80/tcp**, **443/tcp** and **443/udp** (HTTP/3). Port 80 must stay
  open: Let's Encrypt uses it to validate the domain and Caddy redirects it to HTTPS.
- Do **not** publish port 8000 or the MinIO ports to the internet.

### 3.2 DNS records (at your domain registrar, e.g. OVH, Cyberfolks, Namecheap)

Find the server's public IP (shown in the hosting panel, or `curl -4 ifconfig.me` on the server).

| Type  | Name / Host | Value                    | TTL    |
|-------|-------------|--------------------------|--------|
| A     | `@` (root, `polskiprimal.pl`) | `<server IPv4>`  | 300 s  |
| CNAME | `www`       | `polskiprimal.pl.`       | 300 s  |
| AAAA  | `@` *(only if the server has a public IPv6)* | `<server IPv6>` | 300 s |

Notes:

- Some panels want the root written as `@`, others as an empty field or the full domain.
  The CNAME target may need a trailing dot (`polskiprimal.pl.`).
- Remove old/parking A or AAAA records for the same names, otherwise Let's Encrypt may hit
  the wrong server.
- DNS can take from a few minutes up to 24 h. Check before launching:
  `nslookup polskiprimal.pl` and `nslookup www.polskiprimal.pl` must return your server IP.
  Starting Caddy before DNS is correct can trigger Let's Encrypt failures and rate limits.

### 3.3 Amazon S3 storage

1. Create a **private** bucket (e.g. `polskiprimal-data`) in `eu-central-1`.
   Keep "Block all public access" enabled.
2. Create an IAM user (or role) limited to that bucket, for example:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:ListBucket"],
         "Resource": "arn:aws:s3:::polskiprimal-data"
       },
       {
         "Effect": "Allow",
         "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
         "Resource": "arn:aws:s3:::polskiprimal-data/*"
       }
     ]
   }
   ```

3. Create an access key for that user and put it in `.env` (next section).

### 3.4 Configuration (`.env`)

```bash
cp .env.example .env      # then edit it; .env is git-ignored and never committed
```

| Variable | Required | Meaning |
|----------|----------|---------|
| `SITE_ADDRESS` | for HTTPS | Your domain(s), e.g. `"polskiprimal.pl, www.polskiprimal.pl"`. Unset = plain HTTP on `http://localhost`. |
| `APP_ENV` | yes | `prod` in production (`dev` by default). |
| `BASE_URL` | yes | Public URL, e.g. `https://polskiprimal.pl`. |
| `SECRET_KEY` | yes | Long random string, used to sign sessions once login ships. Generate: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `STORAGE_BACKEND` | yes | `s3` for real data. Defaults to `memory` under Docker if unset (demo only, data lost on restart). |
| `S3_BUCKET` | with `s3` | Bucket name, e.g. `polskiprimal-data`. |
| `AWS_REGION` | with `s3` | e.g. `eu-central-1`. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | with `s3` | IAM credentials. Set both, or leave both empty to use an instance IAM role. |
| `S3_ENDPOINT_URL` | no | Only for MinIO/other S3-compatible servers. Leave unset for AWS. |
| `HTTP_PORT`, `HTTPS_PORT` | no | Host ports for Caddy (defaults 80 / 443). |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | no | Only for the optional `minio` profile. |
| `DATABASE_URL`, `BLIK_API_KEY`, `PRZELEWY24_*` | no | Reserved for later phases; leave empty. |

Example production `.env`:

```dotenv
APP_ENV=prod
BASE_URL=https://polskiprimal.pl
SECRET_KEY=<generated random string>
SITE_ADDRESS="polskiprimal.pl, www.polskiprimal.pl"
STORAGE_BACKEND=s3
S3_BUCKET=polskiprimal-data
AWS_REGION=eu-central-1
AWS_ACCESS_KEY_ID=<key id>
AWS_SECRET_ACCESS_KEY=<secret>
```

Secrets live only in `.env` on the server (or in your secret manager). Never commit them and
never paste them into issues or chat.

### 3.5 Launch (one command)

```bash
docker compose up -d --build
```

Then load the starter content into S3 (once; existing objects are not overwritten):

```bash
docker compose exec app python -m app.seed
```

Verify:

```bash
docker compose ps                         # app = healthy, caddy = running
docker compose logs -f caddy              # look for "certificate obtained successfully"
curl -I https://polskiprimal.pl/health    # HTTP/2 200
```

Caddy obtains the Let's Encrypt certificate on the first request/start and renews it
automatically. Certificates are stored in the `caddy_data` volume: do not delete it
(`docker compose down` keeps volumes; `docker compose down -v` deletes them).

Set up an external uptime monitor (e.g. UptimeRobot) on `https://polskiprimal.pl/health`.

### 3.6 Updating the live site

```bash
git pull
docker compose up -d --build
```

Content changes (categories, blog, theme) live in S3 once seeded. Editing files in
`content/` and pushing to GitHub updates the *starter* content only. To publish repo
versions to S3 run `docker compose exec app python -m app.seed` (adds new objects) or
`... python -m app.seed --overwrite` (**replaces** existing objects, including edits
made directly in S3: use with care).

### 3.7 Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Browser shows a certificate warning / `docker compose logs caddy` shows ACME errors | DNS does not point to this server yet, or ports 80/443 are blocked by a firewall or the hosting provider. |
| Site is up but has no content | `STORAGE_BACKEND` is still `memory`/`s3` without valid `S3_BUCKET`, `AWS_REGION`, credentials; or the seed was not run. Check `docker compose logs app`. |
| `env_file ... required` / unknown field errors | Docker Compose is older than 2.24. Upgrade Compose. |
| `port is already allocated` | Another service uses port 80/443. Stop it or change `HTTP_PORT` / `HTTPS_PORT` (production needs 80 and 443). |

## 4. For co-workers: clone, run, edit

1. `git clone <repo-url>` and `cd` into it.
2. `docker compose up --build`, then open http://localhost. No AWS account or `.env` needed.
3. Content is plain JSON/Markdown in `content/` (`categories/`, `blog/`, `config/theme.json`).
   Edit it in GitHub or locally, open a pull request. The files are copied into the image,
   so after editing run `docker compose up --build` to see the change (the in-memory
   backend loads them on every container start).
4. Without Docker (Python 3.11+): see `README.md` (`uvicorn app.main:app --reload`). For the
   compiled Tailwind stylesheet run `npm install && npm run build:css` (optional; without it
   the page falls back to the Tailwind CDN).
5. Never commit `.env`, keys or passwords. `.env.example` is the only env file in git.

## 5. Notes

- The page still loads HTMX and Alpine.js from public CDNs (unpkg). Self-hosting them is a
  possible later hardening step.
- Option B/C (DynamoDB / PostgreSQL) will be added as new storage backends; the Docker and
  Caddy setup does not change.

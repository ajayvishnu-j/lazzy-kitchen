# 🍽️ Hotel Lazzy-Kitchen

A production-style **hotel dining food ordering web application**, built for learning and demonstration purposes.

> ⚠️ **This project uses a MOCK payment system only.** No real payment gateway, card processing, UPI, or wallet integration is used anywhere. See [Security Notes](#security-notes).

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Docker Setup](#docker-setup)
- [Database Setup](#database-setup)
- [Running Locally](#running-locally)
- [Testing](#testing)
- [Jenkins Setup](#jenkins-setup)
- [GitHub Setup](#github-setup)
- [Slack Webhook Setup](#slack-webhook-setup)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)
- [Security Learning](#security-learning)
- [Scope Restrictions](#scope-restrictions)

---

## Project Overview

Hotel Lazzy-Kitchen is a digital dining ordering system for customers eating **inside** the restaurant (dine-in only — no delivery, no room service). A customer:

1. Registers with name, mobile, email, table number, and password.
2. Browses the South Indian tiffin menu.
3. Adds items to a cart.
4. Reviews the order and completes a **simulated** payment.
5. Receives an order confirmation; the kitchen gets a Slack notification.

---

## Architecture

```
                    Internet / Browser
                           |
                           v
                        Nginx
                    Reverse Proxy (:80)
                           |
             +-------------+-------------+
             |                           |
             v                           v
       Frontend Container          Backend Container
       (Nginx + static files)      (Python Flask API)
                                         |
                                         v
                                  MySQL Container
                                         |
                                         v
                                  Slack Webhook
```

Containers: `lazzy-nginx`, `lazzy-frontend`, `lazzy-backend`, `lazzy-mysql`.

Only `lazzy-nginx` is exposed to the host, on port 80. The frontend, backend, and MySQL communicate over an internal Docker network (`lazzy-network`) and are not directly reachable from the browser.

---

## Technology Stack

| Layer          | Technology                                  |
|----------------|----------------------------------------------|
| Frontend       | HTML5, CSS3, Vanilla JavaScript              |
| Backend        | Python, Flask, SQLAlchemy                    |
| Database       | MySQL 8.4                                    |
| Reverse Proxy  | Nginx                                        |
| Containers     | Docker, Docker Compose                       |
| CI/CD          | Jenkins                                      |
| Notifications  | Slack Incoming Webhooks                      |
| Source Control | Git, GitHub                                  |

---

## Prerequisites

- Docker Desktop (macOS/Windows) or Docker Engine + Compose plugin (Linux)
- Git
- A code editor (VS Code recommended)
- (Optional) Python 3.12 locally, if you want to run the backend outside Docker for development

---

## Installation

```bash
git clone https://github.com/<your-username>/lazzy-kitchen.git
cd lazzy-kitchen
cp .env.example .env
```

Edit `.env` and set real values for `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`, `SECRET_KEY`, and `SLACK_WEBHOOK_URL`.

---

## Environment Variables

All secrets are supplied via environment variables — **never hardcoded**. See `.env.example`:

```env
MYSQL_ROOT_PASSWORD=change_this_root_password
MYSQL_DATABASE=lazzy_kitchen
MYSQL_USER=lazzy_user
MYSQL_PASSWORD=change_this_password

SECRET_KEY=change_this_to_a_long_random_string
CORS_ORIGINS=http://localhost

SLACK_WEBHOOK_URL=https://hooks.slack.com/services/CHANGE/THIS/WEBHOOK
```

`.env` is listed in `.gitignore` and must never be committed.

---

## Docker Setup

Each service has its own Dockerfile under `docker/`:

- `docker/frontend.Dockerfile` — Nginx serving the static frontend.
- `docker/backend.Dockerfile` — Python Flask app run via Gunicorn.
- `docker/nginx.Dockerfile` — The reverse-proxy Nginx layer.

MySQL uses the official `mysql:8.4` image with a named volume (`mysql_data`) so data survives container restarts.

---

## Database Setup

The schema and seed data live in `database/init.sql` and run automatically the **first time** the MySQL container starts (via `docker-entrypoint-initdb.d`).

Tables: `customers`, `menu_items`, `orders`, `order_items`, `restaurant_config`.

To re-seed from scratch, remove the volume (see [Troubleshooting](#troubleshooting)) and start again.

---

## Running Locally

```bash
docker compose build
docker compose up -d
docker compose ps
```

Then open:

```
http://localhost
```

View logs:

```bash
docker compose logs -f
```

Stop everything:

```bash
docker compose down
```

Stop and **remove all data** (containers, network, and the MySQL volume):

```bash
docker compose down -v
```

---

## Testing

Backend tests use `pytest` and an in-memory SQLite database, so they don't require a running MySQL server:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest tests/
```

Covered: registration (valid/invalid), menu listing & availability, order creation, invalid demo payment, cart total calculation, order history, health endpoint.

---

## Jenkins Setup

1. Install Jenkins with the Docker Pipeline plugin.
2. Create a new Pipeline job pointing at this repository's `Jenkinsfile`.
3. Ensure the Jenkins agent has Docker and Docker Compose available.
4. Add any required credentials (e.g., a `.env` file or environment variables) as Jenkins credentials/secrets — never in the repo.
5. Trigger the pipeline manually or via a GitHub webhook on push.

Pipeline stages: Checkout → Install Dependencies → Lint → Run Tests → Validate Docker Compose → Build Images → Deploy → Health Check.

---

## GitHub Setup

```bash
git init
git add .
git commit -m "Initial commit: Hotel Lazzy-Kitchen"
git branch -M main
git remote add origin https://github.com/<your-username>/lazzy-kitchen.git
git push -u origin main
```

Confirm `.env` is **not** tracked:

```bash
git status --ignored
```

---

## Slack Webhook Setup

1. Go to <https://api.slack.com/apps> and create a new Slack app (or use an existing one).
2. Enable **Incoming Webhooks** and add a new webhook to the channel you want order alerts in.
3. Copy the webhook URL into `.env` as `SLACK_WEBHOOK_URL`.
4. Restart the backend: `docker compose restart backend`.

The webhook URL is read only by the backend and is never sent to the browser.

---

## API Documentation

Base path: `/api`

| Method | Endpoint                          | Description                          |
|--------|------------------------------------|---------------------------------------|
| POST   | `/api/register`                    | Create a customer account             |
| POST   | `/api/login`                       | Customer login                        |
| GET    | `/api/menu`                        | List all menu items + restaurant status |
| GET    | `/api/menu/<id>`                   | Get a single menu item                |
| GET    | `/api/status`                      | Restaurant open/closed & prep time    |
| POST   | `/api/orders`                      | Place an order (with demo payment)    |
| GET    | `/api/orders/<order_number>`       | Get a single order                    |
| GET    | `/api/customer/<id>/orders`        | Get a customer's order history        |
| GET    | `/api/health`                      | Health check                          |

**Example — place an order:**

```json
POST /api/orders
{
  "customer_id": 1,
  "table_number": "12",
  "items": [{ "menu_item_id": 1, "quantity": 2 }],
  "payment": { "card_number": "1234 4321 5678 8765", "pin": "4321", "cvv": "123" }
}
```

**Response:**

```json
{
  "success": true,
  "message": "Order placed successfully.",
  "order": { "order_number": "LZK-20260810-0001", "status": "PLACED", "...": "..." },
  "estimated_preparation": "15-25 minutes"
}
```

---

## Troubleshooting

**Port 80 already in use** — stop whatever is bound to it, or change the host port mapping in `docker-compose.yml` under the `nginx` service.

**Backend can't connect to MySQL** — wait a few seconds after `docker compose up -d`; the backend has a health check dependency on MySQL being healthy first. Check with `docker compose logs mysql`.

**Reset everything (including data):**

```bash
docker compose down -v
docker compose up -d --build
```

**Rebuild after code changes:**

```bash
docker compose up -d --build
```

---

## Security Notes

- Passwords are hashed with Werkzeug's `generate_password_hash` — never stored in plain text.
- Card number, PIN, and CVV are validated against fixed demo values **in memory only** and are **never written to the database or logs**.
- MySQL is not exposed to the host by default.
- All secrets come from environment variables, never hardcoded.
- Backend re-validates everything the frontend sends (prices, quantities, availability) — frontend validation is a UX convenience only.
- Error responses never leak Python stack traces to the client.

---

## Security Learning

This project intentionally demonstrates good practices for learners:

- **Why passwords are hashed:** if the database is ever leaked, hashed passwords can't be reversed into the originals, protecting customers who reuse passwords elsewhere.
- **Why secrets shouldn't be committed to Git:** committed secrets stay in version history forever, even after "deleting" them in a later commit.
- **Why payment information isn't stored:** minimizing what sensitive data you hold reduces the impact of any future breach — you can't leak what you never saved.
- **Why MySQL shouldn't be publicly exposed:** database ports are a common target for automated attacks; only the application layer should reach it.
- **Why Nginx is used as a reverse proxy:** it centralizes TLS, routing, and headers, and hides internal service topology from the internet.
- **Why backend validation is required:** client-side JavaScript can be bypassed entirely by anyone using browser dev tools or calling the API directly.
- **Why frontend validation alone is insufficient:** it only improves user experience — it enforces nothing.
- **Why environment variables are used:** they let the same codebase run in different environments (dev/staging/prod) without code changes or leaked secrets.
- **Basic Docker security:** run containers with least privilege, don't expose ports you don't need, and keep base images patched.
- **Basic API security:** validate all inputs server-side, use parameterized queries (SQLAlchemy ORM does this for you), and return generic error messages to clients.

---

## Scope Restrictions

This version is a **dining ordering system only**. It intentionally does **not** implement: hotel room booking, room service, delivery, real payment gateways, real card processing, UPI, wallets, banking APIs, or stored credit card data.

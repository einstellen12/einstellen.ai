# Subscription & Billing Microservice

This is a Django-based microservice for managing subscriptions and billing within a SaaS platform. It supports plan management, payment integration with Stripe, Razorpay, and PayPal, SaaS-based billing, auto-renewals, and invoice generation, using PostgreSQL as its database.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Setup](#setup)
- [Database Schema](#database-schema)
- [Microservice Architecture](#microservice-architecture)
- [API Endpoints](#api-endpoints)
- [Usage](#usage)
- [Deployment](#deployment)

## Overview

The Subscription & Billing Microservice handles subscription plans, tenant-based billing, and payment processing for a SaaS application. It integrates with an Authentication Service for JWT-based security and supports multiple payment gateways for flexibility.

## Features

- Plan management with predefined tiers (HumanLite, HumanAdv, HumanPro).
- Payment integration with Stripe, Razorpay, and PayPal.
- SaaS-based billing tied to tenants.
- Auto-renewal support with invoice generation.
- Webhook support for payment confirmation (Stripe).

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis (optional for caching)
- uWSGI
- Docker (optional for deployment)
- Accounts with Stripe, Razorpay, and PayPal

### Installation

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd billing_service
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Ensure `requirements.txt` includes:
   ```
   Django==4.2.7
   djangorestframework==3.14.0
   psycopg2-binary==2.9.9
   python-jose==3.3.0
   redis==5.0.1
   python-dotenv==1.0.1
   uwsgi==2.0.23
   stripe==7.0.0
   razorpay==1.4.1
   paypalrestsdk==1.13.1
   ```

3. **Set Environment Variables**:
   Create a `.env` file in the root directory:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=False
   DATABASE_URL=postgres://user:password@localhost:5432/billing_db
   REDIS_HOST=localhost
   REDIS_PORT=6379
   EMAIL_HOST=smtp.example.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=your-email@example.com
   EMAIL_HOST_PASSWORD=your-email-password
   EMAIL_USE_TLS=True
   RECIPIENT_LIST=admin1@example.com,admin2@example.com
   JWT_SECRET=your-jwt-secret
   JWT_EXPIRY=3600
   STRIPE_SECRET_KEY=your-stripe-secret-key
   STRIPE_WEBHOOK_SECRET=your-stripe-webhook-secret
   RAZORPAY_KEY_ID=your-razorpay-key-id
   RAZORPAY_KEY_SECRET=your-razorpay-key-secret
   PAYPAL_CLIENT_ID=your-paypal-client-id
   PAYPAL_CLIENT_SECRET=your-paypal-client-secret
   PAYPAL_MODE=sandbox
   ```

4. **Run Migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Seed Plans (Optional)**:
   ```bash
   python manage.py shell
   ```
   ```python
   from billing.models import Plan
   Plan.objects.create(name='HumanLite', description='Basic plan', price=10.00)
   Plan.objects.create(name='HumanAdv', description='Advanced plan', price=20.00)
   Plan.objects.create(name='HumanPro', description='Pro plan', price=30.00)
   ```

6. **Test Locally**:
   ```bash
   python manage.py runserver
   ```

## Database Schema

The microservice uses PostgreSQL with the following schema:

```mermaid
erDiagram
    Plan ||--o{ Subscription : offers
    Subscription ||--o{ Invoice : generates
    Subscription ||--o{ AuditLog : logs
    Invoice ||--o{ AuditLog : logs

    Plan {
        UUID id PK
        VARCHAR name "HumanLite, HumanAdv, HumanPro"
        TEXT description
        DECIMAL price
        VARCHAR billing_cycle "e.g., monthly"
        TIMESTAMP created_at
    }

    Subscription {
        UUID id PK
        UUID tenant_id FK "From Auth Service"
        UUID plan_id FK
        VARCHAR payment_method "stripe, razorpay, paypal"
        VARCHAR payment_id "External payment ID"
        VARCHAR status "active, pending, cancelled, expired"
        TIMESTAMP start_date
        TIMESTAMP end_date
        BOOLEAN auto_renew
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    Invoice {
        UUID id PK
        UUID subscription_id FK
        DECIMAL amount
        VARCHAR status "paid, unpaid, failed"
        TIMESTAMP invoice_date
        TIMESTAMP due_date
        VARCHAR payment_id "External payment ID"
        TIMESTAMP created_at
    }

    AuditLog {
        UUID id PK
        UUID user_id FK "Nullable"
        VARCHAR action
        VARCHAR ip_address
        VARCHAR tenant
        JSON details
        TIMESTAMP timestamp
    }
```

## Microservice Architecture

The architecture shows how the Subscription & Billing Microservice interacts with other components:

```mermaid
graph TD
    A[Client] -->|HTTP Requests| B[API Gateway]
    B -->|JWT Validation| C[Auth Service]
    B -->|Routes Requests| D[Subscription & Billing Microservice]
    D -->|Stores Data| E[PostgreSQL]
    D -->|Caches Data| F[Redis]
    D -->|Logs Errors| G[Email Service]
    D -->|Audit Logs| E
    D -->|Payments| H[Stripe]
    D -->|Payments| I[Razorpay]
    D -->|Payments| J[PayPal]
    H -->|Webhook| D

    subgraph Subscription & Billing Microservice
        D1[Views]
        D2[Payment Handlers]
        D3[Middleware]
        D1 --> D2
        D1 --> D3
    end

    C -->|JWT Token| A
```

- **Client**: Sends HTTP requests to the API Gateway.
- **API Gateway**: Routes requests and validates JWT tokens with the Auth Service.
- **Auth Service**: Provides JWT tokens for authentication.
- **Subscription & Billing Microservice**: Manages plans, subscriptions, and billing.
- **PostgreSQL**: Stores persistent data (plans, subscriptions, invoices).
- **Redis**: Used for caching (optional).
- **Email Service**: Receives error logs.
- **Stripe/Razorpay/PayPal**: Handles payment processing, with Stripe supporting webhooks.

## API Endpoints

| **Endpoint**                          | **Method** | **Description**                          | **Request Body**                              | **Response**                              |
|---------------------------------------|------------|------------------------------------------|-----------------------------------------------|-------------------------------------------|
| `/plans/`                             | GET        | List all plans                           | -                                             | `[{plan_list}]`                           |
| `/subscriptions/create/`              | POST       | Create a subscription                    | `{plan_id, payment_method}`                   | `{subscription_id, payment_id}`           |
| `/subscriptions/{subscription_id}/`   | GET        | Retrieve subscription details            | -                                             | `{subscription_details}`                  |
| `/subscriptions/{subscription_id}/cancel/` | POST  | Cancel a subscription                    | -                                             | `{message}`                               |
| `/invoices/`                          | GET        | List tenant invoices                     | -                                             | `[{invoice_list}]`                        |
| `/invoices/{invoice_id}/pay/`         | POST       | Pay an invoice                           | -                                             | `{message, payment_id}`                   |
| `/webhook/stripe/`                    | POST       | Handle Stripe webhook events             | Stripe webhook payload                        | `{message}`                               |

**Authentication**: All endpoints except `/webhook/stripe/` require a `Bearer {{jwt_token}}` header.

## Usage

1. **List Plans**:
   ```bash
   curl -X GET {{base_url}}/plans/ \
   -H "Authorization: Bearer {{jwt_token}}"
   ```

2. **Create a Subscription (Stripe)**:
   ```bash
   curl -X POST {{base_url}}/subscriptions/create/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"plan_id": "{{plan_id}}", "payment_method": "stripe"}'
   ```

3. **Get Subscription Details**:
   ```bash
   curl -X GET {{base_url}}/subscriptions/{{subscription_id}}/ \
   -H "Authorization: Bearer {{jwt_token}}"
   ```

4. **Cancel a Subscription**:
   ```bash
   curl -X POST {{base_url}}/subscriptions/{{subscription_id}}/cancel/ \
   -H "Authorization: Bearer {{jwt_token}}"
   ```

5. **List Invoices**:
   ```bash
   curl -X GET {{base_url}}/invoices/ \
   -H "Authorization: Bearer {{jwt_token}}"
   ```

6. **Pay an Invoice**:
   ```bash
   curl -X POST {{base_url}}/invoices/{{invoice_id}}/pay/ \
   -H "Authorization: Bearer {{jwt_token}}"
   ```

7. **Stripe Webhook (Testing)**:
   - Use Stripe CLI:
     ```bash
     stripe listen --forward-to localhost:8000/webhook/stripe/
     ```

## Deployment

### uWSGI Configuration

1. **Create a uWSGI Configuration File**:
   Create `uwsgi.ini` in the project root:
   ```ini
   [uwsgi]
   module = billing_service.wsgi:application
   master = true
   processes = 4
   threads = 2
   socket = 0.0.0.0:8000
   chmod-socket = 666
   vacuum = true
   die-on-term = true
   logto = /var/log/uwsgi/billing.log
   ```

2. **Run uWSGI Locally**:
   ```bash
   uwsgi --ini uwsgi.ini
   ```

### Docker Deployment with uWSGI

1. **Dockerfile**:
   ```dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY . .

   ENV PYTHONUNBUFFERED=1

   CMD ["uwsgi", "--ini", "uwsgi.ini"]
   ```

2. **docker-compose.yml**:
   ```yaml
   version: '3.8'

   services:
     app:
       build: .
       ports:
         - "8000:8000"
       env_file:
         - .env
       depends_on:
         - db
         - redis
       volumes:
         - ./logs:/var/log/uwsgi
       command: >
         sh -c "python manage.py migrate &&
                uwsgi --ini uwsgi.ini"

     db:
       image: postgres:15
       environment:
         POSTGRES_USER: ${DATABASE_URL#postgres://}
         POSTGRES_PASSWORD: ${DATABASE_URL#*://*:}
         POSTGRES_DB: billing_db
       volumes:
         - postgres_data:/var/lib/postgresql/data

     redis:
       image: redis:7
       ports:
         - "6379:6379"

   volumes:
     postgres_data:
   ```

3. **Build and Run**:
   ```bash
   mkdir -p logs
   docker-compose up --build
   ```

### Production Deployment

1. **Run uWSGI Behind Nginx**:
   - Install Nginx:
     ```bash
     sudo apt update
     sudo apt install nginx
     ```
   - Create an Nginx config file (e.g., `/etc/nginx/sites-available/billing`):
     ```nginx
     server {
         listen 80;
         server_name your-domain.com;

         location / {
             include uwsgi_params;
             uwsgi_pass 0.0.0.0:8000;
         }
     }
     ```
   - Enable and restart Nginx:
     ```bash
     sudo ln -s /etc/nginx/sites-available/billing /etc/nginx/sites-enabled
     sudo nginx -t
     sudo systemctl restart nginx
     ```

2. **Run uWSGI**:
   ```bash
   uwsgi --ini uwsgi.ini
   ```

3. **Systemd Service (Optional)**:
   - Create a systemd service file (e.g., `/etc/systemd/system/billing.service`):
     ```ini
     [Unit]
     Description=uWSGI instance to serve Billing Microservice
     After=network.target

     [Service]
     User=your-user
     Group=www-data
     WorkingDirectory=/path/to/billing_service
     ExecStart=/usr/local/bin/uwsgi --ini uwsgi.ini
     Restart=always

     [Install]
     WantedBy=multi-user.target
     ```
   - Enable and start:
     ```bash
     sudo systemctl enable billing
     sudo systemctl start billing
     ```
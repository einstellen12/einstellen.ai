# SaaS Einstellen Microservices

This repository contains a suite of Django-based microservices forming a SaaS platform for job recruitment and management. The services include Authentication, Candidate Profile, Job Listing & Application, Notification & Communication, Subscription & Billing, and AI Interview, each designed with single responsibility principles and multi-tenant support.

## Table of Contents
- [Overview](#overview)
- [Microservices](#microservices)
  - [Authentication Microservice](#authentication-microservice)
  - [Candidate Profile Microservice](#candidate-profile-microservice)
  - [Job Listing & Application Microservice](#job-listing--application-microservice)
  - [Notification & Communication Microservice](#notification--communication-microservice)
  - [Subscription & Billing Microservice](#subscription--billing-microservice)
  - [AI Interview Microservice](#ai-interview-microservice)
- [Setup](#setup)
- [Database Schemas](#database-schemas)
- [Overall Architecture](#overall-architecture)
- [Deployment](#deployment)

## Overview

This SaaS platform provides a comprehensive solution for job recruitment, candidate management, billing, and AI-driven interviews. Each microservice is independently deployable, communicates via HTTP or WebSockets, and uses PostgreSQL for persistent storage, with Redis for real-time features where applicable.

## Microservices

### Authentication Microservice

**Purpose**: Manages user authentication and authorization, issuing JWT tokens for secure access across services.

**Features**:
- User registration and login.
- JWT token generation and validation.
- Tenant management.

**Endpoints**:
- `POST /register/` - Register a user.
- `POST /login/` - Login and get JWT token.
- `GET /tenants/` - List tenants (admin only).

**Database**: PostgreSQL

### Candidate Profile Microservice

**Purpose**: Manages candidate profiles, including personal details, education, work experience, skills, and CV parsing.

**Features**:
- Profile creation and updates.
- CV upload and parsing.
- Education, work experience, skills, and certification management.

**Endpoints**:
- `POST /candidates/` - Create a candidate profile.
- `GET /candidates/{candidate_id}/` - Retrieve profile.
- `PUT /candidates/{candidate_id}/update/` - Update profile.
- `POST /candidates/{candidate_id}/upload-cv/` - Upload CV.
- `POST /candidates/{candidate_id}/{resource}/` - Add education, work experience, skills, certifications.
- `PUT /{resource}/{resource_id}/edit/` - Edit resources.

**Database**: PostgreSQL

### Job Listing & Application Microservice

**Purpose**: Handles job postings, candidate applications, and employer-candidate matching.

**Features**:
- Job posting (company, title, description, salary, etc.).
- Candidate job applications.
- Application Tracking System (ATS).
- Employer-candidate matching algorithm (TF-IDF).

**Endpoints**:
- `POST /companies/` - Create a company.
- `POST /jobs/` - Post a job.
- `GET /jobs/{job_id}/` - Retrieve job details.
- `GET /jobs/list/` - List jobs.
- `POST /jobs/{job_id}/apply/` - Apply for a job.
- `GET /applications/` - List applications.
- `PUT /applications/{application_id}/status/` - Update application status.
- `GET /jobs/{job_id}/matches/` - Get matching candidates.

**Database**: PostgreSQL (per tenant)

### Notification & Communication Microservice

**Purpose**: Manages notifications and communication between candidates and employers.

**Features**:
- Email and SMS notifications (SMTP, Twilio).
- In-app messaging.
- Interview reminders.
- WebSockets for real-time chat.

**Endpoints**:
- `POST /notifications/send/` - Send a notification.
- `GET /notifications/` - List notifications.
- `POST /messages/send/` - Send a message.
- `GET /messages/` - List messages.
- `POST /reminders/create/` - Create a reminder.
- `GET /reminders/` - List reminders.
- `WebSocket /ws/chat/{room_name}/` - Real-time chat.

**Database**: PostgreSQL + Redis

### Subscription & Billing Microservice

**Purpose**: Manages subscription plans and billing for tenants.

**Features**:
- Plans management (HumanLite, HumanAdv, HumanPro).
- Payment integration (Stripe, Razorpay, PayPal).
- SaaS-based billing with credit system.
- Auto-renewals and invoices.

**Endpoints**:
- `GET /plans/` - List plans.
- `POST /subscriptions/create/` - Create a subscription.
- `GET /subscriptions/{subscription_id}/` - Retrieve subscription.
- `POST /subscriptions/{subscription_id}/cancel/` - Cancel subscription.
- `POST /subscriptions/{subscription_id}/consume-credits/` - Consume credits.
- `GET /invoices/` - List invoices.
- `POST /invoices/{invoice_id}/pay/` - Pay an invoice.
- `POST /webhook/stripe/` - Handle Stripe webhook.

**Database**: PostgreSQL

### AI Interview Microservice

**Purpose**: Conducts AI-driven interviews with video conferencing, question generation, and scoring.

**Features**:
- WebRTC-based video conferencing.
- Real-time coding collaboration via WebSockets.
- AI question generation based on resume and JD (Azure or local models).
- Transcription with Faster Whisper for follow-up questions.
- Scoring and feedback reports.
- Integration with Subscription & Billing for credit usage.

**Endpoints**:
- `POST /interviews/start/` - Start an interview (consumes credits).
- `POST /interviews/{interview_id}/end/` - End an interview and generate feedback.
- `WebSocket /ws/interview/{interview_id}/` - Video and coding session.

**Database**: PostgreSQL + Redis

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis
- uWSGI
- Docker (optional)
- Accounts with Stripe, Razorpay, PayPal, Twilio, Azure (optional for AI models)
- Additional dependencies: `faster-whisper`, `aiortc` (for AI Interview)

### General Installation

For each microservice:
1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <service-name>_service
   ```
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Set Environment Variables**:
   Create a `.env` file (see each service’s section below).
4. **Run Migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
5. **Test Locally**:
   ```bash
   python manage.py runserver
   ```

#### Authentication Microservice
- **.env**:
  ```
  SECRET_KEY=your-secret-key
  DATABASE_URL=postgres://user:password@localhost:5432/auth_db
  JWT_SECRET=your-jwt-secret
  JWT_EXPIRY=3600
  ```

#### Candidate Profile Microservice
- **.env**:
  ```
  SECRET_KEY=your-secret-key
  DATABASE_URL=postgres://user:password@localhost:5432/candidate_db
  JWT_SECRET=your-jwt-secret
  ```

#### Job Listing & Application Microservice
- **.env**:
  ```
  SECRET_KEY=your-secret-key
  DATABASE_URL=postgres://user:password@localhost:5432/job_db
  JWT_SECRET=your-jwt-secret
  ```

#### Notification & Communication Microservice
- **.env**:
  ```
  SECRET_KEY=your-secret-key
  DATABASE_URL=postgres://user:password@localhost:5432/notification_db
  REDIS_URL=redis://localhost:6379/0
  TWILIO_ACCOUNT_SID=your-twilio-sid
  TWILIO_AUTH_TOKEN=your-twilio-token
  EMAIL_HOST=smtp.example.com
  EMAIL_PORT=587
  EMAIL_HOST_USER=your-email
  EMAIL_HOST_PASSWORD=your-email-password
  ```

#### Subscription & Billing Microservice
- **.env**:
  ```
  SECRET_KEY=your-secret-key
  DATABASE_URL=postgres://user:password@localhost:5432/billing_db
  JWT_SECRET=your-jwt-secret
  STRIPE_SECRET_KEY=your-stripe-secret-key
  STRIPE_WEBHOOK_SECRET=your-stripe-webhook-secret
  RAZORPAY_KEY_ID=your-razorpay-key-id
  RAZORPAY_KEY_SECRET=your-razorpay-key-secret
  PAYPAL_MODE=sandbox
  PAYPAL_CLIENT_ID=your-paypal-client-id
  PAYPAL_CLIENT_SECRET=your-paypal-client-secret
  PAYPAL_RETURN_URL=http://localhost:8000/return
  PAYPAL_CANCEL_URL=http://localhost:8000/cancel
  ```
- Seed plans:
  ```python
  from billing.models import Plan
  Plan.objects.bulk_create([
      Plan(name='HumanLite', description='Basic plan', price=10.00, credits=5),
      Plan(name='HumanAdv', description='Advanced plan', price=20.00, credits=10),
      Plan(name='HumanPro', description='Pro plan', price=30.00, credits=20)
  ])
  ```

#### AI Interview Microservice
- **.env**:
  ```
  SECRET_KEY=your-secret-key
  DATABASE_URL=postgres://user:password@localhost:5432/interview_db
  REDIS_URL=redis://localhost:6379/0
  JWT_SECRET=your-jwt-secret
  AZURE_QUESTION_ENDPOINT=https://your-azure-endpoint/question
  AZURE_SCORING_ENDPOINT=https://your-azure-endpoint/score
  AZURE_API_KEY=your-azure-api-key
  LOCAL_MODEL_DIR=/path/to/models
  RESUME_SERVICE_URL=http://candidate-service
  JOB_SERVICE_URL=http://job-service
  BILLING_SERVICE_URL=http://billing-service
  ```
- **Dependencies**: Ensure `faster-whisper` and `aiortc` are in `requirements.txt`.

## Database Schemas

### Authentication Microservice
```mermaid
erDiagram
    User ||--o{ Tenant : owns
    User ||--o{ AuditLog : logs

    User {
        UUID id PK
        VARCHAR email
        VARCHAR password_hash
        TIMESTAMP created_at
    }

    Tenant {
        UUID id PK
        UUID user_id FK
        VARCHAR name
        TIMESTAMP created_at
    }

    AuditLog {
        UUID id PK
        UUID user_id FK
        VARCHAR action
        VARCHAR ip_address
        VARCHAR tenant
        JSON details
        TIMESTAMP timestamp
    }
```

### Candidate Profile Microservice
```mermaid
erDiagram
    Candidate ||--o{ Education : has
    Candidate ||--o{ WorkExperience : has
    Candidate ||--o{ Skill : has
    Candidate ||--o{ Certification : has
    Candidate ||--o{ AuditLog : logs

    Candidate {
        UUID id PK
        UUID user_id FK
        VARCHAR first_name
        VARCHAR last_name
        DATE dob
        VARCHAR phone
        VARCHAR location
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    Education {
        UUID id PK
        UUID candidate_id FK
        VARCHAR degree
        VARCHAR university
        INT start_year
        INT end_year
    }

    WorkExperience {
        UUID id PK
        UUID candidate_id FK
        VARCHAR company_name
        VARCHAR job_title
        DATE start_date
        DATE end_date
    }

    Skill {
        UUID id PK
        UUID candidate_id FK
        VARCHAR skill_name
    }

    Certification {
        UUID id PK
        UUID candidate_id FK
        VARCHAR title
        VARCHAR issued_by
        DATE issue_date
    }

    AuditLog {
        UUID id PK
        UUID user_id FK
        VARCHAR action
        VARCHAR ip_address
        VARCHAR tenant
        JSON details
        TIMESTAMP timestamp
    }
```

### Job Listing & Application Microservice
```mermaid
erDiagram
    Company ||--o{ Job : posts
    Job ||--o{ Application : receives
    Company ||--o{ AuditLog : logs

    Company {
        UUID id PK
        VARCHAR name
        UUID tenant_id FK
        TIMESTAMP created_at
    }

    Job {
        UUID id PK
        UUID company_id FK
        VARCHAR title
        TEXT description
        VARCHAR location
        VARCHAR salary_range
        JSON key_skills
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    Application {
        UUID id PK
        UUID job_id FK
        UUID candidate_id FK
        VARCHAR status
        TIMESTAMP applied_at
        TIMESTAMP updated_at
        FLOAT match_score
    }

    AuditLog {
        UUID id PK
        UUID user_id FK
        VARCHAR action
        VARCHAR ip_address
        VARCHAR tenant
        JSON details
        TIMESTAMP timestamp
    }
```

### Notification & Communication Microservice
```mermaid
erDiagram
    Notification ||--o{ AuditLog : logs
    Message ||--o{ AuditLog : logs
    InterviewReminder ||--o{ AuditLog : logs

    Notification {
        UUID id PK
        UUID user_id FK
        UUID tenant_id FK
        VARCHAR notification_type
        VARCHAR subject
        TEXT message
        VARCHAR recipient
        TIMESTAMP sent_at
        BOOLEAN is_sent
        TIMESTAMP created_at
    }

    Message {
        UUID id PK
        UUID sender_id FK
        UUID receiver_id FK
        UUID tenant_id FK
        TEXT content
        TIMESTAMP sent_at
        BOOLEAN is_read
    }

    InterviewReminder {
        UUID id PK
        UUID application_id FK
        UUID tenant_id FK
        UUID candidate_id FK
        UUID employer_id FK
        TIMESTAMP interview_time
        TIMESTAMP reminder_time
        BOOLEAN is_sent
        TIMESTAMP created_at
    }

    AuditLog {
        UUID id PK
        UUID user_id FK
        VARCHAR action
        VARCHAR ip_address
        VARCHAR tenant
        JSON details
        TIMESTAMP timestamp
    }
```

### Subscription & Billing Microservice
```mermaid
erDiagram
    Plan ||--o{ Subscription : offers
    Subscription ||--o{ Invoice : generates
    Subscription ||--o{ CreditUsage : tracks
    Subscription ||--o{ AuditLog : logs

    Plan {
        UUID id PK
        VARCHAR name
        TEXT description
        DECIMAL price
        INT credits
        VARCHAR billing_cycle
        TIMESTAMP created_at
    }

    Subscription {
        UUID id PK
        UUID tenant_id FK
        UUID plan_id FK
        VARCHAR payment_method
        VARCHAR payment_id
        VARCHAR status
        TIMESTAMP start_date
        TIMESTAMP end_date
        BOOLEAN auto_renew
        INT remaining_credits
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    Invoice {
        UUID id PK
        UUID subscription_id FK
        DECIMAL amount
        VARCHAR status
        TIMESTAMP invoice_date
        TIMESTAMP due_date
        VARCHAR payment_id
        TIMESTAMP created_at
    }

    CreditUsage {
        UUID id PK
        UUID subscription_id FK
        INT amount
        VARCHAR reason
        TIMESTAMP used_at
    }

    AuditLog {
        UUID id PK
        UUID user_id FK
        VARCHAR action
        VARCHAR ip_address
        VARCHAR tenant
        JSON details
        TIMESTAMP timestamp
    }
```

### AI Interview Microservice
```mermaid
erDiagram
    Interview ||--o{ Transcript : generates
    Interview ||--o{ QuestionAnswer : contains
    Interview ||--o{ FeedbackReport : produces
    Interview ||--o{ AuditLog : logs

    Interview {
        UUID id PK
        UUID tenant_id FK
        UUID subscription_id FK
        UUID candidate_id FK
        VARCHAR status
        TIMESTAMP start_time
        TIMESTAMP end_time
        TEXT resume
        TEXT job_description
        TIMESTAMP created_at
    }

    Transcript {
        UUID id PK
        UUID interview_id FK
        TEXT text
        TIMESTAMP timestamp
    }

    QuestionAnswer {
        UUID id PK
        UUID interview_id FK
        TEXT question
        TEXT answer
        TEXT code
        BOOLEAN is_deviated
        FLOAT score
        TIMESTAMP asked_at
    }

    FeedbackReport {
        UUID id PK
        UUID interview_id FK
        FLOAT overall_score
        JSON detailed_scores
        TEXT comments
        TIMESTAMP generated_at
    }

    AuditLog {
        UUID id PK
        UUID user_id FK
        VARCHAR action
        VARCHAR ip_address
        VARCHAR tenant
        JSON details
        TIMESTAMP timestamp
    }
```

## Overall Architecture

```mermaid
graph TD
    A[Client] -->|HTTP/WebSocket| B[API Gateway]
    B -->|JWT Validation| C[Auth Service]
    B -->|Routes Requests| D[Candidate Profile Service]
    B -->|Routes Requests| E[Job Listing & Application Service]
    B -->|Routes Requests| F[Notification & Communication Service]
    B -->|Routes Requests| G[Subscription & Billing Service]
    B -->|Routes Requests| H[AI Interview Service]

    C -->|Stores Data| I[PostgreSQL Auth]
    D -->|Stores Data| J[PostgreSQL Candidate]
    E -->|Stores Data| K[PostgreSQL Job]
    F -->|Stores Data| L[PostgreSQL Notification]
    F -->|Real-Time| M[Redis]
    G -->|Stores Data| N[PostgreSQL Billing]
    G -->|Caching| O[Redis]
    H -->|Stores Data| P[PostgreSQL Interview]
    H -->|Real-Time| Q[Redis]

    D -->|Logs Errors| R[Email Service]
    E -->|Logs Errors| R
    F -->|Logs Errors| R
    G -->|Logs Errors| R
    H -->|Logs Errors| R

    F -->|SMS| S[Twilio]
    G -->|Payments| T[Stripe]
    G -->|Payments| U[Razorpay]
    G -->|Payments| V[PayPal]
    T -->|Webhook| G

    H -->|Fetches Resume| D
    H -->|Fetches JD| E
    H -->|Consumes Credits| G

    C -->|JWT Token| A
```

- **Client**: Interacts with the platform via HTTP or WebSocket.
- **API Gateway**: Routes requests and validates JWT tokens.
- **Auth Service**: Issues JWT tokens.
- **Candidate Profile Service**: Manages candidate data, provides resumes to AI Interview.
- **Job Listing & Application Service**: Handles job postings, provides JDs to AI Interview.
- **Notification & Communication Service**: Manages notifications and real-time chat.
- **Subscription & Billing Service**: Manages billing and credits, used by AI Interview.
- **AI Interview Service**: Conducts AI-driven interviews with video and coding.
- **PostgreSQL**: Persistent storage per service.
- **Redis**: Real-time features (chat, WebRTC signaling) and caching.
- **Email Service**: Error logging.
- **Twilio/Stripe/Razorpay/PayPal**: External integrations.
- **Service Interactions**: AI Interview fetches resumes and JDs, consumes credits from Billing.

## Deployment

### uWSGI Configuration (Generic)
For each service, create `uwsgi.ini`:
```ini
[uwsgi]
module = <service_name>_service.wsgi:application
master = true
processes = 4
threads = 2
socket = 0.0.0.0:8000
chmod-socket = 666
vacuum = true
die-on-term = true
logto = /var/log/uwsgi/<service_name>.log
```

### Docker Deployment
Each service has a `Dockerfile` and `docker-compose.yml`. Example for any service (adjust for AI Interview WebSocket):
- **Dockerfile**:
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  ENV PYTHONUNBUFFERED=1
  CMD ["uwsgi", "--ini", "uwsgi.ini"]
  ```
- **docker-compose.yml** (example for AI Interview):
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
        sh -c "python manage.py migrate && uwsgi --ini uwsgi.ini"
    db:
      image: postgres:15
      environment:
        POSTGRES_USER: ${DATABASE_URL#postgres://}
        POSTGRES_PASSWORD: ${DATABASE_URL#*://*:}
        POSTGRES_DB: interview_db
      volumes:
        - postgres_data:/var/lib/postgresql/data
    redis:
      image: redis:7
      ports:
        - "6379:6379"
  volumes:
    postgres_data:
  ```

- **Build and Run**:
  ```bash
  mkdir -p logs
  docker-compose up --build
  ```

### Production Deployment
1. **Nginx Reverse Proxy**:
   - Config (`/etc/nginx/sites-available/<service_name>`):
     ```nginx
     server {
         listen 80;
         server_name <service_name>.your-domain.com;
         location / {
             include uwsgi_params;
             uwsgi_pass 0.0.0.0:8000;
         }
         location /ws/ { 
             proxy_pass http://0.0.0.0:8000;
             proxy_http_version 1.1;
             proxy_set_header Upgrade $http_upgrade;
             proxy_set_header Connection "upgrade";
             proxy_set_header Host $host;
             proxy_set_header X-Real-IP $remote_addr;
             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
             proxy_set_header X-Forwarded-Proto $scheme;
         }
     }
     ```
   - Enable and restart:
     ```bash
     sudo ln -s /etc/nginx/sites-available/<service_name> /etc/nginx/sites-enabled
     sudo nginx -t
     sudo systemctl restart nginx
     ```

2. **Systemd Service**:
   - File (`/etc/systemd/system/<service_name>.service`):
     ```ini
     [Unit]
     Description=uWSGI instance to serve <Service Name> Microservice
     After=network.target
     [Service]
     User=your-user
     Group=www-data
     WorkingDirectory=/path/to/<service_name>_service
     ExecStart=/usr/local/bin/uwsgi --ini uwsgi.ini
     Restart=always
     [Install]
     WantedBy=multi-user.target
     ```
   - Enable and start:
     ```bash
     sudo systemctl enable <service_name>
     sudo systemctl start <service_name>
     ```
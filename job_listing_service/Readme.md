# Job Listing & Application Microservice

This is a Django-based microservice for managing job listings and candidate applications. It supports multi-tenancy with a PostgreSQL database per SaaS tenant and includes features like job postings, application tracking, and employer-candidate matching.

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

The Job Listing & Application Microservice is part of a SaaS platform, designed to handle job postings by companies, applications from candidates, and tracking of application statuses. It integrates with an Authentication Service for JWT-based security and the Candidate Profile Service for candidate data in matching algorithms.

## Features

- Job postings with company details, title, description, salary, and key skills.
- Candidate applications with automatic match score calculation.
- Application Tracking System (ATS) to manage application statuses (e.g., applied, shortlisted, rejected).
- Employer-candidate matching algorithm using TF-IDF and cosine similarity.
- Multi-tenant support with PostgreSQL databases scoped by tenant.

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis
- uWSGI
- Docker (optional for deployment)

### Installation

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd job_listing_service
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
   scikit-learn==1.3.2
   ```

3. **Set Environment Variables**:
   Create a `.env` file in the root directory:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=False
   DATABASE_URL=postgres://user:password@localhost:5432/job_listing_db
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
   ```

4. **Run Migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Test Locally**:
   ```bash
   python manage.py runserver
   ```

## Database Schema

The microservice uses PostgreSQL with the following schema, scoped per tenant:

```mermaid
erDiagram
    Company ||--o{ Job : posts
    Job ||--o{ Application : receives
    Company ||--o{ AuditLog : logs

    Company {
        UUID id PK
        VARCHAR name
        UUID tenant_id FK "From Auth Service"
        TIMESTAMP created_at
    }

    Job {
        UUID id PK
        UUID company_id FK
        VARCHAR title
        TEXT description
        VARCHAR location
        VARCHAR salary_range
        JSON key_skills "e.g., ['Python', 'Django']"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    Application {
        UUID id PK
        UUID job_id FK
        UUID candidate_id FK "From Candidate Profile Service"
        VARCHAR status "e.g., 'applied', 'shortlisted'"
        TIMESTAMP applied_at
        TIMESTAMP updated_at
        FLOAT match_score
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

The architecture shows how the Job Listing & Application Microservice interacts with other components:

```mermaid
graph TD
    A[Client] -->|HTTP Requests| B[API Gateway]
    B -->|JWT Validation| C[Auth Service]
    B -->|Routes Requests| D[Job Listing & Application Microservice]
    D -->|Stores Data| E[PostgreSQL]
    D -->|Caches Data| F[Redis]
    D -->|Logs Errors| G[Email Service]
    D -->|Audit Logs| E
    D -->|Fetches Candidate Profiles| H[Candidate Profile Service]

    subgraph Job Listing & Application Microservice
        D1[Views]
        D2[Matching Algorithm]
        D3[Middleware]
        D1 --> D2
        D1 --> D3
    end

    C -->|JWT Token| A
```

- **Client**: Sends HTTP requests to the API Gateway.
- **API Gateway**: Routes requests and validates JWT tokens with the Auth Service.
- **Auth Service**: Provides JWT tokens for authentication.
- **Job Listing & Application Microservice**: Manages jobs and applications.
- **PostgreSQL**: Stores job and application data per tenant.
- **Redis**: Used for caching (optional).
- **Email Service**: Receives error logs.
- **Candidate Profile Service**: Provides candidate data for matching.

## API Endpoints

| **Endpoint**                          | **Method** | **Description**                          | **Request Body**                              | **Response**                              |
|---------------------------------------|------------|------------------------------------------|-----------------------------------------------|-------------------------------------------|
| `/companies/`                         | POST       | Create a new company                     | `{name}`                                      | `{company_id}`                            |
| `/jobs/`                              | POST       | Post a new job                           | `{company_id, title, description, location, salary_range, key_skills}` | `{job_id}`                            |
| `/jobs/{job_id}/`                     | GET        | Retrieve job details                     | -                                             | `{job_details}`                           |
| `/jobs/list/`                         | GET        | List all jobs for tenant                 | -                                             | `[{job_list}]`                            |
| `/jobs/{job_id}/apply/`               | POST       | Apply for a job                          | -                                             | `{application_id, match_score}`           |
| `/applications/`                      | GET        | List all applications for tenant         | -                                             | `[{application_list}]`                    |
| `/applications/{application_id}/status/` | PUT     | Update application status                | `{status}`                                    | `{message}`                               |
| `/jobs/{job_id}/matches/`             | GET        | Get matching candidates for a job        | -                                             | `[{candidate_id, match_score}]`           |

**Authentication**: All endpoints require a `Bearer {{jwt_token}}` header.

## Usage

1. **Create a Company**:
   ```bash
   curl -X POST {{base_url}}/companies/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"name": "Tech Corp"}'
   ```

2. **Create a Job**:
   ```bash
   curl -X POST {{base_url}}/jobs/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"company_id": "{{company_id}}", "title": "Software Engineer", "description": "Develop software solutions.", "location": "Remote", "salary_range": "$80,000 - $120,000", "key_skills": ["Python", "Django"]}'
   ```

3. **Apply for a Job**:
   ```bash
   curl -X POST {{base_url}}/jobs/{{job_id}}/apply/ \
   -H "Authorization: Bearer {{jwt_token}}"
   ```

4. **Update Application Status**:
   ```bash
   curl -X PUT {{base_url}}/applications/{{application_id}}/status/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"status": "shortlisted"}'
   ```

5. **Get Matching Candidates**:
   ```bash
   curl -X GET {{base_url}}/jobs/{{job_id}}/matches/ \
   -H "Authorization: Bearer {{jwt_token}}"
   ```

## Deployment

### uWSGI Configuration

1. **Create a uWSGI Configuration File**:
   Create `uwsgi.ini` in the project root:
   ```ini
   [uwsgi]
   module = job_listing_service.wsgi:application
   master = true
   processes = 4
   threads = 2
   socket = 0.0.0.0:8000
   chmod-socket = 666
   vacuum = true
   die-on-term = true
   logto = /var/log/uwsgi/job_listing.log
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
         POSTGRES_DB: job_listing_db
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
   - Create an Nginx config file (e.g., `/etc/nginx/sites-available/job_listing`):
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
     sudo ln -s /etc/nginx/sites-available/job_listing /etc/nginx/sites-enabled
     sudo nginx -t
     sudo systemctl restart nginx
     ```

2. **Run uWSGI**:
   ```bash
   uwsgi --ini uwsgi.ini
   ```

3. **Systemd Service (Optional)**:
   - Create a systemd service file (e.g., `/etc/systemd/system/job_listing.service`):
     ```ini
     [Unit]
     Description=uWSGI instance to serve Job Listing Microservice
     After=network.target

     [Service]
     User=your-user
     Group=www-data
     WorkingDirectory=/path/to/job_listing_service
     ExecStart=/usr/local/bin/uwsgi --ini uwsgi.ini
     Restart=always

     [Install]
     WantedBy=multi-user.target
     ```
   - Enable and start:
     ```bash
     sudo systemctl enable job_listing
     sudo systemctl start job_listing
     ```
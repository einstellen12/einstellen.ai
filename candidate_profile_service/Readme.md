# Candidate Profile Microservice

This is a Django-based microservice for managing candidate profiles, including creating profiles, uploading and parsing CVs, and editing profile details. It follows a microservices architecture and uses PostgreSQL as its database.

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

The Candidate Profile Microservice is part of a larger SaaS platform, designed to handle candidate-related data such as personal information, education, work experience, skills, and certifications. It integrates with an Authentication Service via JWT tokens and supports CV parsing to automatically populate profile data.

## Features

- Create and retrieve candidate profiles.
- Upload CVs in PDF format and parse them to extract data (personal info, skills, experience, education, certifications).
- Add and edit profile details (education, work experience, skills, certifications).
- Secure access with JWT authentication.
- Audit logging for all operations.
- Error logging with email notifications for critical issues.

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
   cd candidate_profile_service
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm  # Fallback NLP model
   ```

   Update `requirements.txt` to include uWSGI:
   ```
   uwsgi==2.0.23
   ```

3. **Set Environment Variables**:
   Create a `.env` file in the root directory:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=False
   DATABASE_URL=postgres://user:password@localhost:5432/candidate_profile_db
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

The microservice uses PostgreSQL with the following schema:

```mermaid
erDiagram
    Candidate ||--o{ Education : has
    Candidate ||--o{ WorkExperience : has
    Candidate ||--o{ Skill : has
    Candidate ||--o{ Certification : has
    Candidate ||--o{ AuditLog : logs

    Candidate {
        UUID id PK
        UUID user_id FK "Unique, from Auth Service"
        VARCHAR first_name
        VARCHAR last_name
        DATE dob
        VARCHAR gender
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
        UUID user_id FK "Nullable"
        VARCHAR action
        VARCHAR ip_address
        VARCHAR tenant
        JSON details
        TIMESTAMP timestamp
    }
```

## Microservice Architecture

The architecture shows how the Candidate Profile Microservice interacts with other components:

```mermaid
graph TD
    A[Client] -->|HTTP Requests| B[API Gateway]
    B -->|JWT Validation| C[Auth Service]
    B -->|Routes Requests| D[Candidate Profile Microservice]
    D -->|Stores Data| E[PostgreSQL]
    D -->|Caches Data| F[Redis]
    D -->|Logs Errors| G[Email Service]
    D -->|Audit Logs| E

    subgraph Candidate Profile Microservice
        D1[Views]
        D2[Resume Parser]
        D3[Middleware]
        D1 --> D2
        D1 --> D3
    end

    C -->|JWT Token| A
```

- **Client**: Sends HTTP requests to the API Gateway.
- **API Gateway**: Routes requests and validates JWT tokens with the Auth Service.
- **Auth Service**: Provides JWT tokens for authentication.
- **Candidate Profile Microservice**: Handles profile operations and CV parsing.
- **PostgreSQL**: Stores candidate data and audit logs.
- **Redis**: Used for caching (optional).
- **Email Service**: Receives error logs.

## API Endpoints

| **Endpoint**                              | **Method** | **Description**                          | **Request Body**                              | **Response**                          |
|-------------------------------------------|------------|------------------------------------------|-----------------------------------------------|---------------------------------------|
| `/candidates/`                            | POST       | Create a new candidate profile           | `{first_name, last_name, dob, phone, location}` | `{candidate_id}`                     |
| `/candidates/{candidate_id}/`             | GET        | Retrieve candidate profile               | -                                             | `{candidate_details}`                |
| `/candidates/{candidate_id}/update/`      | PUT        | Update candidate profile                 | `{updated_data}`                              | `{message}`                          |
| `/candidates/{candidate_id}/upload-cv/`   | POST       | Upload and parse CV                      | Form-data: `{cv, job_role, job_description, key_skills}` | `{message, file_path, parsed_data}` |
| `/candidates/{candidate_id}/education/`   | POST       | Add education                            | `{degree, university, start_year, end_year}`  | `{education_id}`                    |
| `/candidates/{candidate_id}/work-experience/` | POST   | Add work experience                      | `{company_name, job_title, start_date, end_date}` | `{work_experience_id}`             |
| `/candidates/{candidate_id}/skills/`      | POST       | Add skill                                | `{skill_name}`                                | `{skill_id}`                        |
| `/candidates/{candidate_id}/certifications/` | POST    | Add certification                        | `{title, issued_by, issue_date}`              | `{certification_id}`                |
| `/candidates/{candidate_id}/edit-personal/` | PUT      | Edit personal info                       | `{first_name, last_name, phone, location}`    | `{message}`                         |
| `/education/{education_id}/edit/`         | PUT        | Edit education                           | `{degree, university, start_year, end_year}`  | `{message}`                         |
| `/work-experience/{work_experience_id}/edit/` | PUT    | Edit work experience                     | `{company_name, job_title, start_date, end_date}` | `{message}`                     |
| `/skills/{skill_id}/edit/`                | PUT        | Edit skill                               | `{skill_name}`                                | `{message}`                         |
| `/certifications/{certification_id}/edit/` | PUT       | Edit certification                       | `{title, issued_by, issue_date}`              | `{message}`                         |

**Authentication**: All endpoints require a `Bearer {{jwt_token}}` header.

## Usage

1. **Create a Profile**:
   ```bash
   curl -X POST {{base_url}}/candidates/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"first_name": "John", "last_name": "Doe", "phone": "7568992589"}'
   ```

2. **Upload a CV**:
   ```bash
   curl -X POST {{base_url}}/candidates/{{candidate_id}}/upload-cv/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -F "cv=@resume.pdf" \
   -F "job_role=Software Engineer" \
   -F "job_description=Develop software solutions" \
   -F "key_skills=[\"Python\", \"Django\"]"
   ```

3. **Edit Personal Info**:
   ```bash
   curl -X PUT {{base_url}}/candidates/{{candidate_id}}/edit-personal/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"phone": "+1987654321"}'
   ```

## Deployment

### uWSGI Configuration

1. **Create a uWSGI Configuration File**:
   Create `uwsgi.ini` in the project root:
   ```ini
   [uwsgi]
   module = candidate_profile_service.wsgi:application
   master = true
   processes = 4
   threads = 2
   socket = 0.0.0.0:8000
   chmod-socket = 666
   vacuum = true
   die-on-term = true
   logto = /var/log/uwsgi/candidate_profile.log
   ```

2. **Run uWSGI Locally**:
   ```bash
   uwsgi --ini uwsgi.ini
   ```

### Docker Deployment with uWSGI

1. **Update Dockerfile**:
   Replace the Gunicorn command with uWSGI:
   ```dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY . .

   ENV PYTHONUNBUFFERED=1

   CMD ["uwsgi", "--ini", "uwsgi.ini"]
   ```

2. **Update docker-compose.yml**:
   Ensure the uWSGI logs directory exists:
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
         POSTGRES_DB: candidate_profile_db
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
   mkdir -p logs  # Create logs directory for uWSGI
   docker-compose up --build
   ```

### Production Deployment

1. **Run uWSGI Behind Nginx**:
   - Install Nginx on your server:
     ```bash
     sudo apt update
     sudo apt install nginx
     ```
   - Create an Nginx configuration file (e.g., `/etc/nginx/sites-available/candidate_profile`):
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
   - Enable the site and restart Nginx:
     ```bash
     sudo ln -s /etc/nginx/sites-available/candidate_profile /etc/nginx/sites-enabled
     sudo nginx -t
     sudo systemctl restart nginx
     ```

2. **Run uWSGI**:
   ```bash
   uwsgi --ini uwsgi.ini
   ```

3. **Systemd Service (Optional)**:
   - Create a systemd service file (e.g., `/etc/systemd/system/candidate_profile.service`):
     ```ini
     [Unit]
     Description=uWSGI instance to serve Candidate Profile Microservice
     After=network.target

     [Service]
     User=your-user
     Group=www-data
     WorkingDirectory=/path/to/candidate_profile_service
     ExecStart=/usr/local/bin/uwsgi --ini uwsgi.ini
     Restart=always

     [Install]
     WantedBy=multi-user.target
     ```
   - Enable and start the service:
     ```bash
     sudo systemctl enable candidate_profile
     sudo systemctl start candidate_profile
     ```
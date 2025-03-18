# Notification & Communication Microservice

This is a Django-based microservice for managing notifications and communication within a SaaS platform. It supports email and SMS notifications, in-app messaging, interview reminders, and real-time chat via WebSockets, using Redis for real-time features and PostgreSQL for persistent storage.

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

The Notification & Communication Microservice facilitates communication between candidates and employers, delivering notifications (email/SMS), managing in-app messages, scheduling interview reminders, and enabling real-time chat. It integrates with an Authentication Service for JWT-based security and uses Redis for WebSocket and reminder scheduling.

## Features

- Email and SMS notifications using SMTP and Twilio.
- In-app messaging between candidates and employers.
- Interview reminders scheduled via Redis.
- Real-time chat using WebSockets with Django Channels.
- Multi-tenant support with PostgreSQL and Redis.

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis
- uWSGI
- Docker (optional for deployment)
- Twilio account (for SMS)

### Installation

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd notification_service
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
   channels==4.0.0
   channels-redis==4.1.0
   twilio==8.10.0
   ```

3. **Set Environment Variables**:
   Create a `.env` file in the root directory:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=False
   DATABASE_URL=postgres://user:password@localhost:5432/notification_db
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
   TWILIO_ACCOUNT_SID=your-twilio-account-sid
   TWILIO_AUTH_TOKEN=your-twilio-auth-token
   TWILIO_PHONE=7568992589
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

The microservice uses PostgreSQL for persistent storage and Redis for real-time data, with the following schema:

```mermaid
erDiagram
    Notification ||--o{ AuditLog : logs
    Message ||--o{ AuditLog : logs
    InterviewReminder ||--o{ AuditLog : logs

    Notification {
        UUID id PK
        UUID user_id FK "From Auth Service"
        UUID tenant_id FK "From Auth Service"
        VARCHAR notification_type "email, sms, in_app"
        VARCHAR subject
        TEXT message
        VARCHAR recipient "Email or phone"
        TIMESTAMP sent_at
        BOOLEAN is_sent
        TIMESTAMP created_at
    }

    Message {
        UUID id PK
        UUID sender_id FK "From Auth Service"
        UUID receiver_id FK "From Auth Service"
        UUID tenant_id FK "From Auth Service"
        TEXT content
        TIMESTAMP sent_at
        BOOLEAN is_read
    }

    InterviewReminder {
        UUID id PK
        UUID application_id FK "From Job Listing Service"
        UUID tenant_id FK "From Auth Service"
        UUID candidate_id FK "From Candidate Profile Service"
        UUID employer_id FK "From Auth Service"
        TIMESTAMP interview_time
        TIMESTAMP reminder_time
        BOOLEAN is_sent
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

- **Redis**: Used for WebSocket channel layer and scheduling reminders (e.g., `reminder_{id}` keys with TTL).

## Microservice Architecture

The architecture shows how the Notification & Communication Microservice interacts with other components:

```mermaid
graph TD
    A[Client] -->|HTTP/WebSocket Requests| B[API Gateway]
    B -->|JWT Validation| C[Auth Service]
    B -->|Routes Requests| D[Notification & Communication Microservice]
    D -->|Stores Persistent Data| E[PostgreSQL]
    D -->|Real-Time Messaging & Reminders| F[Redis]
    D -->|Logs Errors| G[Email Service]
    D -->|Audit Logs| E
    D -->|SMS Notifications| H[Twilio]

    subgraph Notification & Communication Microservice
        D1[Views]
        D2[Consumers WebSockets]
        D3[Middleware]
        D1 --> D2
        D1 --> D3
    end

    C -->|JWT Token| A
```

- **Client**: Sends HTTP requests or WebSocket connections to the API Gateway.
- **API Gateway**: Routes requests and validates JWT tokens with the Auth Service.
- **Auth Service**: Provides JWT tokens for authentication.
- **Notification & Communication Microservice**: Manages notifications, messages, and reminders.
- **PostgreSQL**: Stores persistent data (notifications, messages, reminders).
- **Redis**: Handles real-time messaging and reminder scheduling.
- **Email Service**: Receives error logs and sends email notifications.
- **Twilio**: Sends SMS notifications.

## API Endpoints

| **Endpoint**             | **Method** | **Description**                          | **Request Body**                              | **Response**                              |
|--------------------------|------------|------------------------------------------|-----------------------------------------------|-------------------------------------------|
| `/notifications/send/`   | POST       | Send a notification (email/SMS/in-app)   | `{notification_type, subject, message, recipient}` | `{notification_id}`                      |
| `/notifications/`        | GET        | List user notifications                  | -                                             | `[{notification_list}]`                   |
| `/messages/send/`        | POST       | Send an in-app message                   | `{receiver_id, content}`                      | `{message_id}`                            |
| `/messages/`             | GET        | List user messages                       | -                                             | `[{message_list}]`                        |
| `/reminders/create/`     | POST       | Create an interview reminder             | `{application_id, candidate_id, employer_id, interview_time, reminder_time}` | `{reminder_id}` |
| `/reminders/`            | GET        | List user reminders                      | -                                             | `[{reminder_list}]`                       |
| `/ws/chat/{room_name}/`  | WebSocket  | Real-time chat                           | `{message, receiver_id}` (JSON)               | `{message, sender_id, sent_at}` (JSON)    |

**Authentication**: All endpoints require a `Bearer {{jwt_token}}` header.

## Usage

1. **Send an Email Notification**:
   ```bash
   curl -X POST {{base_url}}/notifications/send/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"notification_type": "email", "subject": "Interview Scheduled", "message": "Your interview is tomorrow at 10 AM.", "recipient": "candidate@example.com"}'
   ```

2. **Send an SMS Notification**:
   ```bash
   curl -X POST {{base_url}}/notifications/send/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"notification_type": "sms", "message": "Interview tomorrow at 10 AM.", "recipient": "7568992589"}'
   ```

3. **Send a Message**:
   ```bash
   curl -X POST {{base_url}}/messages/send/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"receiver_id": "{{receiver_id}}", "content": "Hello, how are you?"}'
   ```

4. **Create an Interview Reminder**:
   ```bash
   curl -X POST {{base_url}}/reminders/create/ \
   -H "Authorization: Bearer {{jwt_token}}" \
   -H "Content-Type: application/json" \
   -d '{"application_id": "{{application_id}}", "candidate_id": "{{candidate_id}}", "employer_id": "{{employer_id}}", "interview_time": "2025-03-10T10:00:00Z", "reminder_time": "2025-03-10T09:00:00Z"}'
   ```

5. **WebSocket Chat**:
   - Connect using a WebSocket client (e.g., `wscat`):
     ```bash
     wscat -c ws://localhost:8000/ws/chat/{{room_name}}/ -H "Authorization: Bearer {{jwt_token}}"
     ```
   - Send: `{"message": "Hi!", "receiver_id": "{{receiver_id}}"}`

## Deployment

### uWSGI Configuration

1. **Create a uWSGI Configuration File**:
   Create `uwsgi.ini` in the project root:
   ```ini
   [uwsgi]
   module = notification_service.wsgi:application
   master = true
   processes = 4
   threads = 2
   socket = 0.0.0.0:8000
   chmod-socket = 666
   vacuum = true
   die-on-term = true
   logto = /var/log/uwsgi/notification.log
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
         POSTGRES_DB: notification_db
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
   - Create an Nginx config file (e.g., `/etc/nginx/sites-available/notification`):
     ```nginx
     server {
         listen 80;
         server_name your-domain.com;

         location / {
             include uwsgi_params;
             uwsgi_pass 0.0.0.0:8000;
         }

         location /ws/ {
             proxy_pass http://0.0.0.0:8000;
             proxy_http_version 1.1;
             proxy_set_header Upgrade $http_upgrade;
             proxy_set_header Connection "upgrade";
         }
     }
     ```
   - Enable and restart Nginx:
     ```bash
     sudo ln -s /etc/nginx/sites-available/notification /etc/nginx/sites-enabled
     sudo nginx -t
     sudo systemctl restart nginx
     ```

2. **Run uWSGI**:
   ```bash
   uwsgi --ini uwsgi.ini
   ```

3. **Systemd Service (Optional)**:
   - Create a systemd service file (e.g., `/etc/systemd/system/notification.service`):
     ```ini
     [Unit]
     Description=uWSGI instance to serve Notification Microservice
     After=network.target

     [Service]
     User=your-user
     Group=www-data
     WorkingDirectory=/path/to/notification_service
     ExecStart=/usr/local/bin/uwsgi --ini uwsgi.ini
     Restart=always

     [Install]
     WantedBy=multi-user.target
     ```
   - Enable and start:
     ```bash
     sudo systemctl enable notification
     sudo systemctl start notification
     ```
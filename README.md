# IntelliID — Intelligent Identity Lifecycle Orchestrator

IntelliID is an enterprise-grade Identity Lifecycle Orchestrator designed to integrate seamlessly with Okta APIs. Built with FastAPI and SQLAlchemy, it automates user provisioning, group migration, and bulk administration while maintaining a robust, persistent SQL audit trail for security compliance.

---

## 🚀 Key Features

*   **Okta User Lifecycle Management**:
    *   List existing Okta users and retrieve status.
    *   Create users with structured validation.
    *   Provision/activate, deactivate, and permanently delete users.
*   **Automated Group Migration**:
    *   List Okta groups.
    *   Move users smoothly between security/distribution groups (`old_group_id` to `new_group_id`) in a single orchestrated action.
*   **High-Throughput Bulk Operations**:
    *   Perform bulk provisioning, bulk deactivation, and bulk deletion for lists of user IDs.
*   **Compliant Audit Logging**:
    *   Every transaction, user state change, or membership move is automatically captured.
    *   Maintains a detailed database log (Action, User, Old Value, New Value, Status, Message, and Timestamp) using local SQLite/SQLAlchemy.
*   **Identity Data Export**:
    *   Instantly download lists of Okta users with active profiles directly as CSV files.

---

## 🛠️ Architecture & Core Stack

*   **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+), utilizing async requests for lightning-fast networking.
*   **Authentication with Okta**: OAuth 2.0 Client Credentials Grant utilizing **Private Key JWT (RS256 assertions)** for zero-compromise security.
*   **Database**: SQLite (via SQLAlchemy ORM) for persistent, localized audit trail storage.
*   **Data Validation**: [Pydantic v2](https://docs.pydantic.dev/) schemas to enforce strong input type safety.

---

## 📂 Project Directory Structure

```text
C:\Users\fuzay\Documents\PROJECT\CTS\intelliid\
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI Application Entrypoint
│   │   ├── core/
│   │   │   └── config.py           # Configuration & Settings (Pydantic-Settings)
│   │   ├── db/
│   │   │   ├── database.py         # SQLAlchemy Database Engine & Sessions
│   │   │   └── models.py           # SQL Database Models (AuditLog Table)
│   │   ├── routers/
│   │   │   ├── users.py            # Individual User lifecycle endpoints
│   │   │   ├── groups.py           # Group memberships and movement
│   │   │   ├── logs.py             # Query system audit logs
│   │   │   ├── export.py           # Identity CSV exporter
│   │   │   └── bulk_users.py       # Bulk orchestrations (Bulk Prov/Deact/Del)
│   │   ├── schemas/
│   │   │   ├── user.py             # User request/response schemas
│   │   │   └── bulk_user.py        # Bulk operation validation schemas
│   │   └── services/
│   │       ├── okta_client.py      # Core Okta API Client (Client Credentials / Private Key JWT)
│   │       ├── user_service.py     # User lifecycle orchestration business logic
│   │       ├── group_service.py    # Group membership manipulation logic
│   │       ├── bulk_user_service.py# Batch execution orchestrator
│   │       └── audit_service.py    # Persistent audit log writer
│   ├── keys/                       # Directory for Okta Private Key certificate (.pem)
│   ├── .env.example                # Sample Environment variables template
│   ├── requirements.txt            # Python dependencies package list
│   └── .gitignore                  # Git Ignore configuration
```

---

## ⚙️ Prerequisites & Setup

### 1. Okta API Integration Requirements
To communicate securely with Okta, IntelliID utilizes **Private Key JWT authentication**. 
Ensure you have:
1. Created an **API Service Integration** in your Okta Admin Console.
2. Granted the following scopes to the integration:
   * `okta.users.manage`
   * `okta.groups.manage`
   * `okta.logs.read`
3. Generated a public/private key pair in Okta. Save the private key in PEM format (e.g., `private_key.pem`) locally on your server.

### 2. Environment Variables Setup
Copy `.env.example` to create a local `.env` configuration:

```bash
cd backend
cp .env.example .env
```

Open `.env` and configure the values:

```env
OKTA_DOMAIN=https://your-domain.okta.com
OKTA_CLIENT_ID=your_okta_service_client_id
OKTA_PRIVATE_KEY_PATH=./keys/okta-private-key.pem

DATABASE_URL=sqlite:///./intelliid.db
FRONTEND_URL=http://localhost:5173
```

> **Security Note:** Never commit your `.env` file or your `.pem` files in public repository commits. Keep `keys/` and `.env` added to your `.gitignore`.

---

## 🚀 Installation & Running

### Step 1: Create and Activate Virtual Environment
Navigate to the `backend` folder:

```bash
cd backend
python -m venv venv
```

Activate the virtual environment:
*   **Windows (PowerShell)**:
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```
*   **Windows (CMD)**:
    ```cmd
    .\venv\Scripts\activate.bat
    ```
*   **macOS / Linux**:
    ```bash
    source venv/bin/activate
    ```

### Step 2: Install Dependencies
Install all required Python packages:

```bash
pip install -r requirements.txt
```

### Step 3: Run the Server
Launch the development server with **Uvicorn**:

```bash
uvicorn app.main:app --reload
```

The server will spin up and start listening on:
*   **App Root**: `http://127.0.0.1:8000/`
*   **Health Status**: `http://127.0.0.1:8000/health`

---

## 📖 API Documentation (Interactive Swagger UI)

FastAPI automatically generates interactive documentation. Once the server is running, visit:
*   **Swagger UI (Interactive API Play)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
*   **ReDoc (Structured Docs)**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🛣️ API Endpoints Summary

### General / Infrastructure
*   `GET /` — Returns application status and metadata.
*   `GET /health` — Simple health check verification.

### Users (`/api/users`)
*   `GET /` — Retrieve all users from Okta.
*   `POST /` — Create a new user in Okta (accepts user profile details).
*   `POST /{user_id}/provision` — Start Okta provisioning for the user.
*   `POST /{user_id}/deactivate` — Safely deactivate a user's Okta identity.
*   `DELETE /{user_id}` — Deletes the user permanently.

### Groups (`/api/groups`)
*   `GET /` — Lists all registered Okta security groups.
*   `POST /move` — Move a user from one group to another.
    *   *Body*: `{ "user_id": "...", "old_group_id": "...", "new_group_id": "..." }`

### Bulk Orchestration (`/api/bulk/users`)
*   `POST /provision` — Provision multiple user IDs in bulk.
*   `POST /deactivate` — Deactivate multiple user IDs in bulk.
*   `DELETE /` — Delete multiple user IDs in bulk.

### Compliance / Audit Logs (`/api/logs`)
*   `GET /` — Fetches the consolidated audit log database events sorted newest-to-oldest.

### Exporter (`/api/export`)
*   `GET /users.csv` — Triggers a live export stream of all Okta users formatted in standardized CSV structure.

---

## 🔒 Security & Compliance Best Practices
1. **Credentials Management**: Always load API client credentials through Environment variables.
2. **Audit Integrity**: Do not clear the `intelliid.db` file in production environments as it maintains historical tracing of identity provisioning operations.
3. **Transport Security**: Deploy this behind an SSL/TLS-terminated reverse proxy (such as Nginx, Traefik, or AWS ALB) in production environments to secure access to the FastAPI endpoints.

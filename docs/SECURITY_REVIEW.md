# UtsavOps — Security Review & Hardening Audit

This document details the security posture, threat modeling, and defensive controls implemented across UtsavOps.

---

## 1. Authentication & Session Management

| Control | Implementation | Verification Status |
| :--- | :--- | :--- |
| **Dedicated Token Secret** | Uses `AUTH_SECRET_KEY` separate from `GEMINI_API_KEY`. In production mode, application refuses to start if `AUTH_SECRET_KEY` is missing or shorter than 32 characters. | **PASSED** |
| **Algorithm** | HMAC-SHA256 (`HS256`) with strict validation. | **PASSED** |
| **Server-Side Token Revocation** | Tokens are revoked on `/api/auth/logout`. Signature hashes are stored in the `revoked_tokens` table in Cloud SQL PostgreSQL and cached in memory. Revoked tokens are immediately rejected on subsequent requests. | **PASSED** |
| **Rate Limiting** | Sliding-window rate limiter limits failed login attempts to 5 attempts per 5-minute window per IP/username. Rate limit counter resets on successful authentication. | **PASSED** |
| **Password Storage** | PBKDF2 / SHA-256 salted password hashing. Passwords are never stored in plaintext or logged. | **PASSED** |

---

## 2. Role-Based Access Control (RBAC)

The system enforces three distinct operator roles:
1. **`admin`**: Full administrative access, feature flag modification, surge mode toggles, and incident mitigation approvals/executions.
2. **`sre_lead`**: AIOps incident investigation, mitigation approval, mitigation execution, and cluster recovery verification.
3. **`operator`**: Order intake, order review, address validation, and voice confirmation streaming.

Mutating endpoints are strictly protected with the `require_roles()` FastAPI dependency:
- `POST /api/flags/surge-mode`: Restricted to `admin` and `sre_lead`.
- `POST /api/aiops/incidents/{id}/actions/{action_id}/approve`: Restricted to `admin` and `sre_lead`.
- `POST /api/aiops/incidents/{id}/actions/{action_id}/execute`: Restricted to `admin` and `sre_lead`.
- `POST /api/customers/{id}/vip`: Restricted to `admin` and `sre_lead`.

---

## 3. Database Integrity & Fail-Safe Modes

- **Authoritative Storage**: Cloud SQL PostgreSQL is the sole authoritative system of record for production orders, customer accounts, and incidents.
- **Fail-Safe Startup**: Unlike development mode where SQLite is permitted, production mode (`APP_ENV=production`) raises a fatal startup error if Cloud SQL PostgreSQL is unreachable, preventing silent data fragmentation.
- **Unique Constraints**: Customer phone numbers are protected by the database-level unique index `uq_customers_phone`. Phone uniqueness is verified before inserts or updates.
- **Transaction Rollback**: Order intake and review mutations are wrapped in explicit database transaction blocks with `await db.rollback()` on error to eliminate orphaned child rows.

---

## 4. API Keys & Secret Handling

- All sponsor API keys (`SARVAM_API_KEY`, `FLAGSMITH_ENV_KEY`, `FLAGSMITH_ADMIN_API_KEY`, `GOOGLE_MAPS_API_KEY`, `GEMINI_API_KEY`, `AUTH_SECRET_KEY`) are read strictly from environment variables.
- Secret values are never exposed in terminal output, client-side bundles, API responses, or Git repositories.
- `.gitignore` strictly ignores `.env`, `*.db`, `*.sqlite`, `*.pem`, `*.key`, and test artifacts.

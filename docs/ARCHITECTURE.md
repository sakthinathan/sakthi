# UtsavOps — Complete Architecture Specification

## 1. System Overview

**UtsavOps** is an autonomous, self-healing commerce operations platform engineered specifically for Indian festive retail spikes. During peak cultural festivals (Diwali, Dussehra, Pongal, Ganesh Chaturthi), retail demand surges by 10x to 25x, incoming orders arrive over chaotic channels (handwritten slips, regional voice notes), and checkout infrastructure faces sudden failure modes.

UtsavOps bridges this chaos through a two-sided architecture:
1. **Multilingual Order Intelligence**: Powered by Sarvam AI (`Document AI`, `Saaras v4`, `Mayura v1`, and `Bulbul v3`) to extract, transcribe, translate, normalize, and confirm orders in regional Indian languages (Hindi, Tamil, English).
2. **Resilient Self-Healing Infrastructure**: Powered by Flagsmith dynamic feature flagging and segment management, coupled with NudgeBee k3s Kubernetes cluster monitoring, Google Cloud SQL PostgreSQL, and Gemini BYOM Root Cause Analysis.

---

## 2. Architectural Layers

### A. Frontend Layer (Operator & SRE Cockpit)
- **Framework**: React 19 + Vite 6 + TailwindCSS v4.
- **Client Routing & Security**: React Router 7 with `AuthProvider` and `ProtectedRoute`.
- **Pages**:
  - `Login`: Secure operator authentication with credentials, role detection, and session management.
  - `Dashboard`: Real-time KPI analytics, surge status notifications, and live sponsor integration badges.
  - `OrderIntake`: Multi-modal order intake (Handwritten Chit upload with preview, Voice note STT with audio preview, or Manual Entry).
  - `OrderReview`: Human-in-the-loop review, item edit/approval, and instant Bulbul v3 voice confirmation playback.
  - `Dispatch`: Google Address Validation, Geocoding, and Google Air Quality API contextual telemetry with map previews.
  - `VIPAndPricing`: Flagsmith surge survival toggle, dynamic bundle pricing, and VIP customer tier segmentation.
  - `AIOpsCenter`: Kubernetes service health cockpit (`utsavops-checkout`, `newsletter-worker`), Gemini BYOM incident investigation, and bounded mitigation approvals.
  - `AuditLog`: Immutable, tamper-evident chronological audit trail of all administrative and automated actions.

### B. Application Gateway Layer (FastAPI Backend)
- **Framework**: FastAPI (Python 3.11/3.13) with asynchronous ASGI event loop.
- **Authentication & RBAC**:
  - HMAC-SHA256 JWT tokens signed with dedicated `AUTH_SECRET_KEY`.
  - In-memory and database-backed revoked token blacklist (`RevokedToken` model).
  - Sliding-window IP/username rate limiting (5 attempts per 300s window).
  - Role-based access control (`admin`, `sre_lead`, `operator`) enforced via `require_roles()` dependencies.
- **Core Routers**:
  - `/api/auth`: Login, operator info, and token revocation logout.
  - `/api/orders`: Order intake, multi-lingual audio/image parsing, status mutation, and Bulbul TTS voice confirmations.
  - `/api/flags`: Flagsmith feature flag queries, surge mode toggle with remote Management API synchronization, and VIP segmentation.
  - `/api/dispatch`: Google Address Validation, Geocoding, and Air Quality lookups.
  - `/api/aiops`: Service health inspection, incident generation, Gemini BYOM investigation, mitigation approval, and recovery verification.
  - `/api/customers`: Customer listing, spend stats, and VIP tier mutations.
  - `/api/audit`: Audit event retrieval with actor, entity, and action tracking.

### C. Database & Data Integrity Layer
- **Authoritative Database**: Google Cloud SQL PostgreSQL (`utsavops` database, hosted on `35.234.219.215:5432`).
- **Connection Framework**: SQLAlchemy 2.0 async engine (`asyncpg` for PostgreSQL, `aiosqlite` for local dev/testing).
- **Relational Models**:
  - `Order` & `OrderItem`: Order tracking, address validation status, coordinates, AQI data, and verification states.
  - `Customer`: Customer demographics, VIP flag, total spend, with strict unique index on phone number (`uq_customers_phone`).
  - `Operator`: System users with hashed passwords and assigned RBAC roles.
  - `RevokedToken`: Signature-level token revocation registry with expiration tracking.
  - `Incident` & `IncidentAction`: AIOps incident tracking, root cause reports, proposed actions, human approvals, and execution logs.
  - `AuditLog`: Immutable operational log recording all mutating operations.
- **Fail-Safe Startup**: Production mode strictly validates Cloud SQL connectivity and halts startup on failure rather than silently degrading to local storage.

### D. Cloud Infrastructure & Kubernetes Layer
- **Google Cloud Platform**:
  - Project ID: `festive-hacks-2026`
  - Region: `asia-south1` (Mumbai), Zone: `asia-south1-a`
  - Cloud SQL PostgreSQL instance: `utsavops-db` (PostgreSQL 15, Always On)
  - Compute Engine VM: `utsavops-nudgebee` (Ubuntu 22.04 LTS, hosting k3s cluster)
- **Kubernetes Cluster (k3s)**:
  - Namespace: `utsavops`
  - Tier 1 (Critical): `utsavops-checkout` Deployment (3 replicas) & Service
  - Tier 2 (Low Priority): `newsletter-worker` Deployment (1 replica)
  - NudgeBee Monitoring & Secret: `flagsmith_api_key` mapped into `nudgebee` namespace.

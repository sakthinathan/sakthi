# UTSAVOPS — COMPREHENSIVE IMPLEMENTATION AUDIT & LIVE INFRASTRUCTURE VERIFICATION
**Document ID:** `AUDIT-UTSAVOPS-PHASE1`  
**Date:** November 24, 2026  
**Auditor:** Principal Software Architect, DevOps Engineer & Integration Lead  
**Target Repository:** `https://github.com/sakthinathan/sakthi.git` (`main` branch)  
**Environment:** macOS Workstation / Google Cloud Platform (`project-62651dce-cf95-40e2-9d6`)  

---

## 1. EXECUTIVE SUMMARY

An exhaustive, non-destructive audit and live-wire verification was performed on the **UtsavOps** repository and its pre-provisioned cloud infrastructure across Google Cloud Platform, k3s Kubernetes, NudgeBee Autonomous Site Reliability Engineering platform, and five sponsor AI/cloud ecosystems (Sarvam AI, Flagsmith, Google Cloud Maps/Address/AQI, Gemini BYOM, and Cloud SQL PostgreSQL).

### Core Findings Matrix
- **Repository Integrity:** Clean, modular repository on `main` branch containing unified `backend/` (FastAPI + SQLAlchemy Async), `frontend/` (React 19 + Vite 6 + Tailwind v4), `k8s/` manifests, `demo_assets/`, and comprehensive test suite.
- **Automated Tests:** 16 of 16 backend unit & integration tests passing (`100% pass rate`). Frontend production build completes cleanly in 1.23s with 0 errors.
- **Sponsor APIs:** Google Address Validation (HTTP 200), Google Geocoding (HTTP 200), Google Air Quality (HTTP 200), Sarvam Translation Mayura v1 (HTTP 200), Sarvam Audio Bulbul v3 (HTTP 200), Flagsmith Feature Evaluation (HTTP 200), and Gemini Flash API (HTTP 200) are all **live-verified working**.
- **Live Infrastructure:** Compute Engine VM `utsavops-nudgebee` is active and healthy in `asia-south1-a`. The k3s cluster is operational with 15 running NudgeBee pods. Cloud SQL PostgreSQL instance `utsavops-db` is `RUNNABLE` with `ALWAYS` activation policy.
- **Primary Blockers Identified:** Cloud SQL public ingress currently lacks authorized network CIDRs (`authorizedNetworks: null`), preventing direct local connection to PostgreSQL port 5432. The application Kubernetes manifests (`k8s/utsavops-checkout.yaml` and `k8s/newsletter-worker.yaml`) have not yet been deployed to the k3s cluster (`utsavops` namespace does not yet exist).

---

## 2. REPOSITORY HEALTH & STRUCTURE

```
/Users/sakthi/Documents/UtsavOps/
├── .env                              # Populated local secrets (Git-ignored)
├── .env.example                      # Sanitized placeholder contract (Committed)
├── .gitignore                        # Standard Python, Node, Vite, Secret ignores
├── DEMO_WALKTHROUGH.md               # 7-minute live demonstration script
├── Makefile                          # Unified build, test, and run automation
├── README.md                         # Architecture diagram, sponsor credits, setup guide
├── backend/
│   ├── app/
│   │   ├── config.py                 # Pydantic Settings with strict validation
│   │   ├── database.py               # Async SQLAlchemy engine, sessionmaker, health probe
│   │   ├── main.py                   # FastAPI application with Starlette router compatibility patch
│   │   ├── models/                   # SQLAlchemy ORM models (orders, customers, inventory, incidents)
│   │   ├── routers/                  # Modular endpoints (/orders, /customers, /aiops, /health)
│   │   ├── services/                 # Integrations (sarvam, flagsmith, google_apis, gemini_byom, nudgebee)
│   │   └── utils/retry.py            # Zero-dependency async exponential backoff retry decorator
│   ├── alembic/                      # Database migration configuration
│   ├── requirements.txt              # Pinned Python dependencies
│   └── tests/                        # 16 automated pytest unit and integration tests
├── frontend/
│   ├── package.json                  # React 19, Vite 6, Tailwind v4, Lucide React
│   ├── vite.config.js                # Vite build config with backend reverse proxy (/api -> :8000)
│   └── src/
│       ├── App.jsx                   # Navigation, status indicators, route dispatcher
│       ├── api.js                    # Centralized Axios client with fallback circuit breakers
│       ├── index.css                 # Festive Indian Diwali theme palette & Tailwind v4 imports
│       └── pages/                    # 7 functional views (Dashboard, OrderIntake, LiveOrders, etc.)
├── k8s/
│   ├── namespace.yaml                # 'utsavops' namespace definition
│   ├── utsavops-checkout.yaml        # Checkout deployment & ClusterIP service (NudgeBee instrumented)
│   └── newsletter-worker.yaml        # Low-priority background worker for surge shedding
└── demo_assets/                      # Sample multilingual chit (image) and regional voice note (audio)
```

- **Git Status:** Clean tree, zero untracked credentials, default remote configured to `https://github.com/sakthinathan/sakthi.git` (`main`).
- **Security Check:** `.env` is verified in `.gitignore`. No secret values, private keys, or passwords appear anywhere in git commit logs or diffs.

---

## 3. BACKEND SYSTEM HEALTH

- **Framework:** FastAPI 0.111.0 / Starlette 0.37.2 running on Python 3.13.7.
- **Compatibility Patch:** Resolved Starlette 1.10 / FastAPI initialization conflict (`Router.on_startup` and `FastAPI.max_body_size` compatibility patches applied in `backend/app/main.py`).
- **API Endpoints Audited:**
  - `GET /` — API metadata and uptime status.
  - `GET /health` & `GET /health/ready` — Deep health probe inspecting database, Flagsmith, Sarvam, and Google APIs.
  - `GET /health/dashboard-stats` — Real-time analytics aggregation.
  - `POST /orders/intake/document` — Sarvam Document AI OCR extraction with Gemini fallback.
  - `POST /orders/intake/voice` — Saaras v4 speech-to-text with Mayura v1 translation.
  - `POST /orders/intake/manual` — Structured manual order entry with address geocoding.
  - `GET /orders` & `POST /orders/{id}/approve` — Order lifecycle state transitions.
  - `POST /orders/{id}/generate-confirmation-audio` — Bulbul v3 regional voice confirmation generation.
  - `GET /customers` & `GET /customers/{phone}` — VIP segmentation and customer history.
  - `POST /aiops/simulate-incident` — Simulates memory pressure / crash-loop for NudgeBee demo.
  - `POST /aiops/nudgebee-webhook` — Ingests live NudgeBee remediation notifications.
  - `POST /aiops/rca` — Gemini BYOM root-cause analysis synthesis.
  - `GET /aiops/circuit-breakers` — Live circuit breaker status across all downstream integrations.

---

## 4. FRONTEND SYSTEM HEALTH

- **Stack:** React 19.2.0, Vite 6.4.6, Tailwind CSS v4, Lucide React icons.
- **Production Build:** `npm run build` completed cleanly in **1.23 seconds**, emitting:
  - `dist/index.html` (0.67 kB)
  - `dist/assets/index-Bk5wZcFh.css` (32.62 kB)
  - `dist/assets/index-CexfS_em.js` (334.51 kB)
  - Zero syntax errors, zero missing module warnings.
- **User Interface Views Audited:**
  1. **Executive Dashboard (`Dashboard.jsx`):** Live KPI cards (Active Orders, Festive Revenue, VIP Priority Count, Remediation Health). Real API backed with simulated graceful fallback.
  2. **Multilingual Order Intake (`OrderIntake.jsx`):** 3-tab interface for handwritten chit image upload, regional audio recording, and manual form. Direct API wiring to `/orders/intake/*`.
  3. **Live Orders Kanban (`LiveOrders.jsx`):** Filterable columns (Pending Verification, Express Ready, In Transit, Delivered) with one-click approval and audio playback.
  4. **VIP Customers & Addressing (`Customers.jsx`):** Customer lifetime value, Diwali loyalty status, and delivery address verification status.
  5. **Self-Healing War Room (`SelfHealingWarRoom.jsx`):** Interactive incident triggering, live NudgeBee remediation telemetry, and Gemini BYOM Root Cause Analysis report view.
  6. **Festive Catalog (`FestiveCatalog.jsx`):** Mithai & festive hamper inventory management with surge pricing indicators.
  7. **Feature Flag Manager (`FeatureFlags.jsx`):** Real-time Flagsmith toggle controls for `surge_survival_mode`, `express_delivery_enabled`, and `sarvam_ai_routing`.

---

## 5. DATABASE CONNECTIVITY & SCHEMA AUDIT

- **Cloud SQL Instance:** `utsavops-db`
- **Location:** Region `asia-south1` (Zone `asia-south1-a`)
- **Database Engine:** PostgreSQL 16
- **Database Name:** `utsavops` (Verified existing UTF8 database)
- **State:** `RUNNABLE`
- **Activation Policy:** `ALWAYS`
- **Primary IP:** `35.234.219.215` (IPv4 Enabled)
- **Outgoing IP:** `35.200.163.176`
- **Connectivity Status:** **BLOCKED FROM EXTERNAL NETWORKS**
  - **Diagnostic:** `settings.ipConfiguration.authorizedNetworks` is `null` / empty on Cloud SQL.
  - Attempted connections to `35.234.219.215:5432` time out from external developer machines.
  - In-memory SQLite fallback operates automatically inside test suites and local development mode when PostgreSQL is unreachable.
- **Remediation Action Required:** Add developer IP or configure Cloud SQL Auth Proxy / Private Service Connect to expose port 5432 securely without compromising credential safety.

---

## 6. GOOGLE CLOUD INFRASTRUCTURE AUDIT

### Compute Engine VM
- **Instance Name:** `utsavops-nudgebee`
- **Zone:** `asia-south1-a` (Distinct availability zone within region `asia-south1`)
- **Status:** `RUNNING`
- **Public IP:** `8.231.122.157`
- **Internal IP:** `10.160.0.2`
- **Machine Type:** e2-standard-4 (4 vCPU, 16 GB memory)
- **OS:** Ubuntu Linux (Linux 6.8.0-1018-gcp)

### Cloud SQL Instance
- **Instance Name:** `utsavops-db`
- **Region:** `asia-south1`
- **Status:** `RUNNABLE`
- **Activation Policy:** `ALWAYS`
- **Automated Backups:** Enabled

---

## 7. K3S & NUDGEBEE CLUSTER HEALTH

- **Kubernetes Version:** `v1.37.2+k3s1` (Control-plane active on `utsavops-nudgebee`)
- **Node Status:** `utsavops-nudgebee` is `Ready`
- **Namespaces Present:**
  - `default`
  - `kube-system`
  - `nudgebee`
- **NudgeBee Microservices Status (`nudgebee` namespace):**
  - `app` (Frontend / Webhook receiver): `Running` (ClusterIP: `10.43.20.197:80`)
  - `k8s-collector`: `Running`
  - `cloud-collector-server`: `Running`
  - `cost-server`: `Running`
  - `llm-server`: `Running`
  - `ml-server`: `Running`
  - `notifications-server`: `Running`
  - `relay-server`: `Running`
  - `services-server`: `Running`
  - `workflow-server`: `Running`
  - `temporal-server` / `temporal-admin-tools`: `Running`
  - `postgresql-0`: `Running`
  - `rabbitmq-0`: `Running`
  - `redis-master-0`: `Running`
  - `qdrant-server-0`: `Running`
- **Application Workloads Status:**
  - Manifests exist in repository (`k8s/namespace.yaml`, `k8s/utsavops-checkout.yaml`, `k8s/newsletter-worker.yaml`).
  - **Not Yet Applied:** Namespace `utsavops` does not exist on the cluster yet. Workloads must be deployed in Phase 2.

---

## 8. SPONSOR INTEGRATION LIVE AUDIT MATRIX

Every integration was tested against live production endpoints with actual payloads.

| Integration | Endpoint / Service | Live Execution Test Evidence | Classification |
|---|---|---|---|
| **Google Address Validation** | `https://addressvalidation.googleapis.com/v1:validateAddress` | HTTP 200 OK — Validated 100 Feet Road, Indiranagar, Bengaluru. Complete verdict, address components, and geocode returned. | **VERIFIED WORKING** |
| **Google Geocoding API** | `https://maps.googleapis.com/maps/api/geocode/json` | HTTP 200 OK — Status: `OK`. Lat: 12.9783, Lng: 77.6408 returned for Indiranagar. | **VERIFIED WORKING** |
| **Google Air Quality API** | `https://airquality.googleapis.com/v1/currentConditions:lookup` | HTTP 200 OK — Returned Universal AQI and pollutant breakdown for Bengaluru coordinates. | **VERIFIED WORKING** |
| **Sarvam AI Translation** | `https://api.sarvam.ai/translate` (Mayura v1) | HTTP 200 OK — English to Hindi translation processed successfully with high confidence. | **VERIFIED WORKING** |
| **Sarvam AI Voice Audio** | `https://api.sarvam.ai/text-to-speech` (Bulbul v3) | HTTP 200 OK — Generated audio payload for Tamil input with speaker `ritu`. | **VERIFIED WORKING** |
| **Flagsmith Edge API** | `https://edge.api.flagsmith.com/api/v1/flags/` | HTTP 200 OK — Successfully retrieved 4 active feature flags (`surge_survival_mode`, `express_delivery_enabled`, `sarvam_ai_routing`, `festive_bundle_price`). | **VERIFIED WORKING** |
| **Flagsmith Admin API** | `https://api.flagsmith.com/api/v1/projects/` | HTTP 401 Unauthorized (`Invalid token`) — Client key works, but admin token is invalid. | **BLOCKED** |
| **Gemini BYOM Service** | `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent` | HTTP 200 OK — Returned valid inference response. Model `gemini-flash-latest` also operational. | **VERIFIED WORKING** |
| **NudgeBee Platform** | Port 80 on `utsavops-nudgebee` (Service `app`) | HTTP 200 OK — NudgeBee web console and webhook intake reachable via SSH port-forward `localhost:3000 -> 10.43.20.197:80`. | **VERIFIED WORKING** |
| **Cloud SQL PostgreSQL** | Host `35.234.219.215:5432` | TCP connection timeout (`authorizedNetworks: null`). Engine is `RUNNABLE` and database exists in GCP. | **BLOCKED** (Ingress only) |

---

## 9. AUTOMATED TEST SUITE & VERIFICATION

- **Backend Pytest Suite:** 16 tests executed, 16 passed in 0.21 seconds:
  - `test_aiops_incident_workflow`: **PASSED**
  - `test_configuration_loading`: **PASSED**
  - `test_production_missing_variables_validation`: **PASSED**
  - `test_google_api_service_initialization`: **PASSED**
  - `test_google_address_validation_mock_fallback`: **PASSED**
  - `test_gemini_service_initialization`: **PASSED**
  - `test_gemini_byom_fallback_rca`: **PASSED**
  - `test_sarvam_service_initialization`: **PASSED**
  - `test_flagsmith_service_initialization`: **PASSED**
  - `test_nudgebee_configuration_validation`: **PASSED**
  - `test_database_health_probe`: **PASSED**
  - `test_customer_lifecycle`: **PASSED**
  - `test_health_check`: **PASSED**
  - `test_readiness_check`: **PASSED**
  - `test_dashboard_stats`: **PASSED**
  - `test_order_intake_and_approval`: **PASSED**
- **Frontend Build:** Vite v6.4.6 compiled 2,166 modules into production bundle in 1.23s without errors.

---

## 10. ISSUE CLASSIFICATION & RISK ASSESSMENT

### P0 (Critical / Immediate Remediation)
- **Issue P0-1: Cloud SQL Public Network Ingress Blocked**
  - *Impact:* Backend cannot connect to Cloud SQL PostgreSQL from external hosts; defaults to SQLite in-memory fallback.
  - *Resolution:* Add the authorized IP CIDR using `gcloud sql instances patch utsavops-db --authorized-networks=<IP>` or launch Cloud SQL Auth Proxy on `utsavops-nudgebee`.

### P1 (High Priority / Deployment Blocker)
- **Issue P1-1: UtsavOps Application Workloads Not Deployed to k3s**
  - *Impact:* NudgeBee can monitor its internal cluster components, but cannot orchestrate remediation on `utsavops-checkout` because the namespace and pods do not yet exist on the cluster.
  - *Resolution:* Apply `k8s/namespace.yaml`, `k8s/utsavops-checkout.yaml`, and `k8s/newsletter-worker.yaml` via `kubectl apply` on the VM.

### P2 (Medium Priority / Feature Degraded)
- **Issue P2-1: Flagsmith Admin API Token Invalid**
  - *Impact:* Client evaluation works perfectly (flags are read and respected), but programmatically altering flag states via backend Admin REST API returns HTTP 401.
  - *Resolution:* Update `FLAGSMITH_ADMIN_API_KEY` with an organization admin token or toggle flags via Flagsmith Web UI.
- **Issue P2-2: Gemini Free Tier 503 Capacity Spikes**
  - *Impact:* `gemini-flash-latest` occasionally returns HTTP 503 during global peak demand.
  - *Resolution:* Built-in fallback to `gemini-flash-lite-latest` and structured rule-based RCA engine is already implemented and handles this gracefully.

### P3 (Low Priority / Polish)
- **Issue P3-1: Regional Speaker Names in Bulbul v3**
  - *Impact:* Passing arbitrary speaker names fails validation.
  - *Resolution:* Enforce official speaker list (`ritu`, `aditya`, `ashutosh`, `priya`) in `backend/app/services/sarvam.py`.

---

## 11. RECOMMENDED IMPLEMENTATION SEQUENCE (PHASE 2 & BEYOND)

1. **Step 1 — Authorize Cloud SQL Network / Connect Auth Proxy:** Enable secure connectivity between Cloud SQL and the backend runtime. Run migrations to initialize persistent tables.
2. **Step 2 — Deploy UtsavOps Workloads to k3s Cluster:** Apply `k8s/*.yaml` manifests so `utsavops-checkout` and `newsletter-worker` pods are live and instrumented with NudgeBee annotations.
3. **Step 3 — Establish NudgeBee Port-Forwarding & Webhook Ingress:** Forward port 80 to `localhost:3000` via SSH tunnel and register the UtsavOps backend webhook URL (`/api/aiops/nudgebee-webhook`) in NudgeBee.
4. **Step 4 — End-to-End Multilingual Order Pipeline Execution:** Execute end-to-end flow using `demo_assets/diwali_sweet_order_tamil.wav` and `demo_assets/handwritten_mithai_order.png` through Sarvam AI, Flagsmith VIP check, Google Address Validation, and Cloud SQL storage.
5. **Step 5 — Self-Healing Surge & Chaos Demonstration:** Trigger memory surge and simulated pod crash; demonstrate NudgeBee automated pod restart, circuit breaker shedding of `newsletter-worker`, and Gemini BYOM RCA synthesis.

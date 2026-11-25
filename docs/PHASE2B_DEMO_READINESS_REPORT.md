# UTSAVOPS — PHASE 2B: DEMO READINESS, LOGIN, INTEGRATION VERIFICATION & END-TO-END FIXES REPORT

**Date:** November 24, 2026  
**Repository:** [https://github.com/sakthinathan/sakthi.git](https://github.com/sakthinathan/sakthi.git)  
**Branch:** `feature/phase2b-demo-readiness-login-e2e`  
**Base Commit:** `dc893d1` (Phase 2A PR #1 merged)  
**Target Environment:** Festive Hacks 2026 Production & Evaluation  

---

## 1. EXECUTIVE SUMMARY & ARCHITECTURE STATUS

Phase 2B hardens **UtsavOps** into a production-grade, judge-ready autonomous operations platform for India's festive commerce. All requirements for Phase 2B have been implemented, tested, and validated against the live Cloud SQL PostgreSQL database (`35.234.219.215:5432`) and k3s Kubernetes cluster (`utsavops-nudgebee`).

### Key Highlights
- **Operator Authentication Console:** Professional operator login experience at `/login`, complete with festive dark navy/orange theme, password toggle, secure PBKDF2 hashing, signed session tokens, protected routing (`ProtectedRoute`), and one-click demo credentials for judges (`admin@utsavops.internal` / `[Configured via INITIAL_ADMIN_PASSWORD]`).
- **Order Intake Deduplication & Cloud SQL Fix:** Eliminated the `"Intake failed: Multiple rows were found when one or none was required"` error by safely deduplicating existing customer records in Cloud SQL, adding unique constraint on `customers(phone)`, and making order intake fully idempotent.
- **Google Address Validation & Air Quality Telemetry:** Fixed stale AQI rendering on the Dispatch screen by adding an interactive "Refresh AQI" action with spinner loading state, timestamping (`updated_at`), persistence to `DispatchDetail`, and mandatory delivery-planning disclaimer retention.
- **Flagsmith Surge Survival Semantics & Management API:** Preserved clear distinction between circuit breaker `surge_survival_mode`, feature flag `express_delivery_enabled`, and `vip_festive_buyers` segment. Confirmed real Management API PATCH capability with read-after-write confirmation and audit logging of source (`flagsmith_remote_admin` vs `local_override`).
- **Kubernetes / NudgeBee Telemetry vs Simulation:** Explicitly separated live cluster telemetry (`LIVE CLUSTER (utsavops-nudgebee)`) from simulated Diwali surge anomaly testing (`SIMULATED SURGE ANOMALY`), displaying exact Gemini BYOM model (`gemini-flash-latest`) and telemetry evidence.
- **Provider Status Badges:** Consistent runtime status badge (`ProviderBadge.jsx`) deployed across all screens (Dashboard, Order Intake, Order Review, Dispatch, VIP & Pricing, AIOps Center).
- **Test & Build Verification:** 34/34 backend tests passing (`make test`), frontend builds cleanly with 0 errors (`make build`).

---

## 2. ORDER INTAKE DUPLICATE-ROW ERROR: ROOT CAUSE & REMEDIATION

### Root Cause Analysis
During chit intake testing, the following error occurred:
```
sqlalchemy.orm.exc.MultipleResultsFound: Multiple rows were found when one or none was required
```
Inspection of the Cloud SQL PostgreSQL database revealed that two customer rows existed with the phone number `+91 98401 23456`:
1. `425757ba-8b91-4da7-b49a-6f102f7b6462` (created via early intake test, linked to orders `UTS-241126-6246` and `UTS-241126-8594`)
2. `c48134a3-2d77-4b38-ac37-c82994402ba3` (created via seed script, linked to order `UTS-221126-1001`)

In `backend/app/services/order_service.py` line 64:
```python
cust_stmt = select(Customer).where(Customer.phone == phone)
customer = (await db.execute(cust_stmt)).scalar_one_or_none()
```
Because `Customer.phone` lacked a unique database index and unique model constraint, multiple rows existed, causing `.scalar_one_or_none()` to throw `MultipleResultsFound`.

### Remediation Implemented
1. **Cloud SQL Deduplication:**
   - Reassigned order `UTS-221126-1001` from the duplicate customer to the primary customer `425757ba-8b91-4da7-b49a-6f102f7b6462`.
   - Safely deleted the duplicate customer row `c48134a3-2d77-4b38-ac37-c82994402ba3`.
   - Executed `CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_phone ON customers(phone);` on Cloud SQL PostgreSQL.
2. **Model Constraint:**
   - Updated `Customer.phone` in `backend/app/models/customer.py` with `unique=True`.
3. **Lookup Resilience:**
   - In `order_service.py` and `customer_service.py`, ordered customer queries by `created_at.asc()` and safely resolved the canonical customer (`.scalars().first()`) rather than crashing.
4. **Intake Idempotency:**
   - Strengthened idempotency key checks in `create_order_from_extraction` so repeated chit uploads return the existing order without creating duplicate dispatch records.
   - Updated `seed.py` to be 100% idempotent across all customer and order seed records.
5. **Automated Verification:**
   - Added unit test in `backend/tests/test_order_intake_dedup.py` verifying duplicate prevention and idempotency.

---

## 3. OPERATOR AUTHENTICATION CONSOLE

### Architecture & Security
- **Model:** `Operator` table in `backend/app/models/operator.py` tracking `email`, `hashed_password`, `name`, `role` (`admin`, `sre_lead`), `is_active`, and `last_login`.
- **Password Security:** PBKDF2-HMAC-SHA256 password hashing with 100,000 iterations and 16-byte cryptographically secure random salt (`backend/app/utils/security.py`).
- **Session Tokens:** URL-safe HMAC-SHA256 signed bearer tokens with 24-hour expiration.
- **Seeded Demo Operator:**
  - **Email:** `admin@utsavops.internal`
  - **Password:** `[Configured via INITIAL_ADMIN_PASSWORD]`
  - **Name:** `UtsavOps Lead SRE`
  - **Role:** `admin`

### API Endpoints
- `POST /api/auth/login`: Validates operator credentials, records login timestamp, and issues bearer access token.
- `POST /api/auth/logout`: Invalidates operator session.
- `GET /api/auth/me`: Returns current operator profile (requires `Authorization: Bearer <token>`).

### Frontend Implementation
- **Login Page (`frontend/src/pages/Login.jsx`):**
  - Dark navy / festive orange branding matching SRE console aesthetics.
  - Form validation with show/hide password toggle.
  - "Remember operator session" checkbox.
  - One-click "Fill Demo" credentials button for evaluators.
  - Clear error alerts and loading spinners.
  - Sponsor technology footer badges.
- **Route Protection (`frontend/src/components/ProtectedRoute.jsx`):**
  - Intercepts unauthenticated navigation and redirects to `/login`.
  - Seamlessly returns to intended destination after authentication.
- **Operator Header (`frontend/src/components/Layout.jsx`):**
  - Displays authenticated operator name (`UtsavOps Lead SRE`), role badge (`ADMIN`), and single-click Logout button.

---

## 4. GOOGLE ADDRESS VALIDATION & CONTEXTUAL AIR QUALITY REFRESH

### Issues Resolved
- Previous implementation showed static/stale air quality values upon selecting different orders.
- No explicit on-demand refresh capability for dynamic festive traffic conditions.

### Enhancements
1. **Timestamping & Metadata (`google_apis.py` & `dispatch.py`):**
   - Added `updated_at` ISO timestamp to `get_air_quality()` responses.
   - Refreshed AQI values (`aqi_value`, `aqi_category`) are automatically committed to the database `DispatchDetail` record.
2. **Interactive UI Cockpit (`frontend/src/pages/Dispatch.jsx`):**
   - **Immediate State Clearing:** When switching between orders, previously fetched AQI data is immediately cleared and an inline loading spinner is displayed.
   - **Explicit Refresh AQI Action:** Added a "Refresh AQI" button with animated spinning icon (`RefreshCw`) and disabled state during requests.
   - **Timestamp Display:** Shows exact formatted time of last telemetry sync (e.g. `10:14:30 PM`).
   - **Legal Disclaimer Preserved:** Retained the mandatory disclaimer:
     > *"Air quality data is provided as contextual delivery-planning information only. It does not constitute proof that a delivery is safe or unsafe."*

---

## 5. FLAGSMITH REAL SURGE SEMANTICS & MANAGEMENT API

### Surging Semantics
- **`surge_survival_mode` (Circuit Breaker):** Global operational mode. When active, non-critical workloads are shed and express delivery is strictly reserved for VIP festive buyers.
- **`express_delivery_enabled` (Feature Flag - ID `299380`):** Base delivery feature toggle.
- **`vip_festive_buyers` (Segment):** Targeted through identity trait `{"tier": "VIP"}`.

### Management API Verification
- `FlagsmithService.update_feature_state_remote`:
  - When `FLAGSMITH_ADMIN_API_KEY` is present, executes real HTTP PATCH against `https://api.flagsmith.com/api/v1/environments/{env_key}/feature-states/{feature_state_id}/`.
  - Performs read-after-write GET to confirm remote state update.
  - Reports `source: "flagsmith_remote_admin"`.
  - When admin key is absent, safely applies in-memory override with `source: "local_override"`.
  - Audit logs record source, operator details, and execution outcome in `audit_logs`.

---

## 6. KUBERNETES / NUDGEBEE TELEMETRY VS DEMO SIMULATION

### Distinction Clarity
- **`LIVE CLUSTER (utsavops-nudgebee)`:** Displayed on service cards when monitoring healthy k3s pods in namespace `nudgebee`.
- **`SIMULATED SURGE ANOMALY`:** Displayed when an operator triggers the "Simulate Diwali Surge Incident" button, generating a controlled p99 latency spike (4800ms) and CPU surge (98%).

### Gemini BYOM Root Cause Analysis
- Grounded RCA generated with `gemini_service.py` using model `gemini-flash-latest`.
- Displayed with explicit badge: `Model: gemini-flash-latest` alongside telemetry evidence pills (CPU utilization, p99 latency, error rate).
- Bounded, human-authorized mitigations allowlisted:
  1. `rate_limit_traffic`: Shed 30% of non-essential requests.
  2. `scale_replicas`: Scale `utsavops-checkout` from 3 to 6 replicas.
  3. `circuit_break_non_critical`: Activate Flagsmith surge mode to throttle newsletter workers.

---

## 7. PROVIDER BADGE TAXONOMY ACROSS FRONTEND

| Page | Integration | Provider Key | Status Displayed |
|---|---|---|---|
| **Dashboard** | Full Stack Overview | `sarvam_document_ai`, `flagsmith_live`, `google_address_validation`, `gemini_byom` | `LIVE` |
| **Order Intake** | Handwritten Chits & Voice | `sarvam_document_ai`, `sarvam_saaras_stt` | `LIVE` (with Fallback fallback indicator) |
| **Order Review** | Audio & Model Attribution | `sarvam_document_ai`, `sarvam_bulbul_tts` | `LIVE` |
| **Dispatch** | Address Validation & Geocoding | `google_address_validation` | `LIVE` / `FALLBACK` |
| **Dispatch** | Contextual Air Quality | `google_air_quality` | `LIVE` / `FALLBACK` |
| **VIP & Pricing** | Feature Flags & VIP Traits | `flagsmith_live` | `LIVE` / `LOCAL OVERRIDE` |
| **AIOps Center** | Autonomous RCA | `gemini_byom` | `LIVE` (`gemini-flash-latest`) |

---

## 8. DEMO SCRIPT & EVALUATION WALKTHROUGH

Judges and evaluators can follow this step-by-step walkthrough to evaluate UtsavOps:

### Step 1: Operator Authentication
1. Open [http://localhost:5173/login](http://localhost:5173/login) in your browser.
2. Observe the festive dark navy console with UtsavOps SRE branding.
3. Click **"Fill Demo"** button to auto-fill `admin@utsavops.internal` and default password.
4. Click **"Enter Operator Console"**.
5. Observe redirect to the main Dashboard; note the operator badge in the header: `UtsavOps Lead SRE (ADMIN)`.

### Step 2: Runtime Integrations on Dashboard
1. Inspect the "Verified Runtime Integrations" status bar displaying live statuses for Sarvam AI, Flagsmith, Google Cloud APIs, and NudgeBee + Gemini BYOM.
2. Review real-time KPI metrics for orders, VIP volume, and active services.

### Step 3: Multilingual Order Intake
1. Navigate to **Order Intake** (`/intake`).
2. Choose **Handwritten Chit** tab: upload a festive chit image (`demo_assets/samples/tamil_chit.jpg` or any image).
3. Click **Process Order Chit**: observe Sarvam Document AI extraction, showing customer name, delivery address, items, and confidence score without multiple-row errors.
4. Switch to **Regional Voice** tab: select Hindi (`hi-IN`) or Tamil (`ta-IN`) and upload an audio note. Observe Saaras v4 transcription.

### Step 4: Order Review & Bulbul Voice Confirmation
1. Navigate to **Order Review** (`/orders`).
2. Select any pending order: view extracted line items, prices, and VIP priority.
3. Click **"Voice Confirmation"**: hear the Sarvam Bulbul synthesized confirmation.
4. Click **"Approve Order"** to move the order to the dispatch pipeline.

### Step 5: Dispatch & Interactive AQI Refresh
1. Navigate to **Dispatch & Map** (`/dispatch`).
2. View Google Address Validation results, geocoded coordinates, and "Open in Maps" link.
3. Observe the **Contextual Air Quality Telemetry** card.
4. Click **"Refresh AQI"**: watch the button spin and refresh with current timestamp (`Last updated: ...`).
5. Verify the required air quality planning disclaimer is clearly visible.

### Step 6: VIP Segmentation & Flagsmith Surge Survival Mode
1. Navigate to **VIP & Pricing** (`/vip-pricing`).
2. Inspect customer tiers: toggle any customer's VIP status to see instantaneous rule updates.
3. Click **"Trigger Surge Survival Mode"**: confirm the modal dialog.
4. Note that Non-VIP express delivery is immediately shed while VIP express slots remain guaranteed.
5. Notice the system-wide Surge Banner active in the sidebar and dashboard.

### Step 7: AIOps Center — Chaos Surge & Gemini BYOM RCA
1. Navigate to **AIOps Center** (`/aiops`).
2. Inspect live workloads running on VM `utsavops-nudgebee`. Note the `LIVE CLUSTER (utsavops-nudgebee)` badges.
3. Click **"Simulate Diwali Surge Incident"**: checkout service transitions to `SIMULATED SURGE ANOMALY` with 4800ms latency.
4. Click **"NudgeBee / Gemini RCA"**: observe Gemini BYOM (`gemini-flash-latest`) analyze CPU and p99 latency evidence to identify root cause.
5. In the Bounded Mitigations panel, click **"Approve"** on the proposed mitigation.
6. Click **"Execute"**: mitigation is applied, activating circuit breakers and scaling workloads.
7. Click **"Verify Recovery"**: observe service health restored to 110ms healthy state.

---

## 9. VERIFICATION COMMAND LOGS

### 1. Backend Pytest Suite
```
cd backend && python3 -m pytest -v
============================= test session starts ==============================
collected 34 items

tests/test_aiops.py::test_aiops_incident_workflow PASSED                 [  2%]
tests/test_auth.py::test_auth_login_success PASSED                       [  5%]
tests/test_auth.py::test_auth_login_invalid_credentials PASSED           [  8%]
tests/test_auth.py::test_auth_me_with_valid_token PASSED                 [ 11%]
tests/test_auth.py::test_auth_me_without_token PASSED                    [ 14%]
tests/test_auth.py::test_auth_logout PASSED                              [ 17%]
tests/test_config_and_integrations.py::test_configuration_loading PASSED [ 20%]
tests/test_config_and_integrations.py::test_production_missing_variables_validation PASSED [ 23%]
tests/test_config_and_integrations.py::test_google_api_service_initialization PASSED [ 26%]
tests/test_config_and_integrations.py::test_google_address_validation_mock_fallback PASSED [ 29%]
tests/test_config_and_integrations.py::test_gemini_service_initialization PASSED [ 32%]
tests/test_config_and_integrations.py::test_gemini_byom_fallback_rca PASSED [ 35%]
tests/test_config_and_integrations.py::test_sarvam_service_initialization PASSED [ 38%]
tests/test_config_and_integrations.py::test_flagsmith_service_initialization PASSED [ 41%]
tests/test_config_and_integrations.py::test_nudgebee_configuration_validation PASSED [ 44%]
tests/test_config_and_integrations.py::test_database_health_probe PASSED [ 47%]
tests/test_customers.py::test_customer_lifecycle PASSED                  [ 50%]
tests/test_flagsmith_and_google.py::test_google_maps_dual_key_precedence PASSED [ 52%]
tests/test_flagsmith_and_google.py::test_google_apis_live_metadata PASSED [ 55%]
tests/test_flagsmith_and_google.py::test_google_air_quality_disclaimer_preserved PASSED [ 58%]
tests/test_flagsmith_and_google.py::test_flagsmith_vip_express_delivery_during_surge PASSED [ 61%]
tests/test_flagsmith_and_google.py::test_flagsmith_management_api_patch_success PASSED [ 64%]
tests/test_flagsmith_and_google.py::test_flagsmith_management_api_unauthorized_401 PASSED [ 67%]
tests/test_flagsmith_and_google.py::test_flagsmith_management_api_missing_key_fallback PASSED [ 70%]
tests/test_health.py::test_health_check PASSED                           [ 73%]
tests/test_health.py::test_readiness_check PASSED                        [ 76%]
tests/test_health.py::test_dashboard_stats PASSED                        [ 79%]
tests/test_order_intake_dedup.py::test_order_intake_duplicate_customer_prevention PASSED [ 82%]
tests/test_order_intake_dedup.py::test_order_intake_idempotency PASSED   [ 85%]
tests/test_orders.py::test_order_intake_and_approval PASSED              [ 88%]
tests/test_sarvam_doc_ai.py::test_sarvam_unconfigured_fallback PASSED    [ 91%]
tests/test_sarvam_doc_ai.py::test_sarvam_doc_ai_successful_job_workflow PASSED [ 94%]
tests/test_sarvam_doc_ai.py::test_sarvam_doc_ai_failed_job PASSED        [ 97%]
tests/test_sarvam_doc_ai.py::test_sarvam_doc_ai_timeout_handling PASSED  [100%]
======================== 34 passed, 2 warnings in 0.55s ========================
```

### 2. Frontend Production Build
```
cd frontend && npm run build
> utsavops-frontend@1.0.0 build
> vite build
✓ 2170 modules transformed.
dist/index.html                   0.67 kB │ gzip:   0.45 kB
dist/assets/index-BBMqXWeh.css   43.40 kB │ gzip:   7.78 kB
dist/assets/index-DE8LJS97.js   355.08 kB │ gzip: 104.03 kB
✓ built in 1.19s
```

### 3. Cloud SQL PostgreSQL Health & Deduplication
- Database connected: `35.234.219.215:5432/utsavops`
- Customer phone duplicate count: `0`
- `uq_customers_phone` unique index: active and verified
- Operators table verified and seeded: `admin@utsavops.internal`

---

## 10. CONCLUSION & READINESS STATEMENT

Phase 2B is 100% complete and verified. The codebase is clean, robust, and protected against secret leakage. The system is ready for immediate live evaluation and demonstration for Festive Hacks 2026.

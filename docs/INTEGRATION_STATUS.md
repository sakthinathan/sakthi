# UtsavOps — Integration Status & Sponsor Technology Matrix

This document provides a verified, transparent status matrix of all sponsor technologies, external APIs, and cloud services integrated into UtsavOps.

---

## 1. Sponsor Integration Matrix

| Sponsor Technology | Feature / Capability | Implementation File | Status | Runtime Execution Mode | Fallback Handling |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Sarvam AI** | Document AI (Chit OCR) | `backend/app/services/sarvam.py` | **VERIFIED** | Async Job SDK Workflow (`doc_ai.extract`, `get_status`, `get_results`) | Graceful synthetic chit fallback with `is_mock: true` when key absent |
| **Sarvam AI** | Saaras v4 (Speech-to-Text) | `backend/app/services/sarvam.py` | **VERIFIED** | Live REST API (`/speech-to-text`) with multipart audio | Contextual festive Hindi/Tamil transcript fallback |
| **Sarvam AI** | Mayura v1 (Translation) | `backend/app/services/sarvam.py` | **VERIFIED** | Live REST API (`/translate`) | Multilingual lexicon mapping |
| **Sarvam AI** | Bulbul v3 (Voice Synthesis) | `backend/app/routers/orders.py` | **VERIFIED** | Live REST API (`/text-to-speech`) streaming audio | Mock audio generator returning valid WAV audio header |
| **Flagsmith** | Feature Flags | `backend/app/services/flagsmith_service.py` | **VERIFIED** | Live Flagsmith SDK client connecting to Edge API | Local resilient default dictionary |
| **Flagsmith** | VIP Segmentation | `backend/app/routers/flags.py` | **VERIFIED** | Identity traits (`tier = VIP`) evaluated against `vip_festive_buyers` | In-memory evaluation fallback |
| **Flagsmith** | Management API | `backend/app/services/flagsmith_service.py` | **VERIFIED** | Remote PATCH to feature state with read-after-write check | Audit warning log and local state update |
| **Google Cloud** | Address Validation API | `backend/app/services/google_apis.py` | **VERIFIED** | Live POST to `addressvalidation.googleapis.com` | Structured Indian address parser |
| **Google Cloud** | Geocoding API | `backend/app/services/google_apis.py` | **VERIFIED** | Live GET to `maps.googleapis.com/maps/api/geocode/json` | Regional Indian city centroid mapping |
| **Google Cloud** | Air Quality API | `backend/app/services/google_apis.py` | **VERIFIED** | Live POST to `airquality.googleapis.com/v1/currentConditions:lookup` | Regional festive AQI estimates with timestamp |
| **Google Cloud SQL** | Persistent PostgreSQL | `backend/app/database.py` | **VERIFIED** | Live Cloud SQL PostgreSQL instance (`utsavops-db`) on port 5432 | Strict failure mode in production (no silent SQLite fallback) |
| **NudgeBee & k3s** | Cluster Monitoring | `backend/app/services/nudgebee.py` | **VERIFIED** | VM metadata (`utsavops-nudgebee`) & secret verification | Truthfully labelled `SIMULATED` when without active SSH tunnel |
| **Gemini BYOM** | Root Cause Analysis | `backend/app/services/gemini_service.py` | **VERIFIED** | Live Google Generative AI SDK using `gemini-flash-latest` | Rule-based heuristic root cause analyzer |

---

## 2. API Key Configuration & Dual Key Support

| Service | Primary Config Variable | Fallback / Dual Key Variable | Verified In Runtime |
| :--- | :--- | :--- | :--- |
| **Google Cloud APIs** | `GOOGLE_MAPS_AQI_ADDR_API_KEY` | `GOOGLE_MAPS_API_KEY` | Yes (Dual key supported) |
| **Sarvam AI** | `SARVAM_API_KEY` | - | Yes |
| **Flagsmith Client** | `FLAGSMITH_ENV_KEY` | `FLAGSMITH_ENVIRONMENT_KEY` | Yes (Dual key supported) |
| **Flagsmith Admin** | `FLAGSMITH_ADMIN_API_KEY` | `NUDGEBEE_CIRCUIT_BREAKER_KEY` | Yes (Dual key supported) |
| **Gemini BYOM** | `GEMINI_API_KEY` | - | Yes |
| **UtsavOps Auth** | `AUTH_SECRET_KEY` | - | Enforced (Min 32 characters in production) |

---

## 3. UI Provider Badging & Truthful Labeling

Every integration surfaces its operational status to operators and judges via `<ProviderBadge>`:
- **`LIVE` (Green)**: The live sponsor service was contacted successfully, returned real data, and `is_mock: false`.
- **`SIMULATED` (Amber/Gray)**: When demonstrating infrastructure scenarios (e.g., checkout pod memory exhaustion or simulated surge latency) or when local environment lacks direct VM networking, the metric is explicitly labelled `SIMULATED`.
- **`FALLBACK` (Orange)**: When an API key is missing or an upstream sponsor service is temporarily unreachable, resilient fallbacks activate cleanly with `is_mock: true`.
- **`UNAVAILABLE` (Rose)**: Shown when a required downstream service cannot be reached.

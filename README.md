# 🪔 UtsavOps — The Self-Healing AI Operating System for India's Festive Commerce

> **Festive Hacks 2026** | Multi-Agent End-to-End Autonomous Festive Operating System

[![Tests](https://img.shields.io/badge/tests-40%20passed-emerald)](./backend/tests)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61dafb)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.0-646cff)](https://vitejs.dev)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-v4-38bdf8)](https://tailwindcss.com)

---

## 1. The Real-World Problem

During Diwali, Dussehra, Pongal, and Ganesh Chaturthi, local Indian sweet shops, gift retailers, and festive merchants experience sudden **10x to 25x surges in incoming orders**. 

Orders do not arrive through clean e-commerce checkouts. Instead, they arrive as:
- **Handwritten paper slips and chits** scribbled over shop counters in regional dialects.
- **WhatsApp voice notes** in Hindi, Tamil, Telugu, and Kannada.
- **Urgent phone calls** requesting immediate festive gift packing and deliveries.

Small retailers face two catastrophic bottlenecks:
1. **Business Intelligence Failure**: Inability to transcribe regional handwriting/audio, normalize product catalogs (e.g., Kaju Katli, Mysore Pak), validate vague Indian addresses, and prioritize high-value VIP buyers over surge crowds.
2. **Infrastructure Collapse**: Sudden burst traffic crashes online checkout services, causing delivery failures, stock misallocations, and revenue loss during their most critical annual business window.

---

## 2. The Solution: UtsavOps

**UtsavOps** transforms chaotic festive commerce into an orderly, self-healing operation with dual intelligence:

1. **Order Intelligence (Sarvam AI)**:
   - **Sarvam Document AI**: OCRs handwritten festive order chits into structured JSON line items.
   - **Saaras v4**: Transcribes multilingual festive voice notes.
   - **Mayura v1**: Translates and normalizes regional item names.
   - **Bulbul v3**: Synthesizes regional voice confirmations back to customers.
   - **Human-In-The-Loop Cockpit**: Operators review, edit, approve, or reject orders before final booking.

2. **VIP Business Rules (Flagsmith)**:
   - Dynamic evaluation of the `vip_festive_buyers` segment.
   - **Surge Survival Mode**: Server-side enforced load shedding during peak hours — VIPs retain express delivery slots while non-VIP orders shift to standard queues.
   - Real-time dynamic bundle pricing and AI routing control.

3. **Self-Healing Infrastructure (NudgeBee, Gemini BYOM & Kubernetes)**:
   - Detects degradation on `utsavops-checkout` (p99 latency spikes, pod memory exhaustion).
   - Gemini BYOM performs telemetry-grounded Root Cause Analysis (RCA).
   - Recommends bounded, allowlisted mitigations requiring human approval.
   - Verifies recovery and restores temporary cluster workloads.

4. **Dispatch Intelligence (Google APIs)**:
   - **Google Address Validation API**: Standardizes and validates addresses.
   - **Google Geocoding API**: Resolves high-precision lat/long coordinates.
   - **Google Air Quality API**: Surfaces contextual AQI telemetry for rider delivery planning.

---

## 3. High-Level Architecture

```
                                  UTSAVOPS ARCHITECTURE
                                  
   [ Handwritten Chit ]    [ Voice Note ]          [ Festive Operator Cockpit ]
           │                     │                              │
           ▼                     ▼                              ▼
    Sarvam Document AI     Sarvam Saaras v4              React 19 + Vite + Tailwind
           │                     │                              │
           └──────────┬──────────┘                              │
                      ▼                                         │
             Mayura Translation                                 │
                      │                                         │
                      ▼                                         ▼
            FastAPI Asynchronous Gateway  ◄───────────────  REST / JSON
            ├── /api/orders (Intake, Review, Bulbul Voice)
            ├── /api/flags (Flagsmith SDK & Surge Rule Engine)
            ├── /api/dispatch (Google Address Validation & AQI)
            ├── /api/aiops (NudgeBee & Gemini BYOM Incident SRE)
            └── /api/audit (Immutable Observability Log)
                      │
                      ├── SQLAlchemy 2.0 Async ──► PostgreSQL (Google Cloud SQL) / SQLite
                      │
                      ├── Flagsmith Edge API (Live Segments & Surge Survival Mode)
                      │
                      └── Kubernetes (k3s Cluster: utsavops-checkout & newsletter-worker)
```

---

## 4. Sponsor Technologies & Implementations

| Sponsor | Feature | Implementation in UtsavOps | Location |
|---------|---------|----------------------------|----------|
| **Sarvam AI** | Document AI | Handwritten festive chit OCR & line-item extraction | `backend/app/services/sarvam.py` |
| **Sarvam AI** | Saaras v4 | Regional speech-to-text for WhatsApp voice notes | `backend/app/services/sarvam.py` |
| **Sarvam AI** | Mayura v1 | Multilingual translation & catalog normalization | `backend/app/services/sarvam.py` |
| **Sarvam AI** | Bulbul v3 | Audio voice confirmation generated for customer | `backend/app/routers/orders.py` |
| **Flagsmith** | Feature Flags | Live evaluation of `surge_survival_mode`, `express_delivery_enabled`, `festive_bundle_price` | `backend/app/services/flagsmith_service.py` |
| **Flagsmith** | Segments | `vip_festive_buyers` priority rules (server-side enforced) | `backend/app/routers/flags.py` |
| **Google Cloud** | Address Validation | Street address verification and granularity checks | `backend/app/services/google_apis.py` |
| **Google Cloud** | Geocoding | Coordinate resolution for map routing | `backend/app/services/google_apis.py` |
| **Google Cloud** | Air Quality | Contextual delivery planning AQI metrics | `backend/app/services/google_apis.py` |
| **NudgeBee & Gemini** | AIOps & BYOM | SRE anomaly detection, evidence-backed RCA, allowlisted mitigations | `backend/app/services/nudgebee.py` |
| **Kubernetes** | Orchestration | Declarative k3s manifests with health probes | `k8s/` |

---

## 5. Quick Start Instructions

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Node.js 18+ (tested on Node v24)
- npm 9+

### 1. Clone & Set Up
```bash
git clone https://github.com/sakthinathan/sakthi.git
cd sakthi

# Setup .env and frontend dependencies
make setup
```

### 2. Seed Festive Demo Data
```bash
make seed
```

### 3. Run Test Suite
```bash
make test
```
*Expected: 40/40 pytest tests passing in < 0.9s.*

---

## 4.5. Comprehensive Documentation Suite

For judges, operators, and engineers, in-depth documentation is available in the [`docs/`](./docs) directory:

- 📐 [Architecture Specification](./docs/ARCHITECTURE.md)
- 📊 [Architecture Diagrams & Sequence Flows](./docs/ARCHITECTURE_DIAGRAM.md)
- 🔌 [Integration Status & Sponsor Technology Matrix](./docs/INTEGRATION_STATUS.md)
- 🚀 [Deployment & Production Run Guide](./docs/DEPLOYMENT_GUIDE.md)
- 🎬 [Judge Demo Walkthrough & Script](./docs/DEMO_WALKTHROUGH.md)
- 🛡️ [Security Review & Hardening Audit](./docs/SECURITY_REVIEW.md)
- ⚠️ [Known Limitations & Engineering Disclosures](./docs/KNOWN_LIMITATIONS.md)
- 📋 [Master Final Implementation Report](./docs/FINAL_IMPLEMENTATION_REPORT.md)

---

### 4. Start the Application

In Terminal 1 (Backend on `http://localhost:8000`):
```bash
make backend
```

In Terminal 2 (Frontend on `http://localhost:5173`):
```bash
make frontend
```

Open `http://localhost:5173` in your browser.

---

## 6. End-to-End Demo Workflow Guide

Follow this 5-minute walkthrough to demonstrate all sponsor integrations:

### Step 1: Multilingual Order Intake (Sarvam AI)
1. Navigate to **Order Intake** (`/intake`).
2. Upload a sample festive chit image or click **Analyze Order with Sarvam AI**.
3. Watch Sarvam Document AI extract customer details, address, and line items (Kaju Katli, Motichoor Laddu) with confidence scores.
4. Switch to the **Voice Note Order** tab, select **Hindi (हिन्दी)** or **Tamil (தமிழ்)**, and analyze a voice order via Saaras v4.

### Step 2: Human-in-the-Loop Review & Bulbul Voice Confirmation
1. Navigate to **Order Review** (`/orders`).
2. Select any pending order.
3. Click **Edit Information** to adjust items or special packaging instructions.
4. Click **Voice Confirmation** to listen to the synthesized Bulbul v3 confirmation audio in Hindi.
5. Click **Approve Order** — notice how VIP rules automatically elevate the customer's priority.

### Step 3: Dispatch & Google Address Validation
1. Navigate to **Dispatch & Map** (`/dispatch`).
2. Select an approved order and click **Validate Address**.
3. Google Address Validation verifies postal granularity, resolves lat/long coordinates, and displays contextual Air Quality (AQI) metrics.

### Step 4: Flagsmith Business Rules & Surge Survival Mode
1. Navigate to **VIP & Pricing** (`/vip-pricing`).
2. Observe active Flagsmith flags (`festive_bundle_price`, `express_delivery_enabled`).
3. Toggle customer VIP status to see instantaneous trait updates.
4. Click **Trigger Surge Survival Mode** — notice that express delivery slots are strictly protected for VIP festive buyers, while standard load is gracefully shed.

### Step 5: Operational Incident & Self-Healing (NudgeBee + Gemini BYOM)
1. Navigate to **AIOps Center** (`/aiops`).
2. Click **Simulate Diwali Surge Incident**.
3. Watch `utsavops-checkout` health degrade to 4800ms p99 latency with 98% CPU contention.
4. Click **NudgeBee / Gemini RCA** to trigger evidence-grounded root-cause analysis.
5. Review the proposed allowlisted mitigations:
   - Toggle Flagsmith Surge Survival Mode
   - Autoscale checkout pods to 5
   - Pause non-critical `newsletter-worker`
6. Click **Approve** and then **Execute** for the mitigation.
7. Click **Verify Checkout Recovery** — observe latency immediately recover to a healthy 110ms.
8. Navigate to **Audit Log** (`/audit`) to view the tamper-evident record of all actions taken.

---

## 7. Real vs. Simulated Integrations Disclosure

In compliance with the Festive Hacks 2026 hackathon standards:

| Integration | Real Implementation | Labeled Fallback Mode |
|-------------|---------------------|-----------------------|
| **Sarvam Document AI** | Real `sarvamai` SDK async-job workflow (`doc_ai.extract` -> poll `get_status` -> `get_results`) with strict JSON schema | Labelled festive Indian sweets catalog extraction with `is_mock: true` and `status: "fallback"` |
| **Sarvam Saaras v4** | Real multipart HTTP upload to `api.sarvam.ai/speech-to-text` | Synthetic regional Hindi/Tamil audio transcription with `is_mock: true` |
| **Sarvam Mayura v1** | Real HTTP call to `api.sarvam.ai/translate` | Local language normalizer |
| **Sarvam Bulbul v3** | Real TTS HTTP call to `api.sarvam.ai/text-to-speech` (speakers: ritu, aditya, ashutosh, priya) | Synthesized valid WAV audio stream |
| **Flagsmith** | Real Python SDK client querying Flagsmith Edge API with `vip_festive_buyers` identity traits (`tier: VIP`) | Local resilient rule engine with identical evaluation semantics |
| **Flagsmith Management API** | Real HTTP PATCH against `api.flagsmith.com/api/v1/environments/{key}/feature-states/` using `FLAGSMITH_ADMIN_API_KEY` | Explicit local override reporting `source: "local_override"` |
| **Google Address Validation & Geocoding** | Real Google Cloud API requests (`GOOGLE_MAPS_AQI_ADDR_API_KEY` or `GOOGLE_MAPS_API_KEY`) | Explicitly labelled fallback coordinates (Malleshwaram Bengaluru coordinates) with `is_mock: true` |
| **Google Air Quality API** | Real Google Air Quality lookup (`currentConditions:lookup`) | Contextual AQI telemetry with mandatory safety disclaimer preserved |
| **NudgeBee & Gemini BYOM** | Real Gemini Generative Language API calls (`gemini-flash-latest`, `gemini-flash-lite-latest`) | Grounded evidence-based SRE rule engine |
| **Kubernetes (k3s)** | Live k3s cluster running on GCP VM `utsavops-nudgebee` with active `utsavops` workloads | In-memory cluster telemetry state for standalone local tests |

---

## 8. AI-Assisted Development Disclosure

Developed using autonomous multi-agent orchestration via Antigravity, coordinating specialized software architecture, order intelligence, backend database, feature flag management, and site reliability engineering agents.

---

## 9. License

MIT License — Festive Hacks 2026.

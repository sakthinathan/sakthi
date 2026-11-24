# UtsavOps — Complete Architecture Diagram

## 1. End-to-End System Architecture

```mermaid
flowchart TD
    subgraph Client ["Client Layer (Browser / Mobile)"]
        UI["React 19 Frontend<br/>(Vite 6 + TailwindCSS v4)"]
        AuthCtx["Auth Context & Token Storage"]
        Badge["ProviderBadges (Live / Simulated / Fallback)"]
    end

    subgraph Gateway ["Application Gateway (FastAPI)"]
        RouterAuth["/api/auth (JWT + Rate Limit + Blacklist)"]
        RouterOrders["/api/orders (Intake, Voice, Review)"]
        RouterFlags["/api/flags (Surge Mode & Segments)"]
        RouterDispatch["/api/dispatch (Address, Geocode, AQI)"]
        RouterAIOps["/api/aiops (NudgeBee & Incident SRE)"]
        RouterAudit["/api/audit (Immutable Audit Trail)"]
    end

    subgraph AuthLayer ["Security & RBAC"]
        AuthSecret["AUTH_SECRET_KEY (HMAC-SHA256)"]
        RateLimiter["Sliding Window Rate Limiter (5 / 5 min)"]
        TokenBlacklist["Token Revocation Cache & DB"]
    end

    subgraph Sponsors ["Sponsor & Cloud Integrations"]
        subgraph SarvamAI ["Sarvam AI Suite"]
            DocAI["Document AI (Async SDK Chit OCR)"]
            Saaras["Saaras v4 (Multilingual STT)"]
            Mayura["Mayura v1 (Catalog Translation)"]
            Bulbul["Bulbul v3 (Multilingual Voice TTS)"]
        end

        subgraph FlagsmithService ["Flagsmith Service"]
            FlagsEdge["Flagsmith Edge API (Flags & Traits)"]
            FlagsMgmt["Flagsmith Management API (Remote Patch)"]
        end

        subgraph GoogleCloud ["Google Cloud APIs"]
            AddrVal["Address Validation API"]
            Geocoding["Geocoding API"]
            AQI["Air Quality API"]
        end

        subgraph BYOM ["AI AIOps & BYOM"]
            Gemini["Gemini BYOM (gemini-flash-latest RCA)"]
            NudgeBeeSvc["NudgeBee Telemetry & VM Metadata"]
        end
    end

    subgraph Storage ["Authoritative Data Layer"]
        CloudSQL[("Google Cloud SQL PostgreSQL<br/>utsavops-db:5432 (Authoritative)")]
        LocalDB[("Local SQLite (Testing Only)")]
    end

    subgraph Infra ["Kubernetes Cluster (utsavops-nudgebee VM)"]
        K8sCheckout["Deployment: utsavops-checkout (Tier: Critical)"]
        K8sWorker["Deployment: newsletter-worker (Tier: Low)"]
        K8sSecret["Secret: flagsmith_api_key"]
    end

    UI --> RouterAuth
    UI --> RouterOrders
    UI --> RouterFlags
    UI --> RouterDispatch
    UI --> RouterAIOps
    UI --> RouterAudit

    RouterAuth --> RateLimiter
    RouterAuth --> TokenBlacklist
    RouterAuth --> AuthSecret

    RouterOrders --> DocAI
    RouterOrders --> Saaras
    RouterOrders --> Mayura
    RouterOrders --> Bulbul

    RouterFlags --> FlagsEdge
    RouterFlags --> FlagsMgmt

    RouterDispatch --> AddrVal
    RouterDispatch --> Geocoding
    RouterDispatch --> AQI

    RouterAIOps --> Gemini
    RouterAIOps --> NudgeBeeSvc
    RouterAIOps --> K8sCheckout
    RouterAIOps --> K8sWorker

    Gateway --> CloudSQL
```

---

## 2. Order Intake & Sarvam Multilingual Processing Flow

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer / Shopkeeper
    actor Operator as Store Operator
    participant UI as UtsavOps UI
    participant Backend as FastAPI Gateway
    participant Sarvam as Sarvam AI APIs
    participant DB as Cloud SQL PostgreSQL

    alt Handwritten Chit
        Operator->>UI: Uploads handwritten paper slip (JPG/PNG)
        UI->>Backend: POST /api/orders/intake/chit
        Backend->>Sarvam: client.doc_ai.extract(file, schema)
        loop Polling Status
            Backend->>Sarvam: client.doc_ai.get_status(job_id)
        end
        Sarvam-->>Backend: client.doc_ai.get_results(job_id)
    else Multilingual Voice Note
        Customer->>UI: Submits audio recording (Hindi/Tamil)
        UI->>Backend: POST /api/orders/intake/voice
        Backend->>Sarvam: Saaras v4 STT (Audio -> Regional Text)
        Backend->>Sarvam: Mayura v1 Translation (Regional -> Normalized English)
    end

    Backend->>DB: Persist Order as 'pending_review'
    Backend-->>UI: Return parsed order line items
    Operator->>UI: Review & approve items in Order Review cockpit
    UI->>Backend: POST /api/orders/{id}/approve
    Backend->>DB: Update order status to 'confirmed'
    UI->>Backend: GET /api/orders/{id}/voice-confirmation
    Backend->>Sarvam: Bulbul v3 TTS (Festive voice confirmation)
    Sarvam-->>Backend: Audio stream (WAV/MP3)
    Backend-->>UI: Play voice confirmation to operator/customer
```

---

## 3. Incident Detection & Gemini BYOM Self-Healing Flow

```mermaid
sequenceDiagram
    autonumber
    actor SRE as SRE Operator / NudgeBee
    participant UI as AIOps Center
    participant Gateway as FastAPI Backend
    participant Gemini as Gemini BYOM
    participant Flagsmith as Flagsmith API
    participant K8s as k3s Cluster (utsavops-nudgebee)

    SRE->>UI: Anomaly detected (p99 latency > 4800ms)
    UI->>Gateway: POST /api/aiops/services/{svc}/simulate-degradation
    Gateway-->>UI: Incident Created (Severity: Critical)
    
    UI->>Gateway: POST /api/aiops/incidents/{id}/investigate
    Gateway->>Gemini: Prompt with cluster telemetry + topology
    Gemini-->>Gateway: Root Cause Analysis + Allowlisted Mitigations
    Gateway-->>UI: Structured RCA & Recommended Actions
    
    SRE->>UI: Approves Mitigation: "Scale checkout + shed newsletter worker"
    UI->>Gateway: POST /api/aiops/incidents/{id}/actions/{act_id}/approve
    UI->>Gateway: POST /api/aiops/incidents/{id}/actions/{act_id}/execute
    
    Gateway->>K8s: Bounded remediation (scale checkout, pause background worker)
    Gateway->>Flagsmith: Activate surge mode trait via Management API
    Gateway-->>UI: Execution confirmation logged in AuditLog
    
    UI->>Gateway: POST /api/aiops/incidents/{id}/verify-recovery
    Gateway-->>UI: Latency restored to 110ms (Recovery Verified)
```

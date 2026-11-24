# UtsavOps — Known Limitations & Honest Disclosures

To ensure transparency with hackathon judges and operators, this document outlines known limitations, simulation boundaries, and operational considerations.

---

## 1. Kubernetes & Infrastructure Telemetry

- **SSH Tunnel Requirement for Live k3s Telemetry**:
  - The k3s cluster and NudgeBee agent run on the Google Compute Engine VM `utsavops-nudgebee`.
  - When the local backend runs on a developer workstation without an active SSH tunnel (`gcloud compute ssh utsavops-nudgebee -- -L 6443:localhost:6443`), the system cannot directly query `kubectl` or the in-cluster metrics server.
  - In this state, the backend honestly reports cluster status as `SIMULATED TELEMETRY (utsavops-nudgebee)`. No fake live metrics are displayed.
- **Simulated Degradation vs Actual Node Failure**:
  - The **Simulate Diwali Surge Incident** button injects a realistic p99 latency spike (4800ms) and CPU exhaustion into the service monitor to demonstrate Gemini BYOM RCA and automated mitigation workflows without permanently crashing the physical VM.

---

## 2. Audio & Speech Processing

- **Browser Audio Autoplay Policies**:
  - Modern web browsers (Chrome, Safari) restrict programmatic audio playback without prior user gesture. Bulbul v3 voice confirmation is initiated on explicit user click ("Play Voice Confirmation").
- **Regional Dialect Breadth**:
  - Saaras v4 and Mayura v1 provide robust support for Hindi and Tamil. Regional colloquialisms outside standard festive vocabulary are normalized using phonetic fallback mapping.

---

## 3. Rate Limiting & Scalability

- **In-Memory Rate Limiting Cache**:
  - The sliding-window rate limiter (5 failed attempts per 300s) uses an in-memory deque cache with database persistence for revocations. In a multi-worker production cluster behind a load balancer, this should be backed by Redis.
- **Sarvam Document AI Job Timeout**:
  - The async polling workflow uses a 60-second polling timeout with exponential backoff. Highly degraded, noisy, or blurry paper chits may trigger a timeout and fall back to the synthetic chit parser with `is_mock: true`.

---

## 4. Google Cloud APIs

- **Air Quality API Availability**:
  - Google Air Quality API provides coverage across major Indian metropolitan areas (Bangalore, Mumbai, Delhi, Chennai). For rural tier-3 coordinates where AQI monitoring stations are absent, the API falls back to regional zonal estimates with an explicit timestamped disclaimer.

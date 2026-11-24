# UtsavOps — Hackathon Demo Walkthrough & Script

Follow this step-by-step judge demonstration script to showcase all sponsor technologies and the full self-healing workflow.

---

## Act 1: The Operator Login & Festive Dashboard (2 Minutes)

1. **Navigate to the Login Page (`http://localhost:5173/login`)**:
   - Point out the security and rate limiting controls.
   - Enter credentials for the lead administrator:
     - Username: `admin`
     - Password: `utsavops@2026`
   - Click **Sign In to Cockpit**.
2. **Dashboard Overview**:
   - Highlight the **Verified Runtime Integrations** badge bar:
     - `Sarvam AI` (Live)
     - `Flagsmith` (Live)
     - `Google Cloud APIs` (Live)
     - `NudgeBee + Gemini BYOM` (Live)
   - Show real-time KPI metrics: Total Orders, Pending Review, Confirmed, and Active Incidents.

---

## Act 2: Multilingual Order Intake & Sarvam AI (3 Minutes)

1. **Navigate to Order Intake (`/intake`)**:
   - Click on the **Handwritten Chit** tab.
   - Upload sample chit: `demo_assets/diwali_chit_sample.jpg` (or click **Load Sample Chit**).
   - Click **Extract Line Items via Sarvam Document AI**.
   - Watch the Document AI async-job workflow poll and extract:
     - Customer: `Ananya Sharma`
     - Address: `Indiranagar, Bangalore`
     - Items: `Kaju Katli (1 kg)`, `Motichoor Ladoo (500g)`, `Mysore Pak (1 kg)`
2. **Multilingual Voice Note Intake**:
   - Switch to the **Voice Note** tab.
   - Select regional language: `Tamil` or `Hindi`.
   - Upload `demo_assets/tamil_voice_order.wav` (or load sample audio).
   - Click **Transcribe & Translate (Saaras v4 + Mayura v1)**.
   - Show how regional colloquial speech is transcribed and catalog-normalized into English line items.
3. **Submit Order**:
   - Click **Submit Order to Review Queue**. Notice the clean, responsive inline loading state.

---

## Act 3: Order Review & Bulbul v3 Voice Confirmation (2 Minutes)

1. **Navigate to Order Review (`/orders`)**:
   - Select the newly ingested order from the queue.
   - Show item inspection, price recalculation, and operator line item adjustments.
   - Click **Approve Order**.
2. **Bulbul v3 Audio Voice Confirmation**:
   - Click **Play Voice Confirmation (Bulbul v3)**.
   - The browser streams synthesized festive audio confirming the order in the customer's preferred language.

---

## Act 4: Dispatch, Google Address Validation & AQI (2 Minutes)

1. **Navigate to Dispatch & Map (`/dispatch`)**:
   - Select the approved order.
   - Click **Validate Address**.
   - Show the green **Google Address Validation** badge verifying street-level granularity.
   - Show resolved GPS latitude and longitude from the **Google Geocoding API**.
   - Inspect the **Google Air Quality API** section:
     - Shows live AQI rating (e.g., AQI 168 - Moderate / Unhealthy for Sensitive Groups).
     - Delivery rider advisory: *"High particulate matter during Diwali fireworks. Prioritize closed EV delivery vans."*
     - Verified timestamp and mandatory data disclaimer.

---

## Act 5: Surge Mode & Flagsmith VIP Segmentation (2 Minutes)

1. **Navigate to VIP & Pricing (`/vip-pricing`)**:
   - Review the customer list. Find `Rajesh Patel` and toggle his VIP badge.
   - Explain the Flagsmith segment: Identity trait `tier = VIP` qualifies him for `vip_festive_buyers`.
2. **Activate Surge Survival Mode**:
   - Click **Toggle Surge Mode**.
   - The confirmation modal warns: *"During peak festive traffic, this strictly restricts express delivery slots to verified VIP festive buyers to protect checkout stability."*
   - Confirm activation.
   - Observe the immediate remote PATCH to Flagsmith Management API, server-side rule update, and glowing orange surge banner appearing across the entire application.

---

## Act 6: Incident Detection & Gemini BYOM Self-Healing (3 Minutes)

1. **Navigate to AIOps Center (`/aiops`)**:
   - Inspect the two monitored services:
     - `utsavops-checkout` (Tier: Critical)
     - `newsletter-worker` (Tier: Low)
2. **Simulate Festive Burst**:
   - Click **Simulate Diwali Surge Incident**.
   - Checkout p99 latency spikes to 4800ms, CPU surges to 98%, and status turns degraded.
3. **Investigate with Gemini BYOM**:
   - Select the generated incident.
   - Click **Investigate with Gemini BYOM**.
   - Gemini models root-cause analysis based on telemetry: identifies thread pool exhaustion caused by concurrent database queries during the festive rush.
   - Gemini recommends strictly bounded mitigations:
     1. Scale `utsavops-checkout` replicas from 3 to 6.
     2. Shed background traffic: Pause `newsletter-worker`.
     3. Enable Flagsmith surge mode for rate throttling.
4. **Human-in-the-Loop Approval & Execution**:
   - Click **Approve Action** as Lead SRE.
   - Click **Execute Bounded Mitigation**.
   - Click **Verify Recovery**.
   - Status updates: p99 latency drops to 110ms, recovery is verified!
5. **Inspect Audit Log (`/audit`)**:
   - Show the immutable chronological log capturing the human operator approval, action execution, and recovered state.

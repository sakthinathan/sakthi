# UtsavOps — Complete Deployment & Run Guide

This guide covers local development, Docker Compose staging, Cloud SQL database connectivity, and Kubernetes deployment on the NudgeBee virtual machine.

---

## 1. Prerequisites

- **Python**: 3.11+ (Python 3.13 recommended)
- **Node.js**: 20+ (Node 24 recommended)
- **Docker & Docker Compose**: v2.20+
- **Google Cloud SDK (`gcloud`)**: Authenticated with project `festive-hacks-2026`
- **Kubernetes CLI (`kubectl`)**: Configured or tunneled to the k3s cluster

---

## 2. Local Development Setup

### A. Environment Configuration
Create your local environment file:
```bash
cp .env.example .env
```
Ensure all required keys are filled in. In development mode (`APP_ENV=development`), SQLite is used by default if `DATABASE_URL` points to SQLite. For production testing, provide the Cloud SQL PostgreSQL connection URL.

### B. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The FastAPI backend will start at `http://localhost:8000`. Swagger API documentation is available at `http://localhost:8000/docs`.

### C. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The React 19 frontend will start at `http://localhost:5173`.

---

## 3. Database Seeding & Migrations

The database models are auto-created on application startup via SQLAlchemy. To initialize default test operators and seed data:
```bash
cd backend
python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
```

Default Operator Credentials:
| Username | Password | Role | Description |
| :--- | :--- | :--- | :--- |
| `admin` | `utsavops@2026` | `admin` | Full administrator with surge toggle and mitigation execution privileges |
| `sre_lead` | `srelead@2026` | `sre_lead` | SRE operator with AIOps incident mitigation approval authority |
| `operator` | `operator@2026` | `operator` | Standard festive intake and order review operator |

---

## 4. Docker Compose Deployment

To build and run both backend and frontend containers locally:
```bash
docker compose up --build -d
```
Check container logs:
```bash
docker compose logs -f backend
```
Access the application:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

---

## 5. Kubernetes & NudgeBee Cluster Setup

The k3s cluster is hosted on the Google Compute Engine virtual machine `utsavops-nudgebee`.

### A. Connect via SSH Tunnel
```bash
gcloud compute ssh utsavops-nudgebee --zone=asia-south1-a -- -L 6443:localhost:6443 -L 3000:localhost:3000
```

### B. Apply Kubernetes Manifests
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/utsavops-checkout.yaml
kubectl apply -f k8s/newsletter-worker.yaml
```

### C. Verify Cluster Resources
```bash
kubectl get pods -n utsavops
kubectl get svc -n utsavops
```

### D. NudgeBee Dashboard Access
Access the live NudgeBee UI through the SSH port-forward tunnel:
```
http://localhost:3000
```

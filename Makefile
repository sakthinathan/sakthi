.PHONY: help setup dev backend frontend test seed build smoke clean

help:
	@echo "UtsavOps — Makefile commands:"
	@echo "  make setup     - Set up environment and install frontend dependencies"
	@echo "  make seed      - Populate database with festive demo data"
	@echo "  make test      - Run backend pytest test suites"
	@echo "  make smoke     - Run live sponsor integrations runtime audit"
	@echo "  make backend   - Run FastAPI server on port 8000"
	@echo "  make frontend  - Run Vite dev server on port 5173"
	@echo "  make dev       - Run tests and seed database"
	@echo "  make build     - Build frontend production distribution"

setup:
	cp -n .env.example .env || true
	cd frontend && npm install

seed:
	cd backend && python3 -m app.seed

test:
	cd backend && python3 -m pytest -v

smoke:
	python3 scripts/smoke_test_integrations.py

backend:
	cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

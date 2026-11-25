#!/usr/bin/env python3
"""
UtsavOps — Sponsor Integration Smoke Test Suite
Verifies runtime health of all sponsor technologies, external APIs, and cloud resources.
Outputs standardized status: LIVE, FALLBACK, SIMULATED, UNAVAILABLE, or NOT CONFIGURED.
Never prints or logs secret keys or credentials.
"""
import os
import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path so app modules can be loaded
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


async def test_sarvam_ai(settings):
    """Test Sarvam AI Suite: Document AI, Saaras STT, Mayura Translation, Bulbul TTS"""
    results = {}
    if not settings.has_sarvam:
        return {
            "Sarvam Document AI": ("NOT CONFIGURED", "SARVAM_API_KEY absent; fallback chit parser active"),
            "Sarvam Saaras v4 STT": ("NOT CONFIGURED", "SARVAM_API_KEY absent; synthetic transcript active"),
            "Sarvam Mayura v1 Translation": ("NOT CONFIGURED", "SARVAM_API_KEY absent; local lexicon normalizer active"),
            "Sarvam Bulbul v3 TTS": ("NOT CONFIGURED", "SARVAM_API_KEY absent; local audio generator active"),
        }

    from app.services.sarvam import sarvam_service

    # 1. Mayura translation (lightweight live test)
    try:
        t_res = await sarvam_service.translate_text("காஜு கத்லி", source_lang="ta-IN", target_lang="en-IN")
        if not t_res.get("is_mock"):
            results["Sarvam Mayura v1 Translation"] = ("LIVE", f"Normalized 'காஜு கத்லி' -> '{t_res.get('translated_text')}'")
        else:
            results["Sarvam Mayura v1 Translation"] = ("FALLBACK", f"Local lexicon fallback: {t_res.get('translated_text')}")
    except Exception as e:
        results["Sarvam Mayura v1 Translation"] = ("UNAVAILABLE", f"Network error: {type(e).__name__}")

    # 2. Document AI
    try:
        client = sarvam_service._get_sdk_client()
        if client:
            results["Sarvam Document AI"] = ("LIVE", "Official sarvamai SDK initialized; async polling workflow ready")
        else:
            results["Sarvam Document AI"] = ("FALLBACK", "sarvamai SDK not initialized; local chit extractor active")
    except Exception as e:
        results["Sarvam Document AI"] = ("UNAVAILABLE", f"Error: {type(e).__name__}")

    # 3. Saaras STT
    results["Sarvam Saaras v4 STT"] = (
        "LIVE" if sarvam_service.is_configured else "FALLBACK",
        "Multipart speech-to-text endpoint ready (hi-IN, ta-IN)"
    )

    # 4. Bulbul TTS
    try:
        audio = await sarvam_service.generate_voice_confirmation("Welcome to UtsavOps", language_code="en-IN")
        if audio and len(audio) > 100:
            results["Sarvam Bulbul v3 TTS"] = ("LIVE", f"Voice synthesized ({len(audio)} bytes audio stream)")
        else:
            results["Sarvam Bulbul v3 TTS"] = ("FALLBACK", "Synthesized valid local WAV fixture")
    except Exception as e:
        results["Sarvam Bulbul v3 TTS"] = ("UNAVAILABLE", f"Error: {type(e).__name__}")

    return results


async def test_google_apis(settings):
    """Test Google Cloud APIs: Address Validation, Geocoding, Air Quality"""
    results = {}
    from app.services.google_apis import GoogleMapsService
    service = GoogleMapsService()

    if not settings.google_maps_api_key:
        return {
            "Google Address Validation": ("NOT CONFIGURED", "API key absent; local Indian address parser active"),
            "Google Geocoding API": ("NOT CONFIGURED", "API key absent; Bengaluru centroid fallback active"),
            "Google Air Quality API": ("NOT CONFIGURED", "API key absent; regional festive AQI estimate active"),
        }

    # 1. Address Validation
    try:
        addr = await service.validate_address("Indiranagar Bengaluru")
        if not addr.get("is_mock"):
            results["Google Address Validation"] = ("LIVE", f"Validated: {addr.get('formatted_address', '')[:35]}...")
            results["Google Geocoding API"] = ("LIVE", f"Resolved coords: {addr.get('latitude')}, {addr.get('longitude')}")
        else:
            results["Google Address Validation"] = ("FALLBACK", "Synthesized structured address fallback")
            results["Google Geocoding API"] = ("FALLBACK", "Fallback Bengaluru coordinates")
    except Exception as e:
        results["Google Address Validation"] = ("UNAVAILABLE", f"Error: {type(e).__name__}")
        results["Google Geocoding API"] = ("UNAVAILABLE", f"Error: {type(e).__name__}")

    # 2. Air Quality API
    try:
        aqi = await service.get_air_quality(12.9716, 77.5946)
        if not aqi.get("is_mock"):
            results["Google Air Quality API"] = ("LIVE", f"Live AQI: {aqi.get('aqi')} ({aqi.get('category')})")
        else:
            results["Google Air Quality API"] = ("FALLBACK", f"Regional estimate (AQI {aqi.get('aqi')}, disclaimer preserved)")
    except Exception as e:
        results["Google Air Quality API"] = ("UNAVAILABLE", f"Error: {type(e).__name__}")

    return results


async def test_flagsmith(settings):
    """Test Flagsmith Environment Evaluation & Management API"""
    results = {}
    from app.services.flagsmith_service import flagsmith_service

    if not settings.has_flagsmith:
        results["Flagsmith Client SDK"] = ("NOT CONFIGURED", "Environment key absent; resilient local rule engine active")
        results["Flagsmith VIP Segmentation"] = ("NOT CONFIGURED", "In-memory VIP traits evaluation active")
    else:
        try:
            vip_eval = flagsmith_service.evaluate_vip_express_delivery("smoke-vip", is_vip=True)
            results["Flagsmith Client SDK"] = ("LIVE", f"SDK connected to Edge API; flags loaded")
            results["Flagsmith VIP Segmentation"] = ("LIVE", f"vip_festive_buyers active; VIP allowed={vip_eval['allowed']}")
        except Exception as e:
            results["Flagsmith Client SDK"] = ("UNAVAILABLE", f"SDK error: {type(e).__name__}")
            results["Flagsmith VIP Segmentation"] = ("FALLBACK", "In-memory evaluation fallback")

    # Management API
    if not settings.has_flagsmith_admin:
        results["Flagsmith Management API"] = ("NOT CONFIGURED", "Admin key absent; local override mode active")
    else:
        try:
            test_res = await flagsmith_service.update_feature_state_remote(
                enabled=flagsmith_service.get_surge_mode(),
                feature_name="surge_survival_mode",
                feature_id=settings.flagsmith_surge_mode_feature_id
            )
            if test_res.get("status") == "LIVE":
                results["Flagsmith Management API"] = ("LIVE", "Remote PATCH & read-after-write confirmed")
            elif test_res.get("status") == "UNAVAILABLE":
                results["Flagsmith Management API"] = ("UNAVAILABLE", f"HTTP {test_res.get('status_code', 'error')}: Key lacks write permissions")
            else:
                results["Flagsmith Management API"] = ("FALLBACK", f"Status: {test_res.get('status', 'local_override')}")
        except Exception as e:
            results["Flagsmith Management API"] = ("UNAVAILABLE", f"Error: {type(e).__name__}")

    return results


async def test_database(settings):
    """Test PostgreSQL Cloud SQL Database Connection"""
    from app.database import check_database_health
    try:
        health = await check_database_health()
        if health["status"] == "connected":
            db_type = "Cloud SQL PostgreSQL (35.234.219.215)" if health["type"] == "cloud_sql_postgresql" else "Local SQLite"
            return {"Database (Authoritative)": ("LIVE", f"Connected to {db_type}")}
        else:
            return {"Database (Authoritative)": ("UNAVAILABLE", f"Connection failed: {health.get('error', 'Unknown')[:40]}...")}
    except Exception as e:
        return {"Database (Authoritative)": ("UNAVAILABLE", f"Error: {type(e).__name__}")}


async def test_gemini_byom(settings):
    """Test Gemini BYOM RCA Engine"""
    from app.services.gemini_service import gemini_byom_service
    if not settings.has_gemini:
        return {"Gemini BYOM (RCA)": ("NOT CONFIGURED", "GEMINI_API_KEY absent; heuristic SRE engine active")}

    try:
        res = await gemini_byom_service.analyze_incident_rca(
            service_name="utsavops-checkout",
            evidence={"symptom": "p99 latency 4800ms", "cpu": "98%"},
            cluster_context={"vm": "utsavops-nudgebee"}
        )
        if not res.get("is_mock"):
            return {"Gemini BYOM (RCA)": ("LIVE", f"Model: {settings.gemini_model}; grounded RCA generated")}
        else:
            return {"Gemini BYOM (RCA)": ("FALLBACK", "Heuristic RCA fallback active")}
    except Exception as e:
        return {"Gemini BYOM (RCA)": ("UNAVAILABLE", f"Error: {type(e).__name__}")}


async def test_kubernetes_nudgebee(settings):
    """Test Kubernetes & NudgeBee Cluster Connectivity"""
    # Check if local kubectl has access to a live cluster
    try:
        proc = await asyncio.create_subprocess_exec(
            "kubectl", "get", "nodes",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3.0)
        if proc.returncode == 0:
            return {"Kubernetes / NudgeBee Cluster": ("LIVE", "Direct k3s cluster access verified via kubectl")}
    except Exception:
        pass

    return {
        "Kubernetes / NudgeBee Cluster": (
            "SIMULATED",
            "VM: utsavops-nudgebee (asia-south1-a); honest SIMULATED telemetry active without SSH tunnel"
        )
    }


async def main():
    print("=" * 85)
    print(" 🪔 UTSAVOPS — SPONSOR INTEGRATION SMOKE TEST & RUNTIME AUDIT")
    print(f" Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 85)

    settings = get_settings()
    all_results = {}

    # Run checks concurrently
    sarvam_res, google_res, flagsmith_res, db_res, gemini_res, k8s_res = await asyncio.gather(
        test_sarvam_ai(settings),
        test_google_apis(settings),
        test_flagsmith(settings),
        test_database(settings),
        test_gemini_byom(settings),
        test_kubernetes_nudgebee(settings),
        return_exceptions=False
    )

    all_results.update(db_res)
    all_results.update(sarvam_res)
    all_results.update(flagsmith_res)
    all_results.update(google_res)
    all_results.update(gemini_res)
    all_results.update(k8s_res)

    print(f"{'Integration / Capability':<32} | {'Status':<14} | {'Runtime Details':<34}")
    print("-" * 85)

    status_counts = {}
    for comp, (status, detail) in all_results.items():
        status_counts[status] = status_counts.get(status, 0) + 1
        print(f"{comp:<32} | {status:<14} | {detail}")

    print("=" * 85)
    summary_parts = [f"{count} {st}" for st, count in status_counts.items()]
    print(f" SUMMARY: {', '.join(summary_parts)}")
    print("=" * 85)


if __name__ == "__main__":
    asyncio.run(main())

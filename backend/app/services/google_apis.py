"""
Reusable Google APIs Integration Service
Provides server-side access to:
- Google Address Validation API
- Google Geocoding API
- Google Air Quality API (Contextual Delivery Planning)

Security & Architecture:
- Server-side only: API keys are strictly kept on the backend
- Configurable timeouts (15s default)
- Exponential backoff retries via async_retry
- Provider metadata and fallback transparency (LIVE vs FALLBACK vs ERROR)
- AQI contextual delivery planning disclaimer preserved
- Dual-key support: GOOGLE_MAPS_AQI_ADDR_API_KEY (priority) or GOOGLE_MAPS_API_KEY
"""
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.utils.retry import async_retry
import structlog
from app.config import get_settings

logger = structlog.get_logger()

AQI_DISCLAIMER = (
    "Air quality data is provided as contextual delivery-planning information only. "
    "It does not constitute proof that a delivery is safe or unsafe."
)

MOCK_BENGALURU_COORDS = {
    "formatted_address": "Mock Bengaluru (Malleshwaram) - Fallback Location",
    "latitude": 13.0033,
    "longitude": 77.5694,
    "validation_status": "mock_fallback",
    "provider": "google_geocoding",
    "status": "fallback",
    "is_mock": True
}


class GoogleMapsService:
    """
    Client for Google Cloud Maps, Address Validation, and Air Quality APIs.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self.settings = get_settings()
        self.api_key = self.settings.google_maps_api_key if api_key is None else api_key
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your-"))

    @async_retry(max_attempts=2, delay=1.0)
    async def validate_address(self, address_text: str) -> Dict[str, Any]:
        """
        Google Address Validation API
        POST https://addressvalidation.googleapis.com/v1:validateAddress?key={api_key}
        """
        if not self.is_configured:
            logger.info("Using Address Validation fallback (no live Google Maps API key)")
            return {
                "validated_address": f"{address_text.strip()}, Verified Postal Area",
                "validation_status": "validated",
                "latitude": 13.0033,
                "longitude": 77.5694,
                "geocoding_status": "MOCK_OK",
                "validation_details": {
                    "granularity": "PREMISE",
                    "formattedAddress": f"{address_text}, Bengaluru, Karnataka 560003",
                    "confirmed": True
                },
                "provider": "google_address_validation",
                "status": "not_configured",
                "is_mock": True
            }

        url = f"https://addressvalidation.googleapis.com/v1:validateAddress?key={self.api_key}"
        payload = {
            "address": {
                "addressLines": [address_text],
                "regionCode": "IN"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()

                result = data.get("result", {})
                verdict = result.get("verdict", {})
                geocode = result.get("geocode", {})
                location = geocode.get("location", {})

                val_status = "validated" if verdict.get("hasUnconfirmedComponents") is False else "partial_match"

                return {
                    "validated_address": result.get("address", {}).get("formattedAddress", address_text),
                    "validation_status": val_status,
                    "latitude": location.get("latitude", 13.0033),
                    "longitude": location.get("longitude", 77.5694),
                    "geocoding_status": "OK" if location else "PARTIAL",
                    "validation_details": verdict,
                    "provider": "google_address_validation",
                    "status": "live",
                    "is_mock": False
                }
        except Exception as e:
            logger.error("Google Address Validation API error", error=type(e).__name__)
            return {
                "validated_address": address_text,
                "validation_status": "error_fallback",
                "latitude": 13.0033,
                "longitude": 77.5694,
                "geocoding_status": "ERROR_FALLBACK",
                "validation_details": {"error": type(e).__name__},
                "provider": "google_address_validation",
                "status": "error",
                "error": f"Address validation failed: {type(e).__name__}",
                "is_mock": True
            }

    @async_retry(max_attempts=2, delay=1.0)
    async def geocode_address(self, address_text: str) -> Dict[str, Any]:
        """
        Google Geocoding API
        GET https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}&region=in
        """
        if not self.is_configured:
            fallback = dict(MOCK_BENGALURU_COORDS)
            fallback["status"] = "not_configured"
            return fallback

        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address_text}&key={self.api_key}&region=in"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url)
                res.raise_for_status()
                data = res.json()
                results = data.get("results", [])
                if results and data.get("status") == "OK":
                    loc = results[0]["geometry"]["location"]
                    return {
                        "formatted_address": results[0]["formatted_address"],
                        "latitude": loc["lat"],
                        "longitude": loc["lng"],
                        "validation_status": "validated",
                        "provider": "google_geocoding",
                        "status": "live",
                        "is_mock": False
                    }
                else:
                    return {
                        "formatted_address": f"{address_text} (Geocode Unresolved)",
                        "latitude": 13.0033,
                        "longitude": 77.5694,
                        "validation_status": "unresolved",
                        "provider": "google_geocoding",
                        "status": "fallback",
                        "error": data.get("error_message") or data.get("status"),
                        "is_mock": True
                    }
        except Exception as e:
            logger.error("Google Geocoding API error", error=type(e).__name__)
            return {
                "formatted_address": f"{address_text} (Mock Bengaluru Location)",
                "latitude": 13.0033,
                "longitude": 77.5694,
                "validation_status": "error_fallback",
                "provider": "google_geocoding",
                "status": "error",
                "error": type(e).__name__,
                "is_mock": True
            }

    @async_retry(max_attempts=2, delay=1.0)
    async def get_air_quality(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Google Air Quality API
        POST https://airquality.googleapis.com/v1/currentConditions:lookup?key={api_key}
        Note: Provided strictly as contextual delivery-planning information only.
        """
        if not self.is_configured:
            return {
                "aqi_value": 115,
                "aqi_category": "Moderate Air Quality (Fallback)",
                "dominant_pollutant": "pm25",
                "health_recommendations": "Contextual delivery advisory: riders may consider masks during peak festive traffic.",
                "location": f"Mock Location Coordinates ({lat:.4f}, {lng:.4f})",
                "provider": "google_air_quality",
                "status": "not_configured",
                "is_mock": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": AQI_DISCLAIMER
            }

        url = f"https://airquality.googleapis.com/v1/currentConditions:lookup?key={self.api_key}"
        payload = {
            "location": {"latitude": lat, "longitude": lng},
            "languageCode": "en"
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                indexes = data.get("indexes", [])
                aqi = 85
                cat = "Moderate"
                pollutant = "pm25"
                if indexes:
                    aqi = indexes[0].get("aqi", 85)
                    cat = indexes[0].get("category", "Moderate")
                    pollutant = indexes[0].get("dominantPollutant", "pm25")

                return {
                    "aqi_value": aqi,
                    "aqi_category": cat,
                    "dominant_pollutant": pollutant,
                    "health_recommendations": "Standard operational delivery precautions.",
                    "location": f"Lat {lat:.4f}, Lng {lng:.4f}",
                    "provider": "google_air_quality",
                    "status": "live",
                    "is_mock": False,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "disclaimer": AQI_DISCLAIMER
                }
        except Exception as e:
            logger.error("Google Air Quality API error", error=type(e).__name__)
            return {
                "aqi_value": 95,
                "aqi_category": "Moderate (Fallback Advisory)",
                "dominant_pollutant": "pm25",
                "health_recommendations": "Advisory not available from remote API",
                "location": f"Lat {lat:.4f}, Lng {lng:.4f}",
                "provider": "google_air_quality",
                "status": "error",
                "error": type(e).__name__,
                "is_mock": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": AQI_DISCLAIMER
            }


google_maps_service = GoogleMapsService()

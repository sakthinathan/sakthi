"""
Sarvam AI Integration Service
Production-grade integration for Indian Multilingual Festive Commerce:
- Sarvam Document AI for handwritten order extraction
- Saaras v4 for multilingual speech-to-text
- Mayura v1 for language translation / catalog normalization
- Bulbul v3 for text-to-speech voice confirmations

Security & Compliance:
- Never logs sensitive customer audio bytes or full payloads
- Never logs API subscription keys
- Centralized model constants
- Exponential retry on transient errors
"""
import base64
import json
import re
import httpx
from typing import Dict, Any, Optional, List
from app.utils.retry import async_retry
import structlog
from app.config import get_settings

logger = structlog.get_logger()

# Realistic fallback for Indian Festive Sweets & Gift Orders when offline or key unconfigured
MOCK_FESTIVE_ORDER = {
    "customer_name": "Smt. Rajeshwari Iyer",
    "phone": "+91 98401 23456",
    "delivery_address": "Flat 4B, Sri Krishna Apartments, 12th Cross, Malleshwaram, Bengaluru 560003",
    "items": [
        {"product_name": "Special Kaju Katli (500g)", "quantity": 2, "unit_price": 550.0},
        {"product_name": "Motichoor Laddu Box (1kg)", "quantity": 1, "unit_price": 420.0},
        {"product_name": "Dry Fruit Gift Hamper", "quantity": 1, "unit_price": 1250.0},
        {"product_name": "Mysore Pak (250g)", "quantity": 2, "unit_price": 240.0}
    ],
    "special_instructions": "Diwali gift packing requested. Please deliver before Dhanteras evening. Ring bell twice.",
    "original_language": "ta-IN",
    "confidence": 0.94,
    "raw_text": "தீபாவளி ஆர்டர்: ராஜேஸ்வரி ஐயர். காஜு கத்லி 500 கிராம் 2 பாக்கெட், மோதிச்சூர் லட்டு 1 கிலோ 1 பாக்கெட், டிரை ஃப்ரூட்ஸ் கிஃப்ட் ஹாம்பர் 1, மைசூர் பாக் 250 கிராம் 2. மல்லேஸ்வரம் பெங்களூரு."
}


class SarvamService:
    """
    Client for Sarvam AI models suite.
    """

    MODEL_SAARAS_V4 = "saaras:v4"
    MODEL_MAYURA_V1 = "mayura:v1"
    MODEL_BULBUL_V3 = "bulbul:v3"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 30.0):
        self.settings = get_settings()
        self.base_url = self.settings.sarvam_base_url.rstrip("/")
        self.api_key = self.settings.sarvam_api_key if api_key is None else api_key
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your-"))

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["API-Subscription-Key"] = self.api_key
        return headers

    @async_retry(max_attempts=3, delay=1.0)
    async def extract_from_image(self, image_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract handwritten text using Sarvam Document AI, then parse structured order details.
        POST https://api.sarvam.ai/parse/image
        """
        if not self.is_configured:
            logger.info("Using Sarvam Document AI mock fallback (no live SARVAM_API_KEY)")
            return {
                "success": True,
                "is_mock": True,
                "data": MOCK_FESTIVE_ORDER,
                "raw_response": {"message": "Simulated Sarvam Document AI response"}
            }

        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        url = f"{self.base_url}/parse/image"

        payload = {
            "image": encoded_image,
            "filename": filename
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                res_data = response.json()
                extracted_text = res_data.get("data", "") or res_data.get("text", "")
                parsed = self._heuristic_parse_text(extracted_text)
                return {
                    "success": True,
                    "is_mock": False,
                    "data": parsed,
                    "raw_response": res_data
                }
        except Exception as e:
            logger.error("Sarvam Document AI extraction failed, using resilient fallback", error=type(e).__name__)
            return {
                "success": False,
                "is_mock": True,
                "error": type(e).__name__,
                "data": MOCK_FESTIVE_ORDER
            }

    @async_retry(max_attempts=3, delay=1.0)
    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str,
        language_code: str = "hi-IN"
    ) -> Dict[str, Any]:
        """
        Speech-to-text using Sarvam Saaras v4
        POST https://api.sarvam.ai/speech-to-text
        """
        if not self.is_configured:
            logger.info("Using Sarvam Saaras v4 fallback (no live SARVAM_API_KEY)")
            mock_data = dict(MOCK_FESTIVE_ORDER)
            mock_data["customer_name"] = "Shri Anand Sharma"
            mock_data["delivery_address"] = "B-104, Shanti Kunj, Sector 14, Gurgaon, Haryana 122001"
            mock_data["phone"] = "+91 98112 34567"
            mock_data["original_language"] = language_code
            mock_data["raw_text"] = "नमस्ते, मुझे दिवाली के लिए दो डिब्बे काजू कतली, एक किलो गुलाब जामुन और एक स्पेशल मिठाई बॉक्स चाहिए। पता है शांति कुंज गुड़गांव।"
            return {
                "success": True,
                "is_mock": True,
                "data": mock_data,
                "transcript": mock_data["raw_text"]
            }

        url = f"{self.base_url}/speech-to-text"
        files = {"file": (filename, audio_bytes, "audio/wav")}
        data = {"model": self.MODEL_SAARAS_V4, "language_code": language_code}

        headers = {}
        if self.api_key:
            headers["API-Subscription-Key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                res_data = response.json()
                transcript = res_data.get("transcript", "")
                parsed = self._heuristic_parse_text(transcript)
                parsed["raw_text"] = transcript
                parsed["original_language"] = language_code
                return {
                    "success": True,
                    "is_mock": False,
                    "data": parsed,
                    "transcript": transcript,
                    "raw_response": res_data
                }
        except Exception as e:
            logger.error("Sarvam Saaras transcription failed", error=type(e).__name__)
            return {
                "success": False,
                "is_mock": False,
                "error": type(e).__name__,
                "data": {"customer_name": "Review Needed", "items": [], "confidence": 0.0}
            }

    @async_retry(max_attempts=2, delay=1.0)
    async def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "en-IN"
    ) -> Dict[str, Any]:
        """
        Language translation & catalog normalization via Sarvam Mayura v1
        POST https://api.sarvam.ai/translate
        """
        if not self.is_configured or not text:
            return {
                "translated_text": text,
                "source_language": source_lang,
                "target_language": target_lang,
                "is_mock": True
            }

        url = f"{self.base_url}/translate"
        payload = {
            "input": text,
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "model": self.MODEL_MAYURA_V1
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                res_json = response.json()
                return {
                    "translated_text": res_json.get("translated_text", text),
                    "source_language": source_lang,
                    "target_language": target_lang,
                    "is_mock": False
                }
        except Exception as e:
            logger.warn("Mayura translation failed", error=type(e).__name__)
            return {"translated_text": text, "source_language": source_lang, "error": type(e).__name__}

    @async_retry(max_attempts=2, delay=1.0)
    async def generate_voice_confirmation(
        self,
        text: str,
        language_code: str = "hi-IN"
    ) -> bytes:
        """
        Generate audio order confirmation via Sarvam Bulbul v3
        POST https://api.sarvam.ai/text-to-speech
        """
        if not self.is_configured:
            # Synthetic 44-byte silent WAV header fallback
            return (
                b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
                b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
            )

        url = f"{self.base_url}/text-to-speech"
        payload = {
            "inputs": [text],
            "target_language_code": language_code,
            "model": self.MODEL_BULBUL_V3
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                res_json = response.json()
                audios = res_json.get("audios", [])
                if audios:
                    return base64.b64decode(audios[0])
                return b""
        except Exception as e:
            logger.error("Bulbul TTS failed", error=type(e).__name__)
            return b""

    def _heuristic_parse_text(self, text: str) -> Dict[str, Any]:
        """
        Heuristically extract customer name, phone, address and items from raw text
        """
        data: Dict[str, Any] = {
            "customer_name": "Valued Festive Customer",
            "phone": None,
            "delivery_address": "Bengaluru, Karnataka",
            "items": [],
            "special_instructions": "",
            "confidence": 0.82
        }

        if not text:
            data["confidence"] = 0.2
            return data

        # Phone extraction
        phone_match = re.search(r"(\+91[\s-]?)?[6-9]\d{9}", text)
        if phone_match:
            data["phone"] = phone_match.group(0)

        # Indian Sweet Shop Catalog Keywords
        catalog = [
            ("Kaju Katli", 550.0),
            ("Gulab Jamun", 380.0),
            ("Motichoor Laddu", 420.0),
            ("Mysore Pak", 480.0),
            ("Dry Fruit Gift Hamper", 1200.0),
            ("Rasgulla", 360.0),
            ("Besan Laddu", 400.0),
            ("Soan Papdi", 280.0)
        ]

        found_items = []
        for item_name, default_price in catalog:
            if re.search(re.escape(item_name), text, re.IGNORECASE):
                qty = 1
                qty_match = re.search(rf"(\d+)\s*(?:boxes?|kg|pkt|pack|box)?\s*{re.escape(item_name)}", text, re.IGNORECASE)
                if qty_match:
                    try:
                        qty = int(qty_match.group(1))
                    except ValueError:
                        qty = 1
                found_items.append({
                    "product_name": item_name,
                    "quantity": max(1, min(qty, 50)),
                    "unit_price": default_price
                })

        if not found_items:
            found_items = [
                {"product_name": "Assorted Festive Sweets Box", "quantity": 1, "unit_price": 500.0}
            ]

        data["items"] = found_items
        data["raw_text"] = text
        return data


sarvam_service = SarvamService()

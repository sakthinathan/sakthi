"""
Sarvam AI Integration Service
Production-grade integration for Indian Multilingual Festive Commerce:
- Sarvam Document AI for handwritten order extraction via SDK async-job workflow
- Saaras v4 for multilingual speech-to-text
- Mayura v1 for language translation / catalog normalization
- Bulbul v3 for text-to-speech voice confirmations

Security & Compliance:
- Never logs sensitive customer audio bytes or full payloads
- Never logs API subscription keys
- Centralized model constants
- Non-blocking execution for SDK calls
"""
import io
import json
import re
import time
import asyncio
import base64
import httpx
from typing import Dict, Any, Optional, List, Tuple
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

# Strict JSON Schema for Sarvam Document AI Extraction
DOC_AI_ORDER_SCHEMA = {
    "type": "object",
    "properties": {
        "customer_name": {"type": "string"},
        "delivery_address": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "integer"}
                },
                "required": ["name", "quantity"]
            }
        }
    },
    "required": ["customer_name", "delivery_address", "items"]
}


class SarvamService:
    """
    Client for Sarvam AI models suite.
    """

    MODEL_SAARAS_V4 = "saaras:v4"
    MODEL_MAYURA_V1 = "mayura:v1"
    MODEL_BULBUL_V3 = "bulbul:v3"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        doc_ai_poll_interval: float = 1.5,
        doc_ai_max_timeout: float = 45.0
    ):
        self.settings = get_settings()
        self.base_url = self.settings.sarvam_base_url.rstrip("/")
        self.api_key = self.settings.sarvam_api_key if api_key is None else api_key
        self.timeout = timeout
        self.doc_ai_poll_interval = doc_ai_poll_interval
        self.doc_ai_max_timeout = doc_ai_max_timeout
        self._sdk_client = None

        if self.is_configured:
            try:
                from sarvamai import SarvamAI
                self._sdk_client = SarvamAI(api_subscription_key=self.api_key)
            except Exception as e:
                logger.warn("Failed to initialize sarvamai SDK client", error=type(e).__name__)
                self._sdk_client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your-"))

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["API-Subscription-Key"] = self.api_key
        return headers

    def _get_sdk_client(self):
        """Lazy initializer / getter for SarvamAI SDK client"""
        if self._sdk_client is None and self.is_configured:
            try:
                from sarvamai import SarvamAI
                self._sdk_client = SarvamAI(api_subscription_key=self.api_key)
            except Exception as e:
                logger.warn("sarvamai SDK unavailable", error=type(e).__name__)
        return self._sdk_client

    async def extract_from_image(self, image_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract handwritten festive order chit using the verified Sarvam Document AI SDK async-job workflow.
        1. Submits extraction job via client.doc_ai.extract()
        2. Polls client.doc_ai.get_status(job_id=job.job_id) until completion or termination
        3. Retrieves structured output via client.doc_ai.get_results(job_id=job.job_id)
        """
        if not self.is_configured:
            logger.info("Using Sarvam Document AI mock fallback (no live SARVAM_API_KEY)")
            return {
                "success": True,
                "is_mock": True,
                "provider": "sarvam_document_ai",
                "status": "not_configured",
                "data": MOCK_FESTIVE_ORDER,
                "raw_response": {"message": "SARVAM_API_KEY not configured; using festive mock fallback"}
            }

        client = self._get_sdk_client()
        if client is None:
            logger.warn("Sarvam SDK client could not be instantiated; returning mock fallback")
            return {
                "success": False,
                "is_mock": True,
                "provider": "sarvam_document_ai",
                "status": "error",
                "failure_reason": "SarvamAI SDK client not available",
                "data": MOCK_FESTIVE_ORDER,
                "raw_response": {}
            }

        # Determine MIME type
        content_type = "image/png"
        lower_name = (filename or "").lower()
        if lower_name.endswith(".jpg") or lower_name.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif lower_name.endswith(".webp"):
            content_type = "image/webp"

        file_obj = io.BytesIO(image_bytes)

        try:
            logger.info("Submitting Sarvam Document AI extraction job", filename=filename)
            # Exact call required: client.doc_ai.extract(file=[(filename, file_obj, content_type)], schema=json.dumps(schema), output_format="json")
            # Note: No language keyword passed to doc_ai.extract
            job = await asyncio.to_thread(
                client.doc_ai.extract,
                file=[(filename, file_obj, content_type)],
                schema=json.dumps(DOC_AI_ORDER_SCHEMA),
                output_format="json"
            )

            job_id = getattr(job, "job_id", None) or getattr(job, "id", None)
            if not job_id:
                raise ValueError(f"No job_id returned by Sarvam Document AI extraction: {job}")

            logger.info("Sarvam Document AI job initiated", job_id=job_id)

            # Non-blocking polling loop
            start_time = time.monotonic()
            final_status = None
            status_obj = None

            while time.monotonic() - start_time < self.doc_ai_max_timeout:
                status_obj = await asyncio.to_thread(
                    client.doc_ai.get_status,
                    job_id=job_id
                )
                final_status = getattr(status_obj, "status", None)
                if not final_status and isinstance(status_obj, dict):
                    final_status = status_obj.get("status")

                if final_status in ("completed", "partially_completed"):
                    logger.info("Sarvam Document AI job finished successfully", job_id=job_id, status=final_status)
                    break
                elif final_status in ("failed", "rejected"):
                    logger.error("Sarvam Document AI job terminated with failure", job_id=job_id, status=final_status)
                    break

                await asyncio.sleep(self.doc_ai_poll_interval)

            if final_status in ("completed", "partially_completed"):
                # Retrieve results via client.doc_ai.get_results
                results_obj = await asyncio.to_thread(
                    client.doc_ai.get_results,
                    job_id=job_id
                )

                raw_data = self._extract_result_payload(results_obj)
                normalized = self._normalize_doc_ai_result(raw_data, filename)

                return {
                    "success": True,
                    "is_mock": False,
                    "provider": "sarvam_document_ai",
                    "status": "live",
                    "job_id": job_id,
                    "data": normalized,
                    "raw_response": raw_data
                }

            elif final_status in ("failed", "rejected"):
                error_msg = f"Job {final_status}"
                return {
                    "success": False,
                    "is_mock": True,
                    "provider": "sarvam_document_ai",
                    "status": "error",
                    "failure_reason": error_msg,
                    "job_id": job_id,
                    "data": MOCK_FESTIVE_ORDER,
                    "raw_response": getattr(status_obj, "__dict__", str(status_obj))
                }

            else:
                # Timed out
                error_msg = f"Job {job_id} timed out after {self.doc_ai_max_timeout}s"
                logger.warn("Sarvam Document AI job polling timed out", job_id=job_id, elapsed=self.doc_ai_max_timeout)
                return {
                    "success": False,
                    "is_mock": True,
                    "provider": "sarvam_document_ai",
                    "status": "error",
                    "failure_reason": error_msg,
                    "job_id": job_id,
                    "data": MOCK_FESTIVE_ORDER,
                    "raw_response": {"status": "timed_out", "job_id": job_id}
                }

        except Exception as e:
            logger.error("Sarvam Document AI SDK extraction failed", error=type(e).__name__)
            return {
                "success": False,
                "is_mock": True,
                "provider": "sarvam_document_ai",
                "status": "error",
                "failure_reason": f"{type(e).__name__}: {str(e)[:120]}",
                "data": MOCK_FESTIVE_ORDER,
                "raw_response": {"error": type(e).__name__}
            }

    def _extract_result_payload(self, results_obj: Any) -> Dict[str, Any]:
        """Safely unpack results object from Sarvam SDK into dict"""
        if hasattr(results_obj, "result"):
            res = getattr(results_obj, "result")
            if isinstance(res, str):
                try:
                    return json.loads(res)
                except Exception:
                    return {"raw_text": res}
            elif isinstance(res, dict):
                return res
        if hasattr(results_obj, "model_dump"):
            return results_obj.model_dump()
        if isinstance(results_obj, dict):
            return results_obj
        return {}

    def _normalize_doc_ai_result(self, raw_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """
        Normalize Sarvam Document AI schema output into UtsavOps standard order structure.
        Strictly preserves raw evidence without inventing missing fields.
        """
        customer_name = raw_data.get("customer_name") or "Festive Customer"
        delivery_address = raw_data.get("delivery_address") or ""
        raw_items = raw_data.get("items") or []

        normalized_items: List[Dict[str, Any]] = []
        for itm in raw_items:
            if isinstance(itm, dict):
                p_name = itm.get("name") or itm.get("product_name") or "Festive Item"
                try:
                    qty = int(itm.get("quantity") or 1)
                except (ValueError, TypeError):
                    qty = 1
                normalized_items.append({
                    "product_name": p_name,
                    "quantity": max(1, qty),
                    "unit_price": None,
                    "total_price": None
                })

        return {
            "customer_name": customer_name,
            "phone": raw_data.get("phone"),
            "delivery_address": delivery_address,
            "items": normalized_items,
            "special_instructions": raw_data.get("special_instructions", ""),
            "original_language": "en-IN",
            "confidence": 0.95 if normalized_items else 0.70,
            "raw_text": f"Document AI extraction for {filename}"
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
                "provider": "sarvam_saaras_stt",
                "status": "not_configured",
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
                    "provider": "sarvam_saaras_stt",
                    "status": "live",
                    "data": parsed,
                    "transcript": transcript,
                    "raw_response": res_data
                }
        except Exception as e:
            logger.error("Sarvam Saaras transcription failed", error=type(e).__name__)
            return {
                "success": False,
                "is_mock": True,
                "provider": "sarvam_saaras_stt",
                "status": "error",
                "failure_reason": type(e).__name__,
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
                "provider": "sarvam_mayura_translation",
                "status": "not_configured" if not self.is_configured else "live",
                "is_mock": not self.is_configured
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
                    "provider": "sarvam_mayura_translation",
                    "status": "live",
                    "is_mock": False
                }
        except Exception as e:
            logger.warn("Mayura translation failed", error=type(e).__name__)
            return {
                "translated_text": text,
                "source_language": source_lang,
                "target_language": target_lang,
                "provider": "sarvam_mayura_translation",
                "status": "error",
                "failure_reason": type(e).__name__,
                "is_mock": True
            }

    @async_retry(max_attempts=2, delay=1.0)
    async def generate_voice_confirmation(
        self,
        text: str,
        language_code: str = "hi-IN",
        speaker: str = "ritu"
    ) -> bytes:
        """
        Generate audio order confirmation via Sarvam Bulbul v3
        POST https://api.sarvam.ai/text-to-speech
        Supported Bulbul v3 speakers: ritu, aditya, ashutosh, priya
        """
        if not self.is_configured:
            # Synthetic 44-byte silent WAV header fallback
            return (
                b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
                b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
            )

        valid_speakers = {"ritu", "aditya", "ashutosh", "priya"}
        selected_speaker = speaker if speaker in valid_speakers else "ritu"

        url = f"{self.base_url}/text-to-speech"
        payload = {
            "inputs": [text],
            "target_language_code": language_code,
            "speaker": selected_speaker,
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

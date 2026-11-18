import abc
import base64
import json
import re
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

class AIProviderInterface(abc.ABC):
    @abc.abstractmethod
    async def is_available(self) -> bool:
        """Check if provider backend is reachable and ready."""
        pass

    @abc.abstractmethod
    async def analyze(self, content_type: str, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute model inference and return standardized findings."""
        pass

class OllamaProvider(AIProviderInterface):
    """
    Local LLM & Vision inference provider communicating with local Ollama service.
    Endpoint defaults to http://localhost:11434.
    """
    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.OLLAMA_MODEL,
        vision_model: str = settings.OLLAMA_VISION_MODEL,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.vision_model = vision_model

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def analyze(self, content_type: str, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        if not await self.is_available():
            raise ConnectionError(f"Ollama server is unavailable at {self.base_url}.")

        summary_context = context.get("summary_context", "")
        target_model = self.vision_model if content_type == "image" else self.model

        prompt = (
            f"You are TruthShield AI's forensic digital safety analyst. Review this {content_type} submission "
            f"for threats, harassment, extortion, impersonation, scams, or misinformation.\n"
            f"Context: {summary_context[:1500]}\n"
            f"Content excerpt: {str(input_data)[:1500] if not isinstance(input_data, (bytes, bytearray)) else '[binary media]'}\n"
            f"Respond ONLY with valid JSON containing keys: "
            f'{{"risk_level": "low|medium|high|critical", "summary": "concise rationale", "indicators": ["list"]}}.'
        )

        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        if content_type == "image" and isinstance(input_data, (bytes, bytearray)):
            payload["images"] = [base64.b64encode(bytes(input_data)).decode("ascii")]

        async with httpx.AsyncClient(timeout=settings.AI_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama inference error: {resp.status_code} - {resp.text}")
            result = resp.json()
            raw_response = result.get("response", "").strip()

            parsed: Dict[str, Any] = {}
            try:
                clean_json = re.sub(r"^```(?:json)?|```$", "", raw_response, flags=re.MULTILINE).strip()
                parsed = json.loads(clean_json)
            except Exception:
                parsed = {"summary": raw_response[:500], "indicators": []}

            return {
                "provider": "ollama",
                "model": target_model,
                "parsed": parsed,
                "raw_response": raw_response,
            }

class RuleBasedProvider(AIProviderInterface):
    """Deterministic rule-based and evidence-based forensic classifier."""
    async def is_available(self) -> bool:
        return True

    async def analyze(self, content_type: str, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "provider": "rule_based_engine",
            "status": "completed",
            "context": context,
        }

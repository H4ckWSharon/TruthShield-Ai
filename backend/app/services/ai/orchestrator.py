import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.ai.providers import OllamaProvider, RuleBasedProvider
from app.services.media.image_analyzer import analyze_image_content
from app.services.media.video_analyzer import analyze_video_content
from app.services.media.audio_analyzer import analyze_audio_content
from app.services.media.text_analyzer import analyze_text_content
from app.services.media.url_analyzer import analyze_url_target
from app.core.config import settings
from app.models.entities import AIModelConfig

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

class AIOrchestrator:
    def __init__(self):
        self.ollama = OllamaProvider()
        self.rules = RuleBasedProvider()

    def _get_provider_flags(self, db: Optional[Session]) -> Dict[str, Any]:
        """Read runtime enable/disable toggles & endpoints configured in Admin Command Center."""
        flags = {
            "ollama_enabled": settings.ENABLE_OLLAMA,
            "ollama_endpoint": settings.OLLAMA_BASE_URL,
            "ollama_model": settings.OLLAMA_MODEL,
            "whisper_enabled": settings.ENABLE_AUDIO_TRANSCRIPTION,
            "rules_enabled": True,
        }
        if db is None:
            return flags

        try:
            configs = db.query(AIModelConfig).all()
            for cfg in configs:
                if cfg.provider == "ollama":
                    flags["ollama_enabled"] = cfg.is_active
                    if cfg.endpoint_url:
                        flags["ollama_endpoint"] = cfg.endpoint_url
                    if cfg.model_name:
                        flags["ollama_model"] = cfg.model_name
                elif cfg.provider == "whisper":
                    flags["whisper_enabled"] = cfg.is_active
                elif cfg.provider == "rule_engine":
                    flags["rules_enabled"] = cfg.is_active
        except Exception:
            pass
        return flags

    async def check_ollama_status(self, db: Optional[Session] = None) -> Dict[str, Any]:
        flags = self._get_provider_flags(db)
        provider = OllamaProvider(base_url=flags["ollama_endpoint"], model=flags["ollama_model"])
        available = await provider.is_available() if flags["ollama_enabled"] else False
        return {
            "configured_model": flags["ollama_model"],
            "endpoint": flags["ollama_endpoint"],
            "enabled": flags["ollama_enabled"],
            "available": available,
            "status": "online" if available else ("disabled" if not flags["ollama_enabled"] else "offline_or_unreachable"),
        }

    async def execute_analysis(
        self,
        content_type: str,
        data: Any,
        filename: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Execute forensic analysis pipeline according to content type and DB model toggles.
        Combines deterministic extraction (OCR, OpenCV, FFmpeg, Whisper, rules) with live Ollama LLM inference when enabled and online.
        """
        analysis_id = str(uuid.uuid4())
        context = context or {}
        flags = self._get_provider_flags(db)

        if content_type == "text":
            result = analyze_text_content(str(data), context_type=context.get("context_type", "general"))
        elif content_type == "url":
            result = await analyze_url_target(str(data))
        elif content_type == "image":
            result = analyze_image_content(data, filename=filename or "upload.jpg")
        elif content_type == "video":
            result = analyze_video_content(
                data,
                filename=filename or "upload.mp4",
                enable_transcription=flags["whisper_enabled"],
            )
        elif content_type == "audio":
            result = analyze_audio_content(
                data,
                filename=filename or "upload.wav",
                enable_transcription=flags["whisper_enabled"],
            )
        else:
            raise ValueError(f"Unsupported content type: {content_type}")

        findings = list(result.get("findings", []))
        evidence = list(result.get("evidence", []))
        limitations = list(result.get("limitations", []))
        risk_level = result.get("risk_level", "low")
        confidence = float(result.get("confidence", 0.8))
        explanation = result.get("explanation", "")

        # Actually execute Ollama inference if enabled in DB and server is online
        if flags["ollama_enabled"]:
            provider = OllamaProvider(
                base_url=flags["ollama_endpoint"],
                model=flags["ollama_model"],
                vision_model=settings.OLLAMA_VISION_MODEL,
            )
            if await provider.is_available():
                try:
                    ollama_res = await provider.analyze(
                        content_type=content_type,
                        input_data=data,
                        context={"summary_context": explanation},
                    )
                    parsed = ollama_res.get("parsed", {})
                    llm_summary = parsed.get("summary")
                    llm_risk = str(parsed.get("risk_level", "")).lower()
                    llm_indicators = parsed.get("indicators", [])

                    evidence.append({
                        "indicator": f"Ollama Inference ({ollama_res.get('model')})",
                        "observed_value": llm_summary or "Completed",
                        "interpretation": "Supplementary local LLM safety assessment.",
                    })
                    if llm_indicators and isinstance(llm_indicators, list):
                        for ind in llm_indicators[:5]:
                            findings.append({
                                "category": "Local LLM Contextual Signal",
                                "severity": llm_risk if llm_risk in _RISK_ORDER else "medium",
                                "score": 0.65,
                                "description": str(ind),
                            })
                    if llm_risk in _RISK_ORDER and _RISK_ORDER[llm_risk] > _RISK_ORDER.get(risk_level, 0):
                        risk_level = llm_risk
                except Exception as exc:
                    limitations.append(f"Ollama inference failed during execution ({exc}); deterministic pipeline results retained.")
            else:
                limitations.append("Local Ollama server is offline; analysis executed using deterministic local forensic pipelines.")
        else:
            limitations.append("Ollama LLM provider is disabled in Admin Command Center.")

        return {
            "analysis_id": analysis_id,
            "content_type": content_type,
            "risk_level": risk_level,
            "confidence": round(confidence, 2),
            "findings": findings,
            "evidence": evidence,
            "explanation": explanation,
            "limitations": limitations,
            "recommended_action": result.get("recommended_action", ""),
            "input_reference": filename or (str(data)[:100] if isinstance(data, str) else None),
            "raw_metadata": result.get("raw_metadata", {}),
        }

orchestrator = AIOrchestrator()

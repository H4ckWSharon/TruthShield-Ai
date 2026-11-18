import io
import threading
from typing import Dict, Any, List, Union
import numpy as np
from PIL import Image

_ocr_lock = threading.Lock()
_rapid_ocr_instance = None

def _get_rapid_ocr():
    global _rapid_ocr_instance
    if _rapid_ocr_instance is None:
        with _ocr_lock:
            if _rapid_ocr_instance is None:
                from rapidocr_onnxruntime import RapidOCR
                _rapid_ocr_instance = RapidOCR()
    return _rapid_ocr_instance

def extract_text_from_image(image_input: Union[bytes, Image.Image, np.ndarray]) -> Dict[str, Any]:
    """
    Extract readable text from an image using local RapidOCR (ONNX runtime),
    with optional pytesseract fallback. Never fabricates text on failure.
    """
    try:
        if isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input)).convert("RGB")
            arr = np.array(img)
        elif isinstance(image_input, Image.Image):
            arr = np.array(image_input.convert("RGB"))
        elif isinstance(image_input, np.ndarray):
            arr = image_input
        else:
            return {"text": "", "lines": [], "engine": "none", "error": "Unsupported image input"}
    except Exception as exc:
        return {"text": "", "lines": [], "engine": "none", "error": str(exc)}

    # Primary: RapidOCR (local ONNX models, zero external binary requirement)
    try:
        ocr = _get_rapid_ocr()
        result, _ = ocr(arr)
        lines: List[Dict[str, Any]] = []
        if result:
            for item in result:
                # RapidOCR returns [bbox, text, confidence]
                if len(item) >= 3:
                    text_str = str(item[1]).strip()
                    conf = float(item[2])
                    if text_str:
                        lines.append({"text": text_str, "confidence": round(conf, 3)})
        combined = "\n".join(line["text"] for line in lines)
        return {
            "text": combined,
            "lines": lines,
            "engine": "rapidocr-onnxruntime",
            "error": None,
        }
    except Exception as rapid_err:
        # Secondary fallback: Tesseract OCR if binary installed on host
        try:
            import pytesseract
            pil_img = Image.fromarray(arr)
            text_out = pytesseract.image_to_string(pil_img).strip()
            lines = [{"text": ln.strip(), "confidence": 0.8} for ln in text_out.splitlines() if ln.strip()]
            return {
                "text": text_out,
                "lines": lines,
                "engine": "tesseract",
                "error": None,
            }
        except Exception as tess_err:
            return {
                "text": "",
                "lines": [],
                "engine": "unavailable",
                "error": f"RapidOCR error: {rapid_err}; Tesseract error: {tess_err}",
            }

import io
from typing import Dict, Any, List
from PIL import Image, ExifTags
import numpy as np
from app.services.media.hasher import compute_sha256_from_bytes, compute_perceptual_hashes
from app.services.media.ocr_engine import extract_text_from_image
from app.services.media.text_analyzer import analyze_text_content

def extract_exif_metadata(img: Image.Image) -> Dict[str, Any]:
    """Safely extract readable EXIF tags without breaking on corrupt binary tags."""
    exif_data = {}
    try:
        raw_exif = img.getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")[:64]
                elif not isinstance(value, (int, float, str, bool)):
                    value = str(value)[:64]
                exif_data[tag_name] = value
    except Exception:
        pass
    return exif_data

def estimate_skin_tone_ratio(img: Image.Image) -> float:
    """
    Forensic heuristic: estimate ratio of pixels conforming to standard human skin tone ranges
    in HSV space. Used as a screening indicator for non-consensual intimate content review.
    """
    try:
        thumb = img.convert("RGB").resize((120, 120))
        arr = np.array(thumb, dtype=np.float32) / 255.0

        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        delta = max_c - min_c

        v = max_c
        s = np.where(max_c > 0, delta / (max_c + 1e-6), 0)

        h = np.zeros_like(r)
        mask = delta > 0
        h = np.where(mask & (max_c == r), ((g - b) / (delta + 1e-6)) % 6, h)
        h = np.where(mask & (max_c == g), ((b - r) / (delta + 1e-6)) + 2, h)
        h = np.where(mask & (max_c == b), ((r - g) / (delta + 1e-6)) + 4, h)
        h = h * 60.0

        skin_mask = (
            ((h >= 0) & (h <= 50)) | (h >= 340)
        ) & (s >= 0.15) & (s <= 0.75) & (v >= 0.25) & (v <= 0.95)

        return round(float(np.mean(skin_mask)), 4)
    except Exception:
        return 0.0

def compute_ela_metrics(img: Image.Image) -> Dict[str, float]:
    """
    Error Level Analysis (ELA): re-save at JPEG 90 and measure regional residual variance
    to surface potential localized tampering or composite splices.
    """
    try:
        rgb = img.convert("RGB")
        # Resize very large images for bounded CPU latency
        rgb.thumbnail((800, 800))
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")

        diff = np.abs(np.array(rgb, dtype=np.float32) - np.array(resaved, dtype=np.float32))
        mean_diff = float(np.mean(diff))
        max_diff = float(np.max(diff))
        std_diff = float(np.std(diff))
        return {
            "ela_mean_error": round(mean_diff, 3),
            "ela_std_error": round(std_diff, 3),
            "ela_peak_error": round(max_diff, 3),
        }
    except Exception:
        return {"ela_mean_error": 0.0, "ela_std_error": 0.0, "ela_peak_error": 0.0}

def analyze_image_content(image_bytes: bytes, filename: str = "upload.jpg") -> Dict[str, Any]:
    """
    Full multimodal forensic inspection of image media:
    - Cryptographic SHA-256 & 4 perceptual hashes (pHash, dHash, aHash, wHash)
    - EXIF provenance metadata extraction & editing software trace detection
    - Error Level Analysis (ELA) compression residual assessment
    - Local OCR text extraction & linguistic threat/scam scanning
    - Chrominance skin-density screening indicator
    """
    sha256 = compute_sha256_from_bytes(image_bytes)

    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        img_format = img.format or "UNKNOWN"
        img_mode = img.mode
    except Exception as e:
        return {
            "content_type": "image",
            "risk_level": "medium",
            "confidence": 0.5,
            "findings": [{
                "category": "Format Error",
                "severity": "medium",
                "score": 0.5,
                "description": f"Failed to parse image file: {str(e)}"
            }],
            "evidence": [],
            "explanation": "Image file could not be decoded as standard visual media.",
            "limitations": ["Invalid or corrupt file bytes"],
            "recommended_action": "Re-upload clean uncorrupted file.",
            "raw_metadata": {"sha256": sha256}
        }

    hashes = compute_perceptual_hashes(img)
    exif = extract_exif_metadata(img)
    skin_ratio = estimate_skin_tone_ratio(img)
    ela_stats = compute_ela_metrics(img)
    ocr_result = extract_text_from_image(img)
    ocr_text = ocr_result.get("text", "").strip()

    findings: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    risk_score = 0.0
    limitations: List[str] = [
        "Chrominance and ELA heuristics assist forensic screening but do not replace human or multi-modal adjudication.",
        "Watermarking or heavy compression can shift perceptual hash Hamming distances."
    ]

    evidence.append({
        "indicator": "Perceptual pHash Fingerprint",
        "observed_value": hashes.get("phash"),
        "interpretation": "Visual perceptual hash invariant under moderate scaling or re-encoding."
    })
    evidence.append({
        "indicator": "Cryptographic SHA-256",
        "observed_value": sha256,
        "interpretation": "Bit-exact integrity digest for chain-of-custody verification."
    })

    # Check EXIF provenance & manipulation software signatures
    if not exif:
        findings.append({
            "category": "Metadata Stripping",
            "severity": "low",
            "score": 0.15,
            "description": "Image lacks camera EXIF provenance tags. Typical of social platform recompression or intentional scrubbing."
        })
    else:
        evidence.append({
            "indicator": "Hardware EXIF Tags",
            "observed_value": list(exif.keys())[:6],
            "interpretation": "Image retains embedded device/software provenance metadata."
        })
        software_tag = str(exif.get("Software", "")).lower()
        editing_tools = ("photoshop", "gimp", "stable diffusion", "midjourney", "dall-e", "comfyui", "faceapp")
        matched_tool = next((tool for tool in editing_tools if tool in software_tag), None)
        if matched_tool:
            findings.append({
                "category": "Synthetic / Editing Tool Signature",
                "severity": "medium",
                "score": 0.55,
                "description": f"EXIF Software metadata indicates processing via '{exif.get('Software')}'."
            })
            evidence.append({
                "indicator": "EXIF Software Tag",
                "observed_value": exif.get("Software"),
                "interpretation": "Provenance metadata reflects image editing or generative media software."
            })
            risk_score = max(risk_score, 0.55)

    # ELA Compression Residual check
    if ela_stats["ela_std_error"] > 12.0 and ela_stats["ela_peak_error"] > 80.0:
        findings.append({
            "category": "Compression Residual Anomaly (ELA)",
            "severity": "medium",
            "score": 0.45,
            "description": f"Localized JPEG residual variance detected (std={ela_stats['ela_std_error']}, peak={ela_stats['ela_peak_error']}). May indicate pasted regions or localized edits."
        })
        risk_score = max(risk_score, 0.45)

    # Skin ratio heuristic
    if skin_ratio > 0.40:
        sev = "high" if skin_ratio > 0.55 else "medium"
        sc = 0.85 if skin_ratio > 0.55 else 0.60
        findings.append({
            "category": "Potential Intimate / Nudity Surface Indicator",
            "severity": sev,
            "score": sc,
            "description": f"Image exhibits substantial skin-tone chromatic density ({skin_ratio * 100:.1f}%). Requires consent verification for NCII."
        })
        evidence.append({
            "indicator": "Chromatic Skin Surface Area",
            "observed_value": f"{skin_ratio * 100:.1f}%",
            "interpretation": "Elevated skin-tone density correlated with intimate or partially clad subjects."
        })
        risk_score = max(risk_score, sc)

    # Real OCR text analysis on embedded screenshot/image text
    if ocr_text:
        evidence.append({
            "indicator": f"Extracted OCR Text ({ocr_result.get('engine')})",
            "observed_value": ocr_text[:200],
            "interpretation": "Readable text extracted directly from image pixels for threat & scam screening."
        })
        ocr_text_analysis = analyze_text_content(ocr_text, context_type="image_ocr")
        for f in ocr_text_analysis.get("findings", []):
            findings.append({
                "category": f"OCR Text — {f['category']}",
                "severity": f["severity"],
                "score": f["score"],
                "description": f"Embedded image text matched indicator: {f['description']}"
            })
            risk_score = max(risk_score, float(f.get("score", 0.0)))
        for ev in ocr_text_analysis.get("evidence", []):
            evidence.append(ev)
    elif ocr_result.get("error"):
        limitations.append(f"OCR unavailable: {ocr_result['error']}")

    if width < 150 or height < 150:
        findings.append({
            "category": "Low Resolution Thumbnail",
            "severity": "low",
            "score": 0.1,
            "description": "Low resolution image may hinder fine-grained tampering or facial verification."
        })

    if risk_score >= 0.90:
        risk_level = "critical"
        confidence = 0.91
        rec_action = "Quarantine asset immediately, escalate into high-priority case, and prepare platform takedown notice."
    elif risk_score >= 0.70:
        risk_level = "high"
        confidence = 0.86
        rec_action = "Verify consent documentation, archive SHA-256 hash, and generate platform takedown report."
    elif risk_score >= 0.40:
        risk_level = "medium"
        confidence = 0.78
        rec_action = "Register asset in Perceptual Hash Vault and review extracted indicators manually."
    else:
        risk_level = "low"
        confidence = 0.90
        rec_action = "No hazardous indicators detected. Asset suitable for standard reference archiving."

    explanation = (
        f"Forensic visual & OCR inspection completed for {img_format} asset ({width}x{height}px). "
        f"Extracted {len(ocr_result.get('lines', []))} OCR text line(s), generated 4 perceptual hashes, "
        f"and flagged {len(findings)} indicator(s) with peak risk rating {risk_level.upper()}."
    )

    return {
        "content_type": "image",
        "risk_level": risk_level,
        "confidence": round(confidence, 2),
        "findings": findings,
        "evidence": evidence,
        "explanation": explanation,
        "limitations": limitations,
        "recommended_action": rec_action,
        "raw_metadata": {
            "filename": filename,
            "width": width,
            "height": height,
            "format": img_format,
            "mode": img_mode,
            "sha256": sha256,
            "hashes": hashes,
            "skin_ratio": skin_ratio,
            "ela": ela_stats,
            "ocr_text": ocr_text,
            "ocr_engine": ocr_result.get("engine"),
            "exif_summary": {k: str(v) for k, v in list(exif.items())[:10]}
        }
    }

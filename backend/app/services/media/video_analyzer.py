import os
import shutil
import subprocess
import tempfile
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from PIL import Image

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None

from app.services.media.hasher import compute_sha256_from_bytes, compute_perceptual_hashes
from app.services.media.image_analyzer import estimate_skin_tone_ratio
from app.services.media.ocr_engine import extract_text_from_image
from app.services.media.text_analyzer import analyze_text_content
from app.services.media.audio_analyzer import analyze_audio_content

def _resolve_ffmpeg_binary() -> Optional[str]:
    """Locate bundled imageio-ffmpeg binary or system ffmpeg."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    return shutil.which("ffmpeg")

def _extract_audio_wav(video_path: str) -> Optional[bytes]:
    """Extract mono 16kHz WAV audio track from video file using FFmpeg, if audio stream exists."""
    ffmpeg_exe = _resolve_ffmpeg_binary()
    if not ffmpeg_exe:
        return None

    wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(wav_fd)
    try:
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            wav_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=25)
        if proc.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 44:
            with open(wav_path, "rb") as f:
                return f.read()
    except Exception:
        pass
    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass
    return None

def _sample_video_frames(temp_path: str) -> Optional[Tuple[float, int, int, int, float, List[Tuple[int, float, Image.Image, np.ndarray]]]]:
    """Decode keyframe samples via OpenCV when available or PyAV fallback."""
    if cv2 is not None:
        cap = cv2.VideoCapture(temp_path)
        if not cap.isOpened():
            return None
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration_sec = total_frames / fps if fps > 0 else 0.0

        num_samples = min(8, max(1, total_frames // 10))
        sample_indices = (
            [int(i * (total_frames - 1) / max(1, num_samples - 1)) for i in range(num_samples)]
            if total_frames > 1 else [0]
        )
        sampled = []
        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)
            sampled.append((idx, idx / fps if fps > 0 else 0.0, pil_img, rgb_frame))
        cap.release()
        return fps, total_frames, width, height, duration_sec, sampled

    import av
    with av.open(temp_path) as container:
        video_streams = [s for s in container.streams if s.type == "video"]
        if not video_streams:
            return None
        vstream = video_streams[0]
        fps = float(vstream.average_rate) if vstream.average_rate else 25.0
        width = int(vstream.width or 0)
        height = int(vstream.height or 0)

        decoded: List[Tuple[int, float, Image.Image, np.ndarray]] = []
        for idx, frame in enumerate(container.decode(video=0)):
            pil_img = frame.to_image()
            ts = float(frame.time) if frame.time is not None else (idx / fps if fps > 0 else 0.0)
            decoded.append((idx, ts, pil_img, np.array(pil_img)))
            if idx >= 120:
                break

        total_frames = max(int(vstream.frames or 0), len(decoded))
        duration_sec = float(vstream.duration * vstream.time_base) if (vstream.duration and vstream.time_base) else (total_frames / fps if fps > 0 else 0.0)
        if not decoded:
            return fps, total_frames, width, height, duration_sec, []
        step = max(1, len(decoded) // 8)
        sampled = [decoded[i] for i in range(0, len(decoded), step)][:8]
        return fps, total_frames, width, height, duration_sec, sampled


def _has_av_audio_stream(temp_path: str) -> bool:
    try:
        import av
        with av.open(temp_path) as container:
            return any(s.type == "audio" for s in container.streams)
    except Exception:
        return False


def analyze_video_content(video_bytes: bytes, filename: str = "video.mp4", enable_transcription: bool = True) -> Dict[str, Any]:
    """
    Production multimodal video analysis:
    - Extracts container metadata via OpenCV (or PyAV fallback)
    - Samples evenly distributed keyframes across video duration
    - Computes frame perceptual hashes, skin-density indicators, and OCR text extraction per keyframe
    - Extracts audio track via FFmpeg (or PyAV container demux) and runs Whisper speech transcription
    - Produces timestamped findings and risk summary
    """
    sha256 = compute_sha256_from_bytes(video_bytes)

    suffix = os.path.splitext(filename)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_file.write(video_bytes)
        temp_path = temp_file.name

    findings: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    frame_hashes: List[Dict[str, Any]] = []
    ocr_timeline: List[Dict[str, Any]] = []
    transcript_segments: List[Dict[str, Any]] = []
    max_risk_score = 0.0
    limitations: List[str] = [
        "Keyframes represent discrete temporal samples across the video; brief sub-second frames between samples may require full-frame inspection."
    ]

    try:
        decoded_video = _sample_video_frames(temp_path)
        if decoded_video is None:
            return {
                "content_type": "video",
                "risk_level": "medium",
                "confidence": 0.5,
                "findings": [{
                    "category": "Format Error",
                    "severity": "medium",
                    "score": 0.5,
                    "description": "Unable to decode video stream."
                }],
                "evidence": [],
                "explanation": "Video container or codec is corrupt or unsupported.",
                "limitations": ["Codec compatibility"],
                "recommended_action": "Transcode to standard H.264 MP4 and retry.",
                "raw_metadata": {"sha256": sha256}
            }

        fps, total_frames, width, height, duration_sec, sampled_frames = decoded_video
        seen_ocr_texts = set()
        for idx, timestamp, pil_img, rgb_frame in sampled_frames:
            hashes = compute_perceptual_hashes(pil_img)
            skin_ratio = estimate_skin_tone_ratio(pil_img)
            ocr_res = extract_text_from_image(rgb_frame)
            frame_text = ocr_res.get("text", "").strip()

            frame_hashes.append({
                "frame_index": idx,
                "timestamp_sec": round(timestamp, 2),
                "phash": hashes.get("phash"),
                "skin_ratio": skin_ratio,
                "ocr_text": frame_text[:120] if frame_text else ""
            })

            if skin_ratio > 0.45:
                sc = 0.85 if skin_ratio > 0.60 else 0.60
                findings.append({
                    "category": "High Skin Surface Ratio",
                    "severity": "high" if skin_ratio > 0.60 else "medium",
                    "score": sc,
                    "timestamp_start": round(timestamp, 2),
                    "timestamp_end": round(timestamp + (1.0 / max(fps, 1.0)), 2),
                    "description": f"Keyframe at {timestamp:.2f}s demonstrates elevated skin surface density ({skin_ratio * 100:.1f}%)."
                })
                max_risk_score = max(max_risk_score, sc)

            if frame_text and frame_text not in seen_ocr_texts:
                seen_ocr_texts.add(frame_text)
                ocr_timeline.append({"timestamp_sec": round(timestamp, 2), "text": frame_text})
                text_eval = analyze_text_content(frame_text, context_type="video_frame_ocr")
                for tf in text_eval.get("findings", []):
                    findings.append({
                        "category": f"Frame OCR — {tf['category']}",
                        "severity": tf["severity"],
                        "score": tf["score"],
                        "timestamp_start": round(timestamp, 2),
                        "timestamp_end": round(timestamp + 1.0, 2),
                        "description": f"At {timestamp:.2f}s, embedded text triggered indicator: {tf['description']}"
                    })
                    max_risk_score = max(max_risk_score, float(tf.get("score", 0.0)))

        # Extract & analyze audio track via FFmpeg or PyAV container fallback
        audio_payload = _extract_audio_wav(temp_path)
        audio_filename = f"{filename}.wav"
        if audio_payload is None and _has_av_audio_stream(temp_path):
            audio_payload = video_bytes
            audio_filename = filename

        audio_meta: Dict[str, Any] = {"has_audio_stream": False}
        if audio_payload:
            audio_res = analyze_audio_content(
                audio_payload,
                filename=audio_filename,
                enable_transcription=enable_transcription,
            )
            audio_meta = {
                "has_audio_stream": True,
                "transcription_status": audio_res["raw_metadata"].get("transcription_status"),
                "audio_fingerprint": audio_res["raw_metadata"].get("audio_fingerprint"),
            }
            transcript_segments = audio_res["raw_metadata"].get("transcript_segments", [])
            for af in audio_res.get("findings", []):
                findings.append({
                    "category": f"Audio Track — {af['category']}",
                    "severity": af["severity"],
                    "score": af["score"],
                    "timestamp_start": af.get("timestamp_start", 0.0),
                    "timestamp_end": af.get("timestamp_end", duration_sec),
                    "description": af["description"],
                })
                max_risk_score = max(max_risk_score, float(af.get("score", 0.0)))
            for lim in audio_res.get("limitations", []):
                if lim not in limitations:
                    limitations.append(lim)
        else:
            limitations.append("No decodable audio stream present in video container.")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    evidence.append({
        "indicator": "Video Container Digest",
        "observed_value": sha256,
        "interpretation": "Cryptographic proof of video stream integrity."
    })
    evidence.append({
        "indicator": "Keyframe Perceptual Sequence",
        "observed_value": f"{len(frame_hashes)} keyframes hashed ({len(ocr_timeline)} with OCR text)",
        "interpretation": "Temporal visual fingerprint & OCR sequence for re-upload tracking."
    })
    if transcript_segments:
        evidence.append({
            "indicator": "Audio Track Speech Transcript",
            "observed_value": " ".join(s["text"] for s in transcript_segments)[:200],
            "interpretation": f"Extracted {len(transcript_segments)} timestamped speech segment(s) via Whisper."
        })

    if max_risk_score >= 0.90:
        risk_level = "critical"
        confidence = 0.90
        rec_action = "Initiate urgent video takedown workflow citing timestamped visual/audio violations."
    elif max_risk_score >= 0.70:
        risk_level = "high"
        confidence = 0.85
        rec_action = "Initiate video takedown workflow citing timestamped intimate, deepfake, or threat indicators."
    elif max_risk_score >= 0.35:
        risk_level = "medium"
        confidence = 0.78
        rec_action = "Add temporal keyframe hashes to Monitoring Vault for automated match detection."
    else:
        risk_level = "low"
        confidence = 0.88
        rec_action = "No hazardous visual, OCR, or audio markers identified across sampled chronology."

    explanation = (
        f"Forensic video processing inspected {total_frames} frames ({duration_sec:.1f}s at {fps:.1f} fps, {width}x{height}px). "
        f"Sampled {len(frame_hashes)} keyframes, extracted {len(ocr_timeline)} OCR text screen(s), "
        f"processed {len(transcript_segments)} speech segment(s), and logged {len(findings)} alert(s). "
        f"Overall risk evaluated as {risk_level.upper()}."
    )

    return {
        "content_type": "video",
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
            "fps": fps,
            "total_frames": total_frames,
            "duration_sec": round(duration_sec, 2),
            "sha256": sha256,
            "sampled_keyframes": frame_hashes,
            "ocr_timeline": ocr_timeline,
            "audio_metadata": audio_meta,
            "transcript_segments": transcript_segments,
        }
    }

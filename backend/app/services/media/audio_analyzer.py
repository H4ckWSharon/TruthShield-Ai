import hashlib
import io
import threading
import wave
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from app.core.config import settings
from app.services.media.hasher import compute_sha256_from_bytes
from app.services.media.text_analyzer import analyze_text_content

_whisper_lock = threading.Lock()
_whisper_model = None
_whisper_model_name: Optional[str] = None

def _get_whisper_model():
    """Lazy thread-safe loader for local Faster-Whisper model."""
    global _whisper_model, _whisper_model_name
    target_size = settings.WHISPER_MODEL_SIZE
    if _whisper_model is not None and _whisper_model_name == target_size:
        return _whisper_model

    with _whisper_lock:
        if _whisper_model is not None and _whisper_model_name == target_size:
            return _whisper_model
        from faster_whisper import WhisperModel
        try:
            _whisper_model = WhisperModel(
                target_size,
                device="cpu",
                compute_type="int8",
                local_files_only=True,
            )
            _whisper_model_name = target_size
        except Exception:
            # Fallback to tiny cached model if configured model isn't downloaded
            _whisper_model = WhisperModel(
                "tiny",
                device="cpu",
                compute_type="int8",
                local_files_only=True,
            )
            _whisper_model_name = "tiny"
    return _whisper_model

def decode_audio_to_pcm16k(audio_bytes: bytes) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Decode WAV/MP3/OGG/FLAC/M4A/AAC audio bytes into 16kHz mono float32 PCM array using PyAV,
    with standard-library wave fallback for uncompressed RIFF WAV.
    """
    meta: Dict[str, Any] = {
        "channels": 1,
        "sample_rate": 16000,
        "duration_sec": 0.0,
        "codec": "unknown",
    }

    # Try PyAV first for universal format decoding + resampling
    try:
        import av
        container = av.open(io.BytesIO(audio_bytes))
        audio_streams = [s for s in container.streams if s.type == "audio"]
        if audio_streams:
            stream = audio_streams[0]
            meta["channels"] = stream.channels or 1
            meta["sample_rate"] = stream.rate or 16000
            meta["codec"] = stream.codec_context.name if stream.codec_context else "av_audio"

            resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
            chunks: List[np.ndarray] = []
            for frame in container.decode(audio=0):
                resampled_frames = resampler.resample(frame)
                for rf in resampled_frames:
                    arr = rf.to_ndarray()
                    chunks.append(arr.reshape(-1))
            container.close()

            if chunks:
                pcm = np.concatenate(chunks).astype(np.float32)
                meta["duration_sec"] = round(len(pcm) / 16000.0, 2)
                return pcm, meta
    except Exception:
        pass

    # Fallback: Standard WAV decoder
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            sr = wf.getframerate()
            frames = wf.getnframes()
            raw = wf.readframes(frames)

            meta["channels"] = ch
            meta["sample_rate"] = sr
            meta["codec"] = "pcm_wav"
            meta["duration_sec"] = round(frames / float(sr or 16000), 2)

            if sw == 2:
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sw == 1:
                samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            else:
                samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0

            if ch > 1:
                samples = samples.reshape(-1, ch).mean(axis=1)

            if sr != 16000 and len(samples) > 0:
                target_len = max(1, int(len(samples) * 16000 / sr))
                samples = np.interp(
                    np.linspace(0, len(samples) - 1, target_len),
                    np.arange(len(samples)),
                    samples,
                ).astype(np.float32)

            return samples, meta
    except Exception:
        return np.array([], dtype=np.float32), meta

def compute_audio_fingerprint(pcm: np.ndarray) -> str:
    """
    Generate a 64-bit perceptual acoustic signature from short-time spectral energy bands.
    """
    if pcm.size < 512:
        return ""
    try:
        # Divide into 65 segments and compare consecutive RMS energy deltas to build 64 bits
        seg_len = max(1, len(pcm) // 65)
        energies = [float(np.mean(pcm[i * seg_len:(i + 1) * seg_len] ** 2)) for i in range(65)]
        bits = ["1" if energies[i + 1] > energies[i] else "0" for i in range(64)]
        val = int("".join(bits), 2)
        return f"{val:016x}"
    except Exception:
        return ""

def analyze_audio_content(audio_bytes: bytes, filename: str = "audio.wav", enable_transcription: bool = True) -> Dict[str, Any]:
    """
    Forensic audio analysis:
    - Real bitstream decoding via PyAV / WAV
    - Acoustic metrics & 64-bit spectral energy fingerprint
    - Local Faster-Whisper speech-to-text transcription (zero fabricated output)
    - Threat / extortion / harassment scanning on real transcript segments
    """
    sha256 = compute_sha256_from_bytes(audio_bytes)
    pcm, meta = decode_audio_to_pcm16k(audio_bytes)
    duration = meta.get("duration_sec", 0.0)
    audio_fp = compute_audio_fingerprint(pcm)

    rms_level = round(float(np.sqrt(np.mean(pcm ** 2))), 4) if pcm.size > 0 else 0.0
    peak_level = round(float(np.max(np.abs(pcm))), 4) if pcm.size > 0 else 0.0
    silence_ratio = round(float(np.mean(np.abs(pcm) < 0.01)), 4) if pcm.size > 0 else 1.0

    transcript_segments: List[Dict[str, Any]] = []
    limitations: List[str] = [
        "Speech analysis assists screening; biometric speaker attribution requires verified reference voiceprints."
    ]
    transcription_status = "disabled" if not enable_transcription else "skipped_empty_or_silent"

    if enable_transcription and pcm.size >= 1600 and rms_level > 0.001:
        try:
            model = _get_whisper_model()
            segments_iter, info = model.transcribe(pcm, beam_size=1, vad_filter=False)
            for seg in segments_iter:
                seg_text = seg.text.strip()
                if seg_text:
                    # avg_logprob mapped softly to [0, 1] confidence indicator
                    conf = round(max(0.0, min(1.0, float(np.exp(getattr(seg, "avg_logprob", -0.3))))), 2)
                    transcript_segments.append({
                        "start": round(float(seg.start), 2),
                        "end": round(float(seg.end), 2),
                        "text": seg_text,
                        "confidence": conf,
                    })
            transcription_status = f"transcribed_whisper_{_whisper_model_name}"
        except Exception as exc:
            transcription_status = "whisper_unavailable"
            limitations.append(f"Local Whisper transcription unavailable: {str(exc)}")
    elif enable_transcription:
        limitations.append("Audio stream contains negligible acoustic signal / silence; no spoken speech transcribed.")

    combined_transcript = " ".join(seg["text"] for seg in transcript_segments).strip()

    evidence: List[Dict[str, Any]] = [
        {
            "indicator": "Audio Bitstream SHA-256",
            "observed_value": sha256,
            "interpretation": "Cryptographic digest ensuring chain-of-custody for audio evidence."
        },
        {
            "indicator": "Acoustic Stream Specs",
            "observed_value": f"{meta['sample_rate']} Hz, {meta['channels']} ch ({meta['codec']}), RMS={rms_level}",
            "interpretation": "Decoded acoustic characteristics from media container."
        },
    ]
    if audio_fp:
        evidence.append({
            "indicator": "Acoustic Spectral Fingerprint",
            "observed_value": audio_fp,
            "interpretation": "64-bit energy-delta perceptual digest for duplicate audio tracking."
        })

    if combined_transcript:
        evidence.append({
            "indicator": f"Whisper Transcript ({_whisper_model_name})",
            "observed_value": combined_transcript[:240],
            "interpretation": f"Extracted {len(transcript_segments)} spoken segment(s) locally."
        })
        text_analysis = analyze_text_content(combined_transcript, context_type="audio_transcription")
        findings = list(text_analysis.get("findings", []))
        # Map segment timestamps onto matched findings
        for finding in findings:
            for seg in transcript_segments:
                finding.setdefault("timestamp_start", seg["start"])
                finding.setdefault("timestamp_end", seg["end"])
                break
        risk_level = text_analysis.get("risk_level", "low")
        confidence = text_analysis.get("confidence", 0.85)
        rec_action = text_analysis.get("recommended_action", "Retain audio evidence in encrypted vault.")
    else:
        findings = []
        risk_level = "low"
        confidence = 0.85
        rec_action = "No hazardous spoken threats detected in decoded stream. Archive cryptographic digest."

    explanation = (
        f"Audio forensic pipeline inspected {duration:.2f}s stream ({meta['codec']}). "
        f"Transcription status: {transcription_status} ({len(transcript_segments)} segment(s)). "
        f"Overall risk evaluated as {risk_level.upper()}."
    )

    return {
        "content_type": "audio",
        "risk_level": risk_level,
        "confidence": confidence,
        "findings": findings,
        "evidence": evidence,
        "explanation": explanation,
        "limitations": limitations,
        "recommended_action": rec_action,
        "raw_metadata": {
            "filename": filename,
            "duration_sec": duration,
            "audio_specs": meta,
            "rms_level": rms_level,
            "peak_level": peak_level,
            "silence_ratio": silence_ratio,
            "audio_fingerprint": audio_fp,
            "sha256": sha256,
            "transcription_status": transcription_status,
            "transcript": combined_transcript,
            "transcript_segments": transcript_segments,
        }
    }

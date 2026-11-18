import io
import math
import os
import struct
import tempfile
import wave
import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.media.hasher import compute_perceptual_hashes, compute_hamming_distance, calculate_similarity_score
from app.services.media.url_analyzer import validate_url_safe, SSRFSecurityViolation
from app.services.reports.pdf_generator import generate_pdf_report
from app.core.file_validator import inspect_file_magic, UnsafeFileTypeError


def _make_png_bytes(width: int = 320, height: int = 120, text: str = "") -> bytes:
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    if text:
        draw = ImageDraw.Draw(img)
        draw.text((20, 45), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_wav_bytes(duration_sec: float = 0.5, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    num_samples = int(duration_sec * sample_rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            val = int(12000 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))
    return buf.getvalue()


def _make_avi_bytes() -> bytes:
    fd, path = tempfile.mkstemp(suffix=".avi")
    os.close(fd)
    try:
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(path, fourcc, 10.0, (160, 120))
        for i in range(12):
            frame = np.full((120, 160, 3), fill_value=(i * 15 % 255, 80, 140), dtype=np.uint8)
            writer.write(frame)
        writer.release()
        with open(path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_root_and_health(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "TruthShield AI"
    assert data["company"] == "TruthShield AI"
    assert data["auth_required"] is False

    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"
    assert res_health.headers.get("X-Content-Type-Options") == "nosniff"
    assert res_health.headers.get("X-Frame-Options") == "DENY"


def test_direct_no_auth_workspace_access(client):
    # Direct access without Bearer token must succeed across core endpoints
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "admin"

    dash_res = client.get("/api/v1/dashboard/stats")
    assert dash_res.status_code == 200
    assert "total_cases" in dash_res.json()

    health_res = client.get("/api/v1/admin/system-health")
    assert health_res.status_code == 200
    assert health_res.json()["database_status"] == "operational"


def test_auth_privilege_escalation_blocked_and_password_reset(client):
    # First registered explicit user when admin exists must NOT gain admin via payload injection
    reg_payload = {
        "email": "attacker@truthshield.com",
        "password": "StrongPassword2026!",
        "full_name": "Standard Reporter",
        "role": "admin"
    }
    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 201
    created = res.json()
    assert created["role"] == "user"

    # Log in as standard user
    login_res = client.post("/api/v1/auth/login", json={
        "email": "attacker@truthshield.com",
        "password": "StrongPassword2026!"
    })
    assert login_res.status_code == 200
    user_token = login_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Verify standard user is blocked from admin center
    admin_res = client.get("/api/v1/admin/users", headers=user_headers)
    assert admin_res.status_code == 403

    # Password reset request + confirm flow
    reset_req = client.post("/api/v1/auth/password-reset-request", json={"email": "attacker@truthshield.com"})
    assert reset_req.status_code == 200
    reset_token = reset_req.json().get("dev_reset_token")
    assert reset_token

    reset_confirm = client.post("/api/v1/auth/password-reset-confirm", json={
        "reset_token": reset_token,
        "new_password": "UpdatedPassword2026!"
    })
    assert reset_confirm.status_code == 200

    # Login with updated password succeeds
    new_login = client.post("/api/v1/auth/login", json={
        "email": "attacker@truthshield.com",
        "password": "UpdatedPassword2026!"
    })
    assert new_login.status_code == 200


def test_case_lifecycle_and_export(client):
    c1 = client.post("/api/v1/cases", json={
        "title": "Deepfake Video Impersonation",
        "category": "deepfake",
        "description": "Manipulated video clip",
        "risk_level": "high",
        "urls": ["https://example.com/fake1"]
    })
    assert c1.status_code == 201
    case1 = c1.json()
    assert "TSA-" in case1["case_number"]

    c2 = client.post("/api/v1/cases", json={
        "title": "Harassment Campaign",
        "category": "harassment",
        "risk_level": "medium",
        "urls": []
    })
    assert c2.status_code == 201
    case2 = c2.json()
    assert case1["case_number"] != case2["case_number"]

    # Delete case1 then create case3 to verify no duplicate case_number collision
    del_res = client.delete(f"/api/v1/cases/{case1['id']}")
    assert del_res.status_code == 204

    c3 = client.post("/api/v1/cases", json={
        "title": "Phishing Portal Takedown",
        "category": "phishing",
        "risk_level": "critical",
        "urls": ["https://example.com/login-scam"]
    })
    assert c3.status_code == 201
    case3 = c3.json()
    assert case3["case_number"] != case2["case_number"]

    # Update & Export JSON bundle
    upd = client.patch(f"/api/v1/cases/{case3['id']}", json={"status": "verified", "notes": "Confirmed phishing"})
    assert upd.status_code == 200
    assert upd.json()["status"] == "verified"

    exp = client.get(f"/api/v1/cases/{case3['id']}/export")
    assert exp.status_code == 200
    assert exp.json()["case"]["case_number"] == case3["case_number"]


def test_evidence_magic_bytes_encryption_and_shredding(client):
    # 1. Disguised Windows PE executable claiming to be image/png MUST be blocked
    exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64
    with pytest.raises(UnsafeFileTypeError):
        inspect_file_magic(exe_bytes, "malware.png")

    bad_upload = client.post(
        "/api/v1/evidence/upload",
        files={"file": ("malware.png", exe_bytes, "image/png")},
    )
    assert bad_upload.status_code == 415

    # 2. Valid PNG upload -> encrypted on disk, decrypted on download, shredded on delete
    png_bytes = _make_png_bytes(200, 100, "Evidence Asset")
    up_res = client.post(
        "/api/v1/evidence/upload",
        files={"file": ("evidence.png", png_bytes, "image/png")},
        data={"description": "Screenshot proof", "is_sensitive": "true"},
    )
    assert up_res.status_code == 201
    ev = up_res.json()
    assert ev["mime_type"] == "image/png"
    assert ev["is_sensitive"] is True
    assert ev["metadata_json"]["encrypted_at_rest"] is True

    # Download must return exact original PNG bytes
    dl_res = client.get(f"/api/v1/evidence/{ev['id']}/download")
    assert dl_res.status_code == 200
    assert dl_res.content == png_bytes

    # List evidence
    list_res = client.get("/api/v1/evidence")
    assert list_res.status_code == 200
    assert any(item["id"] == ev["id"] for item in list_res.json())

    # Delete & shred
    del_res = client.delete(f"/api/v1/evidence/{ev['id']}")
    assert del_res.status_code == 204


def test_text_and_image_ocr_analysis(client):
    benign = client.post("/api/v1/analysis/text", json={"text": "Routine status update for team."})
    assert benign.status_code == 200
    assert benign.json()["risk_level"] == "low"

    threat = client.post("/api/v1/analysis/text", json={"text": "I will murder you and destroy your house."})
    assert threat.status_code == 200
    assert threat.json()["risk_level"] in ("high", "critical")
    assert len(threat.json()["findings"]) > 0

    # Render image containing real threat text and verify RapidOCR extracts & flags it
    threat_img = _make_png_bytes(420, 140, "I will murder you")
    img_res = client.post(
        "/api/v1/analysis/image",
        files={"file": ("threat_banner.png", threat_img, "image/png")},
    )
    assert img_res.status_code == 200
    img_data = img_res.json()
    assert "murder" in img_data["raw_metadata"]["ocr_text"].lower()
    assert img_data["risk_level"] in ("high", "critical")


def test_video_and_audio_analysis_pipelines(client):
    avi_bytes = _make_avi_bytes()
    vid_res = client.post(
        "/api/v1/analysis/video",
        files={"file": ("sample.avi", avi_bytes, "video/x-msvideo")},
    )
    assert vid_res.status_code == 200
    v_data = vid_res.json()
    assert v_data["content_type"] == "video"
    assert len(v_data["raw_metadata"]["sampled_keyframes"]) >= 1

    wav_bytes = _make_wav_bytes()
    aud_res = client.post(
        "/api/v1/analysis/audio",
        files={"file": ("tone.wav", wav_bytes, "audio/wav")},
    )
    assert aud_res.status_code == 200
    a_data = aud_res.json()
    assert a_data["content_type"] == "audio"
    assert a_data["raw_metadata"]["duration_sec"] > 0
    assert len(a_data["raw_metadata"]["audio_fingerprint"]) == 16
    # Ensure no fabricated hardcoded placeholder sentence appears
    assert "Audio segment processed via TruthShield" not in a_data["raw_metadata"].get("transcript", "")


def test_ssrf_blocking_comprehensive(client):
    blocked_targets = [
        "http://127.0.0.1:8080/admin",
        "http://localhost:3000",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/",
        "http://[::ffff:127.0.0.1]/admin",
        "file:///etc/passwd",
    ]
    for target in blocked_targets:
        with pytest.raises(SSRFSecurityViolation):
            validate_url_safe(target)

    api_block = client.post("/api/v1/analysis/url", json={"url": "http://169.254.169.254/latest/meta-data"})
    assert api_block.status_code == 400
    assert "SSRF Protection" in api_block.json()["detail"]


def test_public_domain_url_allowed(monkeypatch):
    import socket
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("157.240.22.174", 0))]
    )
    safe_url, ips = validate_url_safe("https://www.instagram.com/p/De3WIpqz5PJ/?rpxt=MWh3c2g0cmRvend4YQ%3D%3D")
    assert safe_url.startswith("https://www.instagram.com/")
    assert ips == ["157.240.22.174"]


def test_fingerprinting_and_duplicate_matches(client):
    img_bytes = _make_png_bytes(256, 128, "Copyright Master Asset 991")
    reg_res = client.post(
        "/api/v1/fingerprints/register",
        files={"file": ("master.png", img_bytes, "image/png")},
        data={"title": "Master Brand Image", "media_type": "image"},
    )
    assert reg_res.status_code == 201
    fp = reg_res.json()
    assert fp["phash"]

    # Exact file search
    search_exact = client.post(
        "/api/v1/fingerprints/search",
        files={"file": ("probe.png", img_bytes, "image/png")},
        data={"max_distance": "10"},
    )
    assert search_exact.status_code == 200
    matches = search_exact.json()
    assert len(matches) >= 1
    assert matches[0]["match_type"] == "exact"
    assert matches[0]["similarity_score"] == 1.0

    # Match history persisted
    hist = client.get("/api/v1/fingerprints/matches")
    assert hist.status_code == 200
    assert len(hist.json()) >= 1


def test_reports_removal_and_admin_endpoints(client):
    c_res = client.post("/api/v1/cases", json={
        "title": "Removal Workflow Integration Case",
        "category": "impersonation",
        "risk_level": "high",
        "urls": ["https://example.com/impersonation-test"]
    })
    assert c_res.status_code == 201
    case_id = c_res.json()["id"]

    # Prepare removal dossier
    prep = client.post("/api/v1/removal/prepare-report", json={
        "case_id": case_id,
        "platform": "instagram",
        "violation_type": "impersonation"
    })
    assert prep.status_code == 201
    wf_id = prep.json()["id"]

    # Human approval
    appr = client.post("/api/v1/removal/approve", json={
        "workflow_id": wf_id,
        "approved": True,
        "submission_reference": "META-REF-12345",
        "notes": "Verified identity mismatch"
    })
    assert appr.status_code == 200
    assert appr.json()["human_approved"] is True

    # PDF generation and download
    rep = client.post("/api/v1/reports/generate", json={
        "case_id": case_id,
        "template_type": "instagram"
    })
    assert rep.status_code == 201
    rep_id = rep.json()["id"]

    pdf_dl = client.get(f"/api/v1/reports/{rep_id}/download")
    assert pdf_dl.status_code == 200
    assert pdf_dl.content.startswith(b"%PDF-")

    # Admin models & audit logs
    models = client.get("/api/v1/admin/models")
    assert models.status_code == 200
    assert len(models.json()) >= 1

    logs = client.get("/api/v1/admin/audit-logs")
    assert logs.status_code == 200
    assert len(logs.json()) >= 1


def test_perceptual_hashing_unit():
    img1 = Image.new("RGB", (100, 100), color=(73, 109, 137))
    hashes1 = compute_perceptual_hashes(img1)
    assert len(hashes1["phash"]) > 0
    assert compute_hamming_distance(hashes1["phash"], hashes1["phash"]) == 0
    assert calculate_similarity_score(hashes1["phash"], hashes1["phash"]) == 1.0


def test_pdf_report_generation_unit():
    case_data = {
        "case_number": "TSA-2026-TEST",
        "title": "Automated Test Case",
        "category": "impersonation",
        "status": "verified",
        "risk_level": "high",
        "description": "Evidence compilation for automated verification.",
        "urls": ["https://example.com/offending_page"]
    }
    pdf_path = generate_pdf_report(case_data, template_type="instagram")
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000

import socket
import ipaddress
import re
from urllib.parse import urlparse, urljoin
from typing import Dict, Any, List, Tuple
import httpx

from app.services.media.text_analyzer import analyze_text_content

MAX_URL_RESPONSE_BYTES = 2 * 1024 * 1024  # 2MB cap for safe HTTP metadata scraping
MAX_REDIRECT_HOPS = 5

class SSRFSecurityViolation(Exception):
    pass

def _check_ip_allowed(ip_str: str) -> None:
    """Validate an IPv4/IPv6 address (including IPv4-mapped IPv6) is strictly public."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        raise SSRFSecurityViolation(f"Invalid resolved IP format: {ip_str}")

    candidates = [ip]
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        candidates.append(ip.ipv4_mapped)

    for candidate in candidates:
        if candidate.is_loopback:
            raise SSRFSecurityViolation(f"Target resolves to loopback address: {ip_str}")
        if candidate.is_private:
            raise SSRFSecurityViolation(f"Target resolves to private internal network: {ip_str}")
        if candidate.is_link_local:
            raise SSRFSecurityViolation(f"Target resolves to link-local/cloud metadata address: {ip_str}")
        if candidate.is_reserved or candidate.is_multicast or candidate.is_unspecified:
            raise SSRFSecurityViolation(f"Target resolves to restricted IP range: {ip_str}")

def validate_url_safe(url: str) -> Tuple[str, List[str]]:
    """
    Strict SSRF validation.
    Blocks localhost, RFC 1918 private IPs, cloud metadata IPs (169.254.169.254),
    IPv4-mapped IPv6 addresses, and non-http/https protocols.
    Returns (url, resolved_ips).
    """
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise SSRFSecurityViolation(
            f"Invalid URL protocol: '{parsed.scheme}'. Only http and https are allowed."
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityViolation("Missing hostname in target URL.")

    blocked_hostnames = {
        "localhost", "127.0.0.1", "0.0.0.0", "::1",
        "metadata.google.internal", "instance-data", "169.254.169.254"
    }
    if hostname.lower() in blocked_hostnames or hostname.lower().endswith(".localhost"):
        raise SSRFSecurityViolation(f"Access to '{hostname}' is blocked by TruthShield SSRF Protection.")

    # Direct IP literal check before DNS resolution
    try:
        ipaddress.ip_address(hostname.split("%")[0])
        _check_ip_allowed(hostname.split("%")[0])
    except ValueError:
        pass

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Could not resolve domain name: '{hostname}'")

    resolved_ips: List[str] = []
    for entry in addr_info:
        ip_str = entry[4][0].split("%")[0]
        _check_ip_allowed(ip_str)
        if ip_str not in resolved_ips:
            resolved_ips.append(ip_str)

    if not resolved_ips:
        raise ValueError(f"No public IP addresses resolved for '{hostname}'")

    return url, resolved_ips

async def _safe_fetch_with_redirects(url: str) -> Dict[str, Any]:
    """
    Perform HTTP GET with manual redirect hop validation and strict streaming byte cap.
    Prevents redirect-based SSRF and memory exhaustion.
    """
    current_url, resolved_ips = validate_url_safe(url)
    redirect_chain: List[str] = [current_url]
    headers = {"User-Agent": "TruthShield-Inspector/2.0 (TruthShield AI)"}

    async with httpx.AsyncClient(timeout=6.0, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECT_HOPS + 1):
            async with client.stream("GET", current_url, headers=headers) as resp:
                if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        break
                    next_url = urljoin(current_url, location)
                    current_url, resolved_ips = validate_url_safe(next_url)
                    redirect_chain.append(current_url)
                    continue

                chunks: List[bytes] = []
                total_bytes = 0
                truncated = False
                async for chunk in resp.aiter_bytes():
                    if total_bytes + len(chunk) > MAX_URL_RESPONSE_BYTES:
                        remaining = MAX_URL_RESPONSE_BYTES - total_bytes
                        if remaining > 0:
                            chunks.append(chunk[:remaining])
                        truncated = True
                        break
                    chunks.append(chunk)
                    total_bytes += len(chunk)

                body_bytes = b"".join(chunks)
                text_body = body_bytes.decode("utf-8", errors="replace")

                return {
                    "status_code": resp.status_code,
                    "final_url": current_url,
                    "redirect_chain": redirect_chain,
                    "resolved_ips": resolved_ips,
                    "content_type": resp.headers.get("content-type", ""),
                    "server": resp.headers.get("server", "hidden"),
                    "content_length": len(body_bytes),
                    "truncated": truncated,
                    "text_body": text_body,
                }

    return {
        "status_code": 310,
        "final_url": current_url,
        "redirect_chain": redirect_chain,
        "resolved_ips": resolved_ips,
        "error": "Exceeded maximum redirect hops",
    }

async def verify_url_live_status(url: str) -> Dict[str, Any]:
    """
    SSRF-safe live check used by Removal Assistance to determine whether a reported
    URL is still accessible or has been removed (HTTP 404/410 or platform unavailability notice).
    Never claims removal unless verified.
    """
    try:
        meta = await _safe_fetch_with_redirects(url)
    except SSRFSecurityViolation:
        raise
    except Exception as exc:
        return {
            "url": url,
            "http_status": None,
            "verification_status": "unreachable_or_error",
            "confirmed_removed": False,
            "detail": str(exc),
        }

    code = meta.get("status_code")
    body_lower = meta.get("text_body", "")[:16384].lower()

    if code in (404, 410):
        return {
            "url": url,
            "http_status": code,
            "verification_status": "confirmed_removed",
            "confirmed_removed": True,
            "detail": f"Origin server returned HTTP {code} (Gone/Not Found).",
        }

    unavailable_markers = (
        "sorry, this page isn't available",
        "the link you followed may be broken",
        "this video isn't available anymore",
        "this account has been suspended",
        "content unavailable",
    )
    if any(marker in body_lower for marker in unavailable_markers):
        return {
            "url": url,
            "http_status": code,
            "verification_status": "confirmed_removed",
            "confirmed_removed": True,
            "detail": "Platform returned an explicit content-unavailable notice.",
        }

    return {
        "url": url,
        "http_status": code,
        "verification_status": "still_accessible",
        "confirmed_removed": False,
        "detail": f"Endpoint responded with HTTP {code}; content appears active.",
    }

async def analyze_url_target(url: str) -> Dict[str, Any]:
    """
    Safely inspect a public URL, verify every redirect hop against SSRF rules,
    extract metadata and OpenGraph tags, and assess phishing/impersonation/text hazards.
    """
    safe_url, initial_ips = validate_url_safe(url)
    parsed = urlparse(safe_url)
    hostname = parsed.hostname or ""

    findings: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    risk_score = 0.0

    # Heuristic 1: Brand impersonation
    brand_keywords = ["paypal", "meta", "facebook", "instagram", "google", "microsoft", "apple", "bank", "netflix", "chase"]
    matched_brands = [b for b in brand_keywords if b in hostname.lower()]
    is_official_brand = any(
        hostname.lower().endswith(f".{b}.com") or hostname.lower() == f"{b}.com"
        for b in matched_brands
    )

    if matched_brands and not is_official_brand:
        findings.append({
            "category": "Brand Impersonation / Phishing",
            "severity": "high",
            "score": 0.85,
            "description": f"Domain name contains brand keyword '{matched_brands[0]}' outside official root domains."
        })
        evidence.append({
            "indicator": "Domain Brand Spoofing",
            "observed_value": hostname,
            "interpretation": f"Potential phishing or impersonation targeting {matched_brands[0]} users."
        })
        risk_score += 0.85

    # Heuristic 2: Excessive subdomains or insecure HTTP
    if len(hostname.split(".")) > 4:
        findings.append({
            "category": "Obfuscated Subdomain Structure",
            "severity": "medium",
            "score": 0.5,
            "description": "Unusually deep subdomain hierarchy often used to mask malicious destinations."
        })
        risk_score += 0.4

    if parsed.scheme.lower() == "http":
        findings.append({
            "category": "Unencrypted Transport (HTTP)",
            "severity": "low",
            "score": 0.25,
            "description": "Target uses plaintext HTTP without TLS certificate authentication."
        })
        risk_score += 0.2

    # Heuristic 3: High-risk TLDs
    suspicious_tlds = (".top", ".xyz", ".club", ".work", ".cam", ".click", ".buzz", ".monster", ".gq", ".cf", ".ml")
    if any(hostname.lower().endswith(tld) for tld in suspicious_tlds):
        findings.append({
            "category": "High-Risk Top-Level Domain",
            "severity": "medium",
            "score": 0.45,
            "description": "Domain utilizes a TLD frequently observed in disposable abuse infrastructure."
        })
        risk_score += 0.4

    # Heuristic 4: Credential harvesting keywords
    harvesting_tokens = ["login", "signin", "verify-account", "wallet", "recover", "security-update", "confirm-identity"]
    matched_tokens = [tok for tok in harvesting_tokens if tok in parsed.path.lower() or tok in parsed.query.lower()]
    if matched_tokens:
        findings.append({
            "category": "Credential Harvesting Path",
            "severity": "high",
            "score": 0.7,
            "description": f"URL path/query contains sensitive credential tokens: {matched_tokens}."
        })
        evidence.append({
            "indicator": "Sensitive Action Parameter",
            "observed_value": matched_tokens,
            "interpretation": "URL structure resembles credential harvesting or authentication spoofing."
        })
        risk_score += 0.6

    # Safe HTTP fetch with redirect validation
    http_metadata: Dict[str, Any] = {"resolved_ips": initial_ips}
    try:
        fetch_res = await _safe_fetch_with_redirects(safe_url)
        text_body = fetch_res.pop("text_body", "")
        http_metadata.update(fetch_res)

        if "text/html" in http_metadata.get("content_type", "").lower() and text_body:
            title_match = re.search(r"<title>(.*?)</title>", text_body, re.IGNORECASE | re.DOTALL)
            if title_match:
                http_metadata["page_title"] = re.sub(r"\s+", " ", title_match.group(1)).strip()[:200]

            desc_match = re.search(
                r'<meta\s+(?:name=["\']description["\']|property=["\']og:description["\'])\s+content=["\'](.*?)["\']',
                text_body,
                re.IGNORECASE | re.DOTALL,
            )
            if desc_match:
                http_metadata["meta_description"] = desc_match.group(1).strip()[:300]

            # Strip HTML tags and inspect visible page snippet via text threat analyzer
            visible_snippet = re.sub(r"<script.*?>.*?</script>|<style.*?>.*?</style>|<[^>]+>", " ", text_body, flags=re.IGNORECASE | re.DOTALL)
            visible_snippet = re.sub(r"\s+", " ", visible_snippet).strip()[:3000]
            if visible_snippet:
                page_text_eval = analyze_text_content(visible_snippet, context_type="web_page")
                for f in page_text_eval.get("findings", []):
                    findings.append(f)
                    risk_score += float(f.get("score", 0.0))
    except SSRFSecurityViolation:
        raise
    except Exception as e:
        http_metadata["fetch_status"] = "network_error_or_timeout"
        http_metadata["error"] = str(e)

    if risk_score >= 1.2:
        risk_level = "critical"
        confidence = min(0.95, 0.70 + (risk_score * 0.15))
    elif risk_score >= 0.7:
        risk_level = "high"
        confidence = min(0.90, 0.65 + (risk_score * 0.15))
    elif risk_score >= 0.3:
        risk_level = "medium"
        confidence = 0.75
    else:
        risk_level = "low"
        confidence = 0.85

    explanation = (
        f"SSRF-safe URL forensic inspection examined '{hostname}' ({', '.join(initial_ips[:2])}). "
        f"Identified {len(findings)} risk indicator(s) with overall risk rating {risk_level.upper()}."
    )

    recommended_action = (
        "Immediate domain report to registrar/hosting abuse desk and blocklist submission recommended."
        if risk_level in ("high", "critical")
        else "Proceed with caution; verify platform TLS certificate and official domain ownership."
    )

    return {
        "content_type": "url",
        "risk_level": risk_level,
        "confidence": round(confidence, 2),
        "findings": findings,
        "evidence": evidence,
        "explanation": explanation,
        "limitations": [
            "URL reputation inspection captures static HTTP HTML/headers without executing client-side JavaScript.",
            "Geo-fenced or authenticated platforms may serve login walls instead of post content."
        ],
        "recommended_action": recommended_action,
        "raw_metadata": http_metadata,
    }

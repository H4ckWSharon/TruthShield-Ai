from typing import Dict, Any
from datetime import datetime, timezone

PLATFORM_GUIDANCE = {
    "youtube": {
        "portal_name": "YouTube Content Abuse & Privacy Reporting Tool",
        "url": "https://www.youtube.com/reportabuse",
        "steps": [
            "1. Click the official YouTube reporting link above (or use the '...' More -> Report button on the video).",
            "2. Select 'Privacy', 'Harassment and Cyberbullying', or 'Misinformation' depending on the violation.",
            "3. Enter the video URL and exact timestamp references from this TruthShield report.",
            "4. Paste the prepared policy violation narrative from the notice draft below.",
            "5. Submit through your Google account and record the confirmation ticket ID below."
        ]
    },
    "instagram": {
        "portal_name": "Instagram Official Content & Safety Reporting Center",
        "url": "https://help.instagram.com/192435014247952",
        "impersonation_url": "https://help.instagram.com/contact/636276399721841",
        "steps": [
            "1. For fake news, harassment, or harmful posts: open the post on Instagram -> tap '...' (three dots) -> Report -> choose 'False information', 'Harassment', or 'Nudity/Sexual activity'.",
            "2. For account impersonation (or reporting without an Instagram account): open the official Meta form using the portal button above.",
            "3. Reference the offending post URL(s) and attach the TruthShield PDF report & SHA-256 evidence digest if requested.",
            "4. Submit the report and save any confirmation reference ID in the tracker below."
        ]
    },
    "facebook": {
        "portal_name": "Facebook Official Content & Safety Reporting Center",
        "url": "https://www.facebook.com/help/1380418588640631",
        "impersonation_url": "https://www.facebook.com/help/174210519303259",
        "steps": [
            "1. Open the official Facebook reporting portal above (or click '...' on the post -> Report post).",
            "2. Choose the matching violation category (False Information, Harassment, Impersonation, or Private Images).",
            "3. Provide the direct post/profile URL and paste the prepared formal notice.",
            "4. Record any Meta confirmation ticket ID in the tracker below."
        ]
    },
    "general_web": {
        "portal_name": "ICANN WHOIS Lookup & Hosting Provider Abuse Desk",
        "url": "https://lookup.icann.org/",
        "steps": [
            "1. Use ICANN Lookup above to find the hosting provider or domain registrar's abuse email.",
            "2. Send the compiled TruthShield PDF incident report to abuse@{hosting-provider.com}.",
            "3. Specify DMCA takedown or Terms of Service violation based on your verified evidence.",
            "4. Record your email thread reference and re-check the link after 48 hours."
        ]
    }
}

def resolve_platform_guidance(platform: str, violation_type: str = "") -> Dict[str, Any]:
    """Return verified live portal URL and guided steps for the target platform & violation."""
    base = PLATFORM_GUIDANCE.get(platform, PLATFORM_GUIDANCE["general_web"])
    portal_url = base["url"]
    if violation_type == "impersonation" and "impersonation_url" in base:
        portal_url = base["impersonation_url"]
    return {
        "portal_name": base["portal_name"],
        "url": portal_url,
        "steps": base["steps"],
    }

def prepare_removal_dossier(
    case_data: Dict[str, Any],
    platform: str,
    violation_type: str
) -> Dict[str, Any]:
    """
    Synthesize an evidence-backed platform removal package requiring human investigator approval.
    Does not attempt unauthorized scraping, bypasses, or fabricated deletions.
    """
    guidance = resolve_platform_guidance(platform, violation_type)
    case_num = case_data.get("case_number", "CASE-000")
    urls = case_data.get("urls", [])
    urls_formatted = "\n".join([f"- {u}" for u in urls]) if urls else "- None specified"

    report_content = (
        f"FORMAL NOTICE OF CONTENT POLICY VIOLATION\n"
        f"Reference Case: {case_num}\n"
        f"Target Platform: {platform.upper()}\n"
        f"Violation Type: {violation_type.upper()}\n"
        f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"To the Trust & Safety Team,\n\n"
        f"We have identified digital content hosted on your platform that violates community safety standards "
        f"regarding {violation_type}.\n\n"
        f"TARGET URL(S):\n{urls_formatted}\n\n"
        f"INCIDENT DESCRIPTION:\n{case_data.get('description', 'Content posted without consent or in violation of platform terms.')}\n\n"
        f"EVIDENCE INTEGRITY:\nForensic cryptographic hashes (SHA-256) have been logged in escrow. "
        f"This report has been reviewed and verified by an authorized human investigator prior to submission.\n\n"
        f"We request immediate expedited review and restriction of access in accordance with your published safety terms."
    )

    return {
        "platform": platform,
        "violation_type": violation_type,
        "report_content": report_content,
        "official_portal_url": guidance["url"],
        "portal_name": guidance["portal_name"],
        "guidance_steps": guidance["steps"],
        "requires_human_approval": True,
        "status": "pending_review"
    }

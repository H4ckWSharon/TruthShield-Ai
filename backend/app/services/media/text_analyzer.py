import re
from typing import Dict, Any, List

# Forensic indicator lexicons
THREAT_PATTERNS = [
    (r"\b(i will|im gonna|going to)\s+(kill|murder|shoot|stab|harm|drown|strangle|destroy)\b", "Direct Violent Threat", 0.95),
    (r"\b(watch your back|you will pay|you will regret this|count your days)\b", "Intimidation / Veiled Threat", 0.80),
    (r"\b(burn your house|bomb|swat(ting)?|put a bullet)\b", "Severe Physical / Property Threat", 0.95),
]

HARASSMENT_PATTERNS = [
    (r"\b(kys|kill yourself|die in a fire|go die)\b", "Self-Harm Encouragement / Severe Cyberbullying", 0.95),
    (r"\b(slut|whore|bitch|worthless piece|retard|scumbag)\b", "Abusive Slurs / Targeted Harassment", 0.70),
    (r"\b(leaking your nudes|expose your photos|release your sextape|pay me or i send)\b", "Sextortion / NCII Blackmail Threat", 0.98),
    (r"\b(post your address|dox(x)?(ing)? you|share your phone number)\b", "Doxxing / Privacy Intrusion Threat", 0.90),
]

IMPERSONATION_PATTERNS = [
    (r"\b(i am the real|my official new account|my old account was hacked|follow this account instead)\b", "Account Takeover / Impersonation Signal", 0.75),
    (r"\b(send money to this cashapp|crypto giveaway|send 1 eth to receive 2 eth|dm me for investment)\b", "Financial Impersonation / Scam Hook", 0.85),
    (r"\b(official customer support|support representative|verify your seed phrase)\b", "Support Impersonation Credential Harvest", 0.90),
]

MISINFORMATION_PATTERNS = [
    (r"\b(the government is hiding|secret cure they dont want you to know|miracle medicine cures all)\b", "Health / Pseudoscience Disinformation", 0.75),
    (r"\b(martial law declared|emergency broadcast all banks closing tomorrow|military taking over)\b", "Panic Induction / Fabricated State Emergency", 0.85),
    (r"\b(leaked secret document proves|shocking proof the election was faked)\b", "Manipulated Civic Disinformation", 0.75),
]

def analyze_text_content(text: str, context_type: str = "general") -> Dict[str, Any]:
    """
    Forensic rule-based text analysis identifying threats, harassment, sextortion,
    impersonation, and viral misinformation.
    """
    findings: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    max_risk_score = 0.0

    lower_text = text.lower()

    # 1. Analyze Threats
    for pattern, name, score in THREAT_PATTERNS:
        match = re.search(pattern, lower_text)
        if match:
            findings.append({
                "category": "Threat & Physical Harm",
                "severity": "critical" if score >= 0.9 else "high",
                "score": score,
                "description": f"Detected matching threat pattern: '{match.group(0)}'."
            })
            evidence.append({
                "indicator": name,
                "observed_value": match.group(0),
                "interpretation": "Language indicative of violent harm, intimidation or coercion."
            })
            max_risk_score = max(max_risk_score, score)

    # 2. Analyze Harassment & Sextortion
    for pattern, name, score in HARASSMENT_PATTERNS:
        match = re.search(pattern, lower_text)
        if match:
            severity = "critical" if score >= 0.95 else ("high" if score >= 0.8 else "medium")
            findings.append({
                "category": "Harassment & Extortion",
                "severity": severity,
                "score": score,
                "description": f"Detected abuse/extortion indicator: '{match.group(0)}'."
            })
            evidence.append({
                "indicator": name,
                "observed_value": match.group(0),
                "interpretation": "Violates digital safety standards against harassment, non-consensual disclosure, or blackmail."
            })
            max_risk_score = max(max_risk_score, score)

    # 3. Analyze Impersonation
    for pattern, name, score in IMPERSONATION_PATTERNS:
        match = re.search(pattern, lower_text)
        if match:
            findings.append({
                "category": "Impersonation & Scam",
                "severity": "high" if score >= 0.85 else "medium",
                "score": score,
                "description": f"Detected impersonation indicator: '{match.group(0)}'."
            })
            evidence.append({
                "indicator": name,
                "observed_value": match.group(0),
                "interpretation": "Language pattern mimics social engineering, credential harvesting, or identity fraud."
            })
            max_risk_score = max(max_risk_score, score)

    # 4. Analyze Misinformation
    for pattern, name, score in MISINFORMATION_PATTERNS:
        match = re.search(pattern, lower_text)
        if match:
            findings.append({
                "category": "Misinformation / Deceptive Claim",
                "severity": "medium",
                "score": score,
                "description": f"Detected unverified high-impact claim indicator: '{match.group(0)}'."
            })
            evidence.append({
                "indicator": name,
                "observed_value": match.group(0),
                "interpretation": "Sensationalist assertion without verifiable source citation."
            })
            max_risk_score = max(max_risk_score, score)

    # Determine overall risk category and confidence
    if max_risk_score >= 0.90:
        risk_level = "critical"
        confidence = 0.94
        rec_action = "Initiate immediate incident case, document evidence hash, and prepare formal platform escalation or law enforcement report."
    elif max_risk_score >= 0.70:
        risk_level = "high"
        confidence = 0.88
        rec_action = "Generate targeted platform violation report citing harassment and content safety policies."
    elif max_risk_score >= 0.40:
        risk_level = "medium"
        confidence = 0.78
        rec_action = "Monitor source profile, archive textual evidence, and request community moderation review."
    else:
        risk_level = "low"
        confidence = 0.85
        rec_action = "No immediate policy violations detected. Keep logged for baseline tracking."

    explanation = (
        f"Linguistic forensic evaluation processed {len(text.split())} words. "
        f"Identified {len(findings)} hazard signal(s) with an explainable peak risk factor of {max_risk_score:.2f}."
    )

    return {
        "content_type": "text",
        "risk_level": risk_level,
        "confidence": round(confidence, 2),
        "findings": findings,
        "evidence": evidence,
        "explanation": explanation,
        "limitations": [
            "Lexical matching does not account for deep sarcasm or localized colloquial slang without LLM context.",
            "Confidence score does not constitute legal adjudication."
        ],
        "recommended_action": rec_action,
        "raw_metadata": {
            "char_count": len(text),
            "word_count": len(text.split()),
            "context_type": context_type
        }
    }

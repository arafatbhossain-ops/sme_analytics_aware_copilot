import re
from typing import Dict, List, Tuple
import pandas as pd

# The prototype intentionally errs on the side of caution.  These are not legal
# compliance rules; they are a demonstrable privacy-scan layer for the prototype.
BASE_PII_COLUMN_PATTERNS = [
    r"name", r"email", r"phone", r"mobile", r"address", r"street", r"city",
    r"state", r"zip", r"postal", r"customer_id", r"client_id", r"order_id",
    r"ssn", r"dob", r"date_of_birth", r"credit", r"card", r"ip_address",
]

HIPAA_COLUMN_PATTERNS = [
    r"patient", r"member", r"medical_record", r"mrn", r"health_plan", r"diagnosis",
    r"condition", r"procedure", r"prescription", r"appointment", r"provider",
    r"clinic", r"insurance", r"claim", r"birth", r"admission", r"discharge",
]

GDPR_COLUMN_PATTERNS = [
    r"user", r"data_subject", r"consent", r"location", r"geo", r"ip", r"device",
    r"cookie", r"identifier", r"nationality", r"passport", r"biometric",
]

PCI_COLUMN_PATTERNS = [
    r"card", r"payment", r"cvv", r"cvc", r"expiration", r"expiry", r"pan",
    r"billing", r"bank", r"account_number",
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CC_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")


def _patterns_for_standard(standard: str) -> list[str]:
    standard = (standard or "PII Baseline").lower()
    patterns = list(BASE_PII_COLUMN_PATTERNS)
    if "hipaa" in standard:
        patterns += HIPAA_COLUMN_PATTERNS
    if "gdpr" in standard:
        patterns += GDPR_COLUMN_PATTERNS
    if "pci" in standard:
        patterns += PCI_COLUMN_PATTERNS
    if "strict" in standard or "all" in standard:
        patterns += HIPAA_COLUMN_PATTERNS + GDPR_COLUMN_PATTERNS + PCI_COLUMN_PATTERNS
    # Keep unique order.
    seen = set()
    return [p for p in patterns if not (p in seen or seen.add(p))]


def standard_description(standard: str) -> str:
    if standard == "PII Baseline":
        return "Flags common personally identifiable fields such as names, emails, phone numbers, addresses, customer IDs, and order IDs."
    if standard == "HIPAA-aware":
        return "Adds healthcare-oriented patterns such as patient/member identifiers, claims, provider, diagnosis, appointment, and medical-record-like fields. Prototype only; not legal compliance advice."
    if standard == "GDPR-aware":
        return "Adds broader personal-data patterns such as user identifiers, consent, location, device, cookie, IP, passport, and biometric-like fields. Prototype only; not legal compliance advice."
    if standard == "PCI-aware":
        return "Adds payment-card and billing-oriented patterns such as card, CVV/CVC, expiration, payment, and bank/account fields. Prototype only; not legal compliance advice."
    if standard == "Strict: PII + HIPAA + GDPR + PCI":
        return "Most conservative prototype mode. Combines baseline PII, healthcare, GDPR-style personal data, and payment-card/billing patterns."
    return "Prototype privacy scan mode."


def detect_sensitive_columns(df: pd.DataFrame, standard: str = "PII Baseline", sample_size: int = 50) -> Dict[str, List[str]]:
    """Return columns likely containing sensitive or identifying data.

    The detector combines column-name matching with lightweight sample-value
    checks for emails, phone numbers, SSNs, ZIP/address-like values, and
    card-like strings. This is a prototype demonstration, not a compliance tool.
    """
    patterns = _patterns_for_standard(standard)
    findings: Dict[str, List[str]] = {}
    for col in df.columns:
        reasons: List[str] = []
        lowered = str(col).lower().strip()
        for pat in patterns:
            if re.search(pat, lowered):
                reasons.append(f"column name matched '{pat}' under {standard}")
                break

        sample_values = df[col].dropna().astype(str).head(sample_size).tolist()
        joined = " ".join(sample_values[:sample_size])
        if EMAIL_RE.search(joined):
            reasons.append("sample values look like email addresses")
        if PHONE_RE.search(joined):
            reasons.append("sample values look like phone numbers")
        if SSN_RE.search(joined):
            reasons.append("sample values look like SSNs")
        if CC_RE.search(joined) and any(token in lowered for token in ["card", "payment", "cc", "pan"]):
            reasons.append("sample values may contain payment-card-like numbers")
        if ZIP_RE.search(joined) and any(token in lowered for token in ["zip", "postal", "address"]):
            reasons.append("sample values look like postal/address information")

        try:
            if df[col].nunique(dropna=True) > max(20, len(df) * 0.8) and df[col].dtype == "object":
                if any(token in lowered for token in ["id", "key", "uuid"]):
                    reasons.append("high-cardinality identifier-like field")
        except Exception:
            pass

        if reasons:
            findings[col] = reasons
    return findings


def split_safe_and_sensitive(df: pd.DataFrame, standard: str = "PII Baseline") -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, List[str]]]:
    findings = detect_sensitive_columns(df, standard=standard)
    sensitive_cols = list(findings.keys())
    safe_df = df.drop(columns=sensitive_cols, errors="ignore")
    sensitive_df = df[sensitive_cols].copy() if sensitive_cols else pd.DataFrame(index=df.index)
    return safe_df, sensitive_df, findings

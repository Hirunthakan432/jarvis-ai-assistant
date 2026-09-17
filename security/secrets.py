"""Conservative credential filtering; not a general sensitive-data classifier."""
import re

LABEL = r'(?:password|passwd|passphrase|api[_ -]?key|access[_ -]?token|auth(?:orization)?|secret|private[_ -]?key)'
PATTERNS = [
    re.compile(r'\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}|AIza[A-Za-z0-9_-]{20,})\b'),
    re.compile(r'(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/_.=-]{6,}'),
    re.compile(r'(?i)\b' + LABEL + r'\s*(?:[=:]|\bis\b)\s*[^\n,;]+'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*'),
    re.compile(r'(?i)/(?:confirm|cancel)\s+\S+'),
    re.compile(r'(?i)(["\']token["\']\s*:\s*)["\'][^"\']+["\']'),
    re.compile(r'https?://[^\s/:]+:[^\s/@]+@[^\s]+'),
]


def redact(text):
    for pattern in PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return text


def reject_credentials(key, value):
    if re.search(LABEL, key, re.I) or redact(value) != value:
        raise ValueError('Credentials cannot be saved in assistant memory or learned commands.')


def redact_data(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if re.search(LABEL, str(k), re.I) or k == 'token' else redact_data(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact_data(v) for v in value]
    if isinstance(value, str):
        return redact(value)
    return value

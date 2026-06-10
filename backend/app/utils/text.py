import re
import unicodedata


def clean_user_text(text: str) -> str:
    """Normalize noisy chat text while preserving useful travel words."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(.)\1{3,}", r"\1\1", text)  # euphoric!!!!!! -> euphoric!!
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = normalize_key(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out

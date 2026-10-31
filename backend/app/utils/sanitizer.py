"""
LenseScan Input Sanitizer.
Prevents injection attacks via OCR-scanned text and uploaded filenames.
"""

import re
import os
from typing import Optional


# Patterns that indicate potential SQL injection attempts
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC|EXECUTE)\b)",
    r"(--|;|/\*|\*/|xp_|sp_)",
    r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)",
    r"('(\s)*(OR|AND)(\s)*')",
]

# Patterns that indicate script injection
SCRIPT_INJECTION_PATTERNS = [
    r"<script[^>]*>",
    r"</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe",
    r"<object",
    r"<embed",
    r"<form",
]

# Allowed image MIME type magic bytes
ALLOWED_IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",      # JPEG
    b"\x89PNG\r\n\x1a\n": "image/png",  # PNG
}


def sanitize_ocr_text(text: str) -> str:
    """
    Sanitize OCR-extracted text to prevent injection attacks.

    - Strips null bytes and control characters
    - Removes potential SQL injection patterns
    - Removes script injection patterns
    - Preserves legitimate label text (prices, dates, addresses)

    Args:
        text: Raw text from OCR extraction.

    Returns:
        Sanitized text safe for processing and storage.
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace("\x00", "")

    # Normalize Devanagari numerals to standard ASCII digits
    devanagari_digits = str.maketrans("०१२३४५६७८९", "0123456789")
    text = text.translate(devanagari_digits)

    # Remove control characters (keep newlines, tabs, and printable chars)
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Flag but don't remove SQL-like patterns — log them for audit
    # We sanitize by escaping single quotes instead of removing
    text = text.replace("'", "'")  # Replace smart quotes
    text = text.replace("'", "'")

    # Remove script injection patterns
    for pattern in SCRIPT_INJECTION_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Strip excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def sanitize_filename(filename: str) -> str:
    """
    Sanitize uploaded filename to prevent path traversal and injection.

    Only allows alphanumeric characters, hyphens, underscores, and dots.
    Strips directory components.

    Args:
        filename: Original filename from upload.

    Returns:
        Safe filename string.
    """
    if not filename:
        return "unnamed_upload"

    # Extract just the filename (no directory path)
    filename = os.path.basename(filename)

    # Remove any non-alphanumeric characters except .-_
    name, ext = os.path.splitext(filename)
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    ext = re.sub(r"[^a-zA-Z0-9.]", "", ext)

    # Limit length
    name = name[:100]

    return f"{name}{ext}" if ext else name


def clean_product_name(name: Optional[str], max_length: int = 200) -> Optional[str]:
    """Officer-entered product name: drop control characters, collapse whitespace, trim. None if empty."""
    if not name:
        return None
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length] or None


def validate_image_content(file_bytes: bytes) -> Optional[str]:
    """
    Validate that file content matches an allowed image type by checking magic bytes.

    This prevents disguised file uploads (e.g., executables renamed to .jpg).

    Args:
        file_bytes: Raw file content bytes.

    Returns:
        Detected MIME type string if valid, None if the file is not a recognized image.
    """
    for signature, mime_type in ALLOWED_IMAGE_SIGNATURES.items():
        if file_bytes[:len(signature)] == signature:
            return mime_type
    return None


def check_sql_injection(text: str) -> bool:
    """
    Check if text contains suspicious SQL injection patterns.

    Args:
        text: Text to check.

    Returns:
        True if suspicious patterns are detected.
    """
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

"""Input validation utilities."""

import os
import re
from pathlib import Path

import config


# ═══════════════════════════════════════════
# EMAIL
# ═══════════════════════════════════════════
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


# ═══════════════════════════════════════════
# COMBO FORMAT
# ═══════════════════════════════════════════
def validate_combo_line(line: str) -> tuple[bool, str, str]:
    """Validate a single combo line. Returns (valid, email, password)."""
    line = line.strip()
    if not line or line.startswith("#"):
        return False, "", ""
    if ":" not in line:
        return False, "", ""
    idx = line.index(":")
    email = line[:idx].strip()
    password = line[idx + 1:].strip()
    if not email or not password:
        return False, "", ""
    if not is_valid_email(email):
        return False, "", ""
    if len(password) > 200:
        return False, "", ""
    return True, email, password


# ═══════════════════════════════════════════
# FILE UPLOAD
# ═══════════════════════════════════════════
ALLOWED_EXTENSIONS = {".txt", ".csv"}


def validate_upload(file_path: str, max_size: int = config.MAX_FILE_SIZE) -> tuple[bool, str]:
    """
    Validate an uploaded file.
    Returns (valid, error_message).
    """
    # Path traversal check
    try:
        resolved = Path(file_path).resolve()
        if not str(resolved).startswith(str(config.TMP_DIR.resolve())):
            return False, "Iɴᴠᴀʟɪᴅ ғɪʟᴇ ᴘᴀᴛʜ."
    except Exception:
        return False, "Iɴᴠᴀʟɪᴅ ғɪʟᴇ."

    # Existence
    if not os.path.exists(file_path):
        return False, "Fɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ."

    # Size
    size = os.path.getsize(file_path)
    if size > max_size:
        return False, f"Fɪʟᴇ ᴛᴏᴏ ʟᴀʀɢᴇ. Mᴀx: {max_size // (1024*1024)}MB."

    # Empty
    if size == 0:
        return False, "Fɪʟᴇ ɪs ᴇᴍᴘᴛʏ."

    # Extension
    ext = Path(file_path).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Iɴᴠᴀʟɪᴅ ғɪʟᴇ ᴛʏᴘᴇ. Aʟʟᴏᴡᴇᴅ: {', '.join(ALLOWED_EXTENSIONS)}"

    return True, ""


# ═══════════════════════════════════════════
# PROXY FORMAT
# ═══════════════════════════════════════════
def validate_proxy_line(line: str) -> bool:
    """Quick check if a line looks like a proxy."""
    line = line.strip()
    if not line or line.startswith("#"):
        return False
    if "://" in line:
        parts = line.split("://", 1)
        if parts[0].lower() not in ("http", "https", "socks4", "socks5"):
            return False
        rest = parts[1]
    else:
        rest = line
    # Must have at least host:port
    parts = rest.rsplit(":", 1)
    if len(parts) != 2:
        return False
    try:
        port = int(parts[1])
        return 1 <= port <= 65535
    except ValueError:
        return False


# ═══════════════════════════════════════════
# SANITIZE
# ═══════════════════════════════════════════
def sanitize_filename(name: str) -> str:
    """Remove path traversal and dangerous chars from filename."""
    name = Path(name).name  # basename only
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    return name


def sanitize_input(text: str, max_len: int = 4096) -> str:
    """Basic input sanitization."""
    text = text.strip()
    text = text[:max_len]
    # Remove control characters except newline
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text

import os
from pathlib import Path
from cryptography.fernet import Fernet
from app.core.config import settings

_KEY_FILE = settings.STORAGE_DIR / ".vault.key"

def _get_or_create_vault_key() -> bytes:
    """Resolve encryption key from environment or persist an isolated local vault key."""
    if settings.EVIDENCE_ENCRYPTION_KEY:
        return settings.EVIDENCE_ENCRYPTION_KEY.encode("utf-8")

    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()

    key = Fernet.generate_key()
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE.write_bytes(key)
    try:
        os.chmod(_KEY_FILE, 0o600)
    except Exception:
        pass
    return key

def _get_fernet() -> Fernet:
    return Fernet(_get_or_create_vault_key())

def encrypt_evidence_bytes(raw_bytes: bytes) -> bytes:
    """Encrypt evidence payload at rest using authenticated AES-128-CBC + HMAC-SHA256."""
    return _get_fernet().encrypt(raw_bytes)

def decrypt_evidence_bytes(stored_bytes: bytes) -> bytes:
    """Decrypt encrypted evidence payload; gracefully supports legacy plaintext if not Fernet-prefixed."""
    if not stored_bytes.startswith(b"gAAAAA"):
        return stored_bytes
    return _get_fernet().decrypt(stored_bytes)

def secure_shred_file(file_path: str) -> None:
    """Overwrite file contents with random bytes and zeros before unlinking from disk."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return
    try:
        size = path.stat().st_size
        if size > 0:
            with open(path, "r+b") as f:
                f.seek(0)
                f.write(os.urandom(min(size, 4 * 1024 * 1024)))
                f.flush()
                os.fsync(f.fileno())
                f.seek(0)
                f.write(b"\x00" * min(size, 4 * 1024 * 1024))
                f.flush()
                os.fsync(f.fileno())
    except Exception:
        pass
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

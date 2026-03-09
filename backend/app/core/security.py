import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

# ── Hashing de contraseñas ─────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT ────────────────────────────────────────────────────────────
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise ValueError(f"Token inválido: {e}")


# ── SHA-256 para consentimientos ───────────────────────────────────
def hash_consent_document(phone: str, timestamp: str, consent_text: str) -> str:
    """
    Genera hash SHA-256 del documento de consentimiento.
    Inmutable y verificable en cualquier momento.
    """
    raw = f"{phone}|{timestamp}|{consent_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_consent_hash(phone: str, timestamp: str, consent_text: str, stored_hash: str) -> bool:
    computed = hash_consent_document(phone, timestamp, consent_text)
    return hmac.compare_digest(computed, stored_hash)


# ── HMAC para webhook de WhatsApp ──────────────────────────────────
def verify_whatsapp_signature(payload: bytes, signature_header: str) -> bool:
    """
    Valida la firma HMAC-SHA256 del webhook de Meta.
    signature_header tiene formato 'sha256=<hex>'
    """
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header[7:]
    computed = hmac.new(
        settings.meta_app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, expected)


# ── Cifrado AES-256 (Fernet) para campos PHI ───────────────────────
def _get_fernet() -> Fernet:
    key = settings.encryption_key
    # Fernet requiere una clave de 32 bytes en base64url
    if len(key) < 32:
        key = key.ljust(32, "0")
    key_bytes = key[:32].encode("utf-8")
    import base64
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_field(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_field(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")

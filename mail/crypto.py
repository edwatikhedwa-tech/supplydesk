from __future__ import annotations

import base64
import binascii
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionConfigError(ValueError):
    pass


def load_key(value: str | None) -> bytes:
    if not value:
        raise EncryptionConfigError(
            "MAIL_TOKEN_ENCRYPTION_KEY не задан. Сгенерируйте 32-байтный ключ и добавьте его в .env."
        )
    raw = value.strip().encode("ascii", "strict")
    try:
        key = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except (ValueError, binascii.Error) as exc:
        raise EncryptionConfigError(
            "MAIL_TOKEN_ENCRYPTION_KEY должен быть URL-safe base64 ключом."
        ) from exc
    if len(key) != 32:
        raise EncryptionConfigError("MAIL_TOKEN_ENCRYPTION_KEY должен декодироваться ровно в 32 байта.")
    return key


def generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def encrypt(value: str, key: bytes, *, associated_data: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, value.encode("utf-8"), associated_data.encode("utf-8"))
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt(value: str, key: bytes, *, associated_data: str) -> str:
    try:
        packed = base64.urlsafe_b64decode(value.encode("ascii"))
        plaintext = AESGCM(key).decrypt(
            packed[:12], packed[12:], associated_data.encode("utf-8")
        )
    except (ValueError, binascii.Error) as exc:
        raise EncryptionConfigError("Не удалось расшифровать сохранённый токен.") from exc
    return plaintext.decode("utf-8")

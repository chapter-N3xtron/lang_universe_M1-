"""Ed25519 receipt signing with no secret serialization in receipts."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .models import Receipt, SignedReceipt, canonical_json_bytes


class ReceiptSigner:
    def __init__(self, private_key: Ed25519PrivateKey):
        self._private_key = private_key
        self._public_key = private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.key_id = hashlib.sha256(self._public_key).hexdigest()[:16]

    @classmethod
    def load_or_create(cls, path: Path) -> ReceiptSigner:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.exists():
            if path.stat().st_mode & 0o077:
                raise PermissionError("signing key permissions must be 0600")
            key = Ed25519PrivateKey.from_private_bytes(path.read_bytes())
        else:
            key = Ed25519PrivateKey.generate()
            raw = key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        return cls(key)

    def public_key_bytes(self) -> bytes:
        """Return a copy of the non-secret raw Ed25519 verification key."""
        return bytes(self._public_key)

    def export_public_key(self, path: Path) -> Path:
        """Safely publish only the raw verification key to a host-selected path."""
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(self._public_key)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            path.chmod(0o644)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def sign(self, receipt: Receipt) -> SignedReceipt:
        payload = canonical_json_bytes(receipt.model_dump(mode="json"))
        signature = base64.b64encode(self._private_key.sign(payload)).decode("ascii")
        return SignedReceipt(receipt=receipt, key_id=self.key_id, signature=signature)


def verify_signed_receipt(signed: SignedReceipt, public_key: bytes) -> None:
    payload = canonical_json_bytes(signed.receipt.model_dump(mode="json"))
    Ed25519PublicKey.from_public_bytes(public_key).verify(
        base64.b64decode(signed.signature, validate=True), payload
    )

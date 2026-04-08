import requests
from django.conf import settings

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from nacl.bindings import (
    crypto_aead_xchacha20poly1305_ietf_encrypt,
    crypto_aead_xchacha20poly1305_ietf_decrypt,
)
import nacl.utils
import base64
import os

from encrypt.cipherpol import CipherPol, CipherPolAgent
   
class DekHandler:

    def encrypt_dek(dek: str) -> str:
        res = requests.post(settings.ENCRYPT_SERVICE_URL, json={"dek": dek})
        res.raise_for_status()
        return res.json()["encrypted_dek"]

    def decrypt_dek(encrypted_dek: str) -> str:
        res = requests.post(settings.DECRYPT_SERVICE_URL, json={"encrypted_dek": encrypted_dek})
        res.raise_for_status()
        return res.json()["dek"]

    def rotate_deks(batch):
        res = requests.post(settings.ROTATE_SERVICE_URL, json={"encrypted_deks": batch})
        res.raise_for_status()
        return res.json()["rotated_deks"]
    
@CipherPol.register("AES256_GCM")
class AES256GCM(CipherPolAgent):

    @staticmethod
    def encrypt(plaintext: str, dek: str) -> str:
        key = base64.b64decode(dek)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()

    @staticmethod
    def decrypt(ciphertext: str, dek: str) -> str:
        raw = base64.b64decode(ciphertext)
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(base64.b64decode(dek))
        return aesgcm.decrypt(nonce, ct, None).decode()
    


@CipherRegistry.register("XCHACHA20_POLY1305")
class XChaCha20Poly1305(CipherPolAgent):

    NONCE_SIZE = 24  # XChaCha uses 24-byte nonce

    @staticmethod
    def encrypt(plaintext: str, dek: str) -> str:
        key = base64.b64decode(dek)

        if len(key) != 32:
            raise ValueError("DEK must be 32 bytes (base64-encoded)")

        nonce = nacl.utils.random(XChaCha20Poly1305.NONCE_SIZE)

        ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(
            plaintext.encode(),
            aad=None,
            nonce=nonce,
            key=key,
        )

        return base64.b64encode(nonce + ciphertext).decode()

    @staticmethod
    def decrypt(ciphertext: str, dek: str) -> str:
        key = base64.b64decode(dek)

        raw = base64.b64decode(ciphertext)
        nonce = raw[:XChaCha20Poly1305.NONCE_SIZE]
        ct = raw[XChaCha20Poly1305.NONCE_SIZE:]

        plaintext = crypto_aead_xchacha20poly1305_ietf_decrypt(
            ct,
            aad=None,
            nonce=nonce,
            key=key,
        )

        return plaintext.decode()
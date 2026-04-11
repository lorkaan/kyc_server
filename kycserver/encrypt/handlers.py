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
        res = requests.post(settings.ENCRYPT_SERVICE_URL, 
                json={"dek": dek}, 
                verify="/certs/ca.crt",
                cert=(
                    "/certs/server.crt",   # Django's cert
                    "/certs/server.key"
                )
            )
        res.raise_for_status()
        return res.json()["encrypted_dek"], res.json()["key_id"]

    def decrypt_dek(encrypted_dek: str) -> str:
        res = requests.post(settings.DECRYPT_SERVICE_URL, 
                json={"encrypted_dek": encrypted_dek},
                verify="/certs/ca.crt",
                cert=(
                    "/certs/server.crt",   # Django's cert
                    "/certs/server.key"
                )
            )
        res.raise_for_status()
        return res.json()["dek"]

    def rotate_deks(batch):
        res = requests.post(settings.ROTATE_SERVICE_URL,
                json={"encrypted_deks": batch},
                verify="/certs/ca.crt",
                cert=(
                    "/certs/server.crt",   # Django's cert
                    "/certs/server.key"
                )
            )
        res.raise_for_status()
        return res.json()["rotated_deks"]
    
@CipherPol.register("AES256_GCM")
class AES256GCM(CipherPolAgent):

    KEY_LENGTH = 32

    @classmethod
    def encrypt(cls, plain_text: str, key: str, **kwargs) -> str:
        key = base64.b64decode(key)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plain_text.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()

    @classmethod
    def decrypt(cls, cipher_text: str, key: str, **kwargs) -> str:
        raw = base64.b64decode(cipher_text)
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(base64.b64decode(key))
        return aesgcm.decrypt(nonce, ct, None).decode()
    
    @classmethod
    def generate_key(cls, **kwargs):
        raw = os.urandom(cls.KEY_LENGTH)
        return base64.b64encode(raw).decode()


@CipherPol.register("XCHACHA20_POLY1305")
class XChaCha20Poly1305(CipherPolAgent):

    KEY_LENGTH = 32
    NONCE_SIZE = 24  # XChaCha uses 24-byte nonce

    @staticmethod
    def encrypt(plain_text: str, key: str, **kwargs) -> str:
        key = base64.b64decode(key)

        if len(key) != 32:
            raise ValueError("DEK must be 32 bytes (base64-encoded)")

        nonce = nacl.utils.random(XChaCha20Poly1305.NONCE_SIZE)

        ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(
            plain_text.encode(),
            aad=None,
            nonce=nonce,
            key=key,
        )

        return base64.b64encode(nonce + ciphertext).decode()

    @staticmethod
    def decrypt(cipher_text: str, key: str, **kwargs) -> str:
        key = base64.b64decode(key)

        raw = base64.b64decode(cipher_text)
        nonce = raw[:XChaCha20Poly1305.NONCE_SIZE]
        ct = raw[XChaCha20Poly1305.NONCE_SIZE:]

        plaintext = crypto_aead_xchacha20poly1305_ietf_decrypt(
            ct,
            aad=None,
            nonce=nonce,
            key=key,
        )

        return plaintext.decode()
    
    @classmethod
    def generate_key(cls, **kwargs):
        raw = os.urandom(cls.KEY_LENGTH)
        return base64.b64encode(raw).decode()
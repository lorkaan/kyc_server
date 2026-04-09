from kyc.models import KycQuestion

from .cipherpol import CipherPol, CipherPolAgent
from .handlers import DekHandler
from rest_framework import serializers
from .models import EncryptionValue



class EncryptionValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = EncryptionValue
        fields = ["ciphertext", "encrypted_dek", "algorithm", "data_type"]

    def to_representation(self, instance):
        """Decrypt the ciphertext using the DEK."""
        ret = super().to_representation(instance)

        if instance.encrypted_dek:
            dek = DekHandler.decrypt_dek(instance.encrypted_dek)
            algo_class = CipherPol.get(instance.algorithm)
            if issubclass(algo_class, CipherPolAgent):
                ret["plaintext"] = algo_class.decrypt(instance.ciphertext, dek)
            else:
                raise TypeError(f"Expected a CipherPolAgent, but instead got: {algo_class}")

        return ret
from kyc.models import KycQuestion

from .cipherpol import CipherPol, CipherPolAgent
from .handlers import DekHandler
from rest_framework import serializers
from .models import EncryptionType, EncryptionValue, get_allowed_data_type_choices

class EncryptionTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = EncryptionType
        fields = "__all__"

    def validate_algorithm(self, value):
        if value not in CipherPol.REGISTRY:
            raise serializers.ValidationError(
                "Invalid encryption algorithm"
            )
        return value

class EncryptionValueSerializer(serializers.ModelSerializer):

    encrypt_type = serializers.CharField(
        source="encrypt_type.algorithm",
        read_only=True
    )

    class Meta:
        model = EncryptionValue
        fields = "__all__"

    def validate_data_type(self, value):
        allowed_types = {
            key for key, _ in get_allowed_data_type_choices()
        }

        if value not in allowed_types:
            raise serializers.ValidationError(
                f"Data type '{value}' is not allowed for encryption."
            )

        return value

    def to_representation(self, instance):
        """Decrypt the ciphertext using the DEK."""
        ret = super().to_representation(instance)

        if instance.dek:
            dek = DekHandler.decrypt_dek(instance.dek)
            algo_class = CipherPol.get(instance.encrypt_type)   # encrypt_type evaluates to the algorithm type
            if issubclass(algo_class, CipherPolAgent):
                ret["plaintext"] = algo_class.decrypt(instance.ciphertext, dek)
            else:
                raise TypeError(f"Expected a CipherPolAgent, but instead got: {algo_class}")

        return ret

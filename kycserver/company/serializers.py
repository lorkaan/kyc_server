from kyc.models import ReferenceValue
from kyc.serializers import ReferenceValueSerializer
from rest_framework import serializers
from .models import Company


class CompanySerializer(serializers.ModelSerializer):
    country = ReferenceValueSerializer(read_only=True)

    country_id = serializers.PrimaryKeyRelatedField(
        source="country",
        queryset=ReferenceValue.objects.filter(
            reference_set__key="countries",
            is_active=True
        ),
        write_only=True
    )

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "registration_number",
            "country",     # 👈 read (full object)
            "country_id",  # 👈 write (pk only)
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]
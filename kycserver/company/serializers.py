from rest_framework import serializers
from .models import Company


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "registration_number",
            "country",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_country(self, value):
        if len(value) != 2:
            raise serializers.ValidationError(
                "Country must be a 2-letter ISO code."
            )
        return value.upper()
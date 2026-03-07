from rest_framework import serializers
from django.db import transaction
from .models import (
    KYCRecord,
    KycAnswer,
    KycAnswerOption,
    PersonCompanyRelationship,
    ReferenceValue,
    RelationshipRole,
    KYCStatus,
    KycQuestion,
)

class RelationshipRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelationshipRole
        fields = "__all__"

class KYCStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCStatus
        fields = "__all__"

class PersonCompanyRelationshipSerializer(serializers.ModelSerializer):
    role = RelationshipRoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=RelationshipRole.objects.all(),
        source="role",
        write_only=True
    )

    class Meta:
        model = PersonCompanyRelationship
        fields = [
            "id",
            "person",
            "company",
            "role",
            "role_id",
            "ownership_percentage",
            "start_date",
            "end_date",
        ]


class KycAnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = KycAnswerOption
        fields = ["id", "option"]

class KycAnswerSerializer(serializers.ModelSerializer):
    selected_options = serializers.PrimaryKeyRelatedField(
        queryset=ReferenceValue.objects.all(),
        many=True,
        required=False
    )

    class Meta:
        model = KycAnswer
        fields = [
            "id",
            "kyc_record",
            "question",
            "repeat_index",
            # scalar values
            "value_number",
            "value_text",
            "value_bool",
            "value_reference",
            "value_date",
            "value_date_from",
            "value_date_to",
            "value_email",
            "value_phone",
            # multi-select
            "selected_options",
        ]

    # -------------------------------------------------
    # VALIDATION
    # -------------------------------------------------

    def validate(self, attrs):
        """
        Let the model handle validation logic via clean().
        We construct an instance and call full_clean().
        """
        instance = self.instance or KycAnswer(**attrs)

        # If updating, merge existing values
        if self.instance:
            for attr, value in attrs.items():
                setattr(instance, attr, value)

        try:
            instance.full_clean()
        except Exception as e:
            raise serializers.ValidationError(e.message_dict if hasattr(e, "message_dict") else str(e))

        return attrs

    # -------------------------------------------------
    # CREATE
    # -------------------------------------------------

    @transaction.atomic
    def create(self, validated_data):
        selected_options = validated_data.pop("selected_options", [])
        answer = KycAnswer.objects.create(**validated_data)

        if selected_options:
            answer.selected_options.set(selected_options)

        return answer

    # -------------------------------------------------
    # UPDATE
    # -------------------------------------------------

    @transaction.atomic
    def update(self, instance, validated_data):
        selected_options = validated_data.pop("selected_options", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.full_clean()
        instance.save()

        if selected_options is not None:
            instance.selected_options.set(selected_options)

        return instance

class KYCRecordSerializer(serializers.ModelSerializer):
    status = KYCStatusSerializer(read_only=True)
    status_id = serializers.PrimaryKeyRelatedField(
        queryset=KYCStatus.objects.all(),
        source="status",
        write_only=True
    )

    answers = KycAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = KYCRecord
        fields = [
            "id",
            "party",
            "status",
            "status_id",
            "risk_score",
            "notes",
            "verified_at",
            "answers",
            "created_at",
            "updated_at",
        ]

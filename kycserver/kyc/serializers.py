from rest_framework import serializers
from .models import (
    KYCRecord,
    KycAnswer,
    KycAnswerOption,
    PersonCompanyRelationship,
    RelationshipRole,
    KYCStatus,
    KycQuestion,
    KycQuestionOption,
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

class KycQuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = KycQuestionOption
        fields = ["id", "value", "label", "order"]

class KycQuestionSerializer(serializers.ModelSerializer):
    options = KycQuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = KycQuestion
        fields = [
            "id",
            "key",
            "label",
            "answer_type",
            "required",
            "order",
            "options",
        ]

class KycAnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = KycAnswerOption
        fields = ["id", "option"]

class KycAnswerSerializer(serializers.ModelSerializer):
    selected_options = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=KycQuestionOption.objects.all(),
        required=False
    )

    class Meta:
        model = KycAnswer
        fields = [
            "id",
            "question",
            "value_number",
            "value_text",
            "value_bool",
            "value_option",
            "selected_options",
        ]

    def create(self, validated_data):
        selected = validated_data.pop("selected_options", [])
        answer = KycAnswer(**validated_data)
        answer.full_clean()
        answer.save()

        for option in selected:
            KycAnswerOption.objects.create(answer=answer, option=option)

        return answer

    def update(self, instance, validated_data):
        selected = validated_data.pop("selected_options", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.full_clean()
        instance.save()

        if selected is not None:
            instance.selected_options.all().delete()
            for option in selected:
                KycAnswerOption.objects.create(answer=instance, option=option)

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
            "person",
            "status",
            "status_id",
            "risk_score",
            "notes",
            "verified_at",
            "answers",
            "created_at",
            "updated_at",
        ]

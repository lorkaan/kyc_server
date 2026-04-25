from encrypt.cipherpol import CipherPol
from encrypt.handlers import DekHandler
from kyc.data_types import AnswerTypeEnum
from encrypt.models import REPRESENTATION_HANDLERS
from encrypt.serializers import EncryptionValueSerializer
from party.serializers import PartySerializer
from rest_framework import serializers
from django.db import transaction
from .models import (
    KYCRecord,
    KycAnswer,
    KycAnswerOption,
    KycCondition,
    KycConditionDependency,
    ReferenceValue,
    RelationshipRole,
    KYCStatus,
    KycQuestion,
    RiskScore,
)

class ReferenceValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferenceValue
        fields = ["id", "code", "label"]

class RelationshipRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelationshipRole
        fields = "__all__"

class KYCStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCStatus
        fields = "__all__"

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

    value_encrypt = EncryptionValueSerializer(read_only=True)

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
            "value_encrypt"
        ]


    # -------------------------------------------------
    # Override read representation
    # -------------------------------------------------
    def to_representation(self, instance):
        """Populate value_* fields from decrypted value_encrypt."""
        ret = super().to_representation(instance)

        enc_value = instance.value_encrypt
        if enc_value:
            # Use the EncryptionValueSerializer to get plaintext
            plaintext = EncryptionValueSerializer(enc_value).data.get("plaintext")
            
            # Map to the correct value_* field based on data_type
            field_name = REPRESENTATION_HANDLERS.get(enc_value.data_type)
            if field_name:
                ret[field_name] = plaintext

        return ret

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
    
class RiskScoreSerializer(serializers.ModelSerializer):

    label_choices = serializers.SerializerMethodField()

    class Meta:
        model = RiskScore
        fields = ["id", "score", "label", "label_choices"]

    def get_label_choices(self, obj):
        return [
            {"value": value, "label": label}
            for value, label in RiskScore.RiskCategory.choices
        ]

class RiskScoreWriteSerializer(serializers.Serializer):
    score = serializers.IntegerField(required=False)
    label = serializers.ChoiceField(
        choices=RiskScore.RiskCategory.choices,
        required=False
    )

    def validate(self, attrs):
        score = attrs.get("score", None)
        label = attrs.get("label", None)

        # ❗ reject empty input
        if score is None and label is None:
            raise serializers.ValidationError(
                "Either 'score' or 'label' must be provided."
            )

        # optional: normalize empty dict cases explicitly
        if score is not None and score < 0:
            raise serializers.ValidationError({
                "score": "Must be >= 0"
            })

        return attrs

class KYCRecordSerializer(serializers.ModelSerializer):
    status = KYCStatusSerializer(read_only=True)
    status_id = serializers.PrimaryKeyRelatedField(
        queryset=KYCStatus.objects.all(),
        source="status",
        write_only=True
    )

    party = PartySerializer(read_only=True)  # 👈 THIS is the key

    answers = KycAnswerSerializer(many=True, read_only=True)

    risk_score = RiskScoreSerializer(read_only=True)

    risk_score_input = RiskScoreWriteSerializer(write_only=True, required=False)

    class Meta:
        model = KYCRecord
        fields = [
            "id",
            "party",
            "status",
            "status_id",
            "risk_score",
            "risk_score_input",
            "notes",
            "verified_at",
            "answers",
            "created_at",
            "updated_at",
        ]

    # -------------------------
    # CREATE
    # -------------------------
    def create(self, validated_data):
        risk_data = validated_data.pop("risk_score_input", None)

        kyc = KYCRecord.objects.create(**validated_data)

        if risk_data:
            RiskScore.objects.create(
                kyc_record=kyc,
                score=risk_data["score"],
                label=risk_data.get("label")
            )

        return kyc

    # -------------------------
    # UPDATE
    # -------------------------
    def update(self, instance, validated_data):
        risk_data = validated_data.pop("risk_score_input", None)

        instance = super().update(instance, validated_data)

        if risk_data:
            RiskScore.objects.create(
                kyc_record=instance,
                score=risk_data["score"],
                label=risk_data.get("label")
            )

        return instance

class KYCRecordPartySerializer(serializers.ModelSerializer):
    status = KYCStatusSerializer(read_only=True)
    status_id = serializers.PrimaryKeyRelatedField(
        queryset=KYCStatus.objects.all(),
        source="status",
        write_only=True
    )

    party = PartySerializer(read_only=True)  # 👈 THIS is the key

    answers = KycAnswerSerializer(many=True, read_only=True)

    risk_score = RiskScoreSerializer()

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

class KycBulkAnswerSerializer(serializers.Serializer):
    """
    Serializer representing a single KYC answer inside
    the bulk submission payload.
    """

    question = serializers.IntegerField()
    repeat_index = serializers.IntegerField(required=False, default=0)

    # Scalar values
    value_number = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
        allow_null=True
    )

    value_text = serializers.CharField(required=False, allow_null=True)

    value_bool = serializers.BooleanField(required=False, allow_null=True)

    value_reference = serializers.PrimaryKeyRelatedField(
        queryset=ReferenceValue.objects.all(),
        required=False,
        allow_null=True
    )

    value_date = serializers.DateField(required=False, allow_null=True)

    value_date_from = serializers.DateField(required=False, allow_null=True)
    value_date_to = serializers.DateField(required=False, allow_null=True)

    value_email = serializers.EmailField(required=False, allow_null=True)

    value_phone = serializers.CharField(required=False, allow_null=True)

    # Multi-select options
    selected_options = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )

    # -------------------------------------------------
    # VALIDATION
    # -------------------------------------------------

    def validate(self, attrs):

        question_id = attrs["question"]

        try:
            question = KycQuestion.objects.select_related(
                "reference_set"
            ).get(pk=question_id)
        except KycQuestion.DoesNotExist:
            raise serializers.ValidationError(
                f"Question {question_id} does not exist"
            )

        attrs["question_obj"] = question

        answer_type = question.answer_type

        # -------------------------------------------------
        # TYPE CHECKING
        # -------------------------------------------------

        if answer_type == AnswerTypeEnum.NUMBER:
            if attrs.get("value_number") is None:
                raise serializers.ValidationError(
                    "value_number required for NUMBER question"
                )

        elif answer_type == AnswerTypeEnum.TEXT or answer_type == AnswerTypeEnum.TEXT_AREA:
            if not attrs.get("value_text"):
                raise serializers.ValidationError(
                    "value_text required for TEXT question"
                )

        elif answer_type == AnswerTypeEnum.BOOL:
            if attrs.get("value_bool") is None:
                raise serializers.ValidationError(
                    "value_bool required for BOOL question"
                )

        elif answer_type == AnswerTypeEnum.SINGLE:

            if attrs.get("value_reference") is None:
                raise serializers.ValidationError(
                    "value_reference required for SINGLE question"
                )

        elif answer_type == AnswerTypeEnum.MULTI:

            options = attrs.get("selected_options", [])

            if not options and question.required:
                raise serializers.ValidationError(
                    "At least one selected_option required"
                )

        elif answer_type == AnswerTypeEnum.DATE:

            if attrs.get("value_date") is None:
                raise serializers.ValidationError(
                    "value_date required"
                )

        elif answer_type == AnswerTypeEnum.RANGE:

            start = attrs.get("value_date_from")
            end = attrs.get("value_date_to")

            if not start or not end:
                raise serializers.ValidationError(
                    "value_date_from and value_date_to required"
                )

            if start > end:
                raise serializers.ValidationError(
                    "Start date must be before end date"
                )

        elif answer_type == AnswerTypeEnum.EMAIL:

            if not attrs.get("value_email"):
                raise serializers.ValidationError(
                    "value_email required"
                )

        elif answer_type == AnswerTypeEnum.PHONE:

            if not attrs.get("value_phone"):
                raise serializers.ValidationError(
                    "value_phone required"
                )

        # -------------------------------------------------
        # REFERENCE SET VALIDATION
        # -------------------------------------------------

        if "selected_options" in attrs and question.reference_set:

            valid_ids = set(
                ReferenceValue.objects.filter(
                    reference_set=question.reference_set
                ).values_list("id", flat=True)
            )

            for opt in attrs["selected_options"]:
                if opt not in valid_ids:
                    raise serializers.ValidationError(
                        f"Invalid reference option {opt}"
                    )

        return attrs


class KycBulkSubmitSerializer(serializers.Serializer):
    """
    Root serializer for bulk KYC submission
    """

    answers = KycBulkAnswerSerializer(many=True)

    def validate_answers(self, answers):

        seen = set()

        for ans in answers:

            key = (
                ans["question"],
                ans.get("repeat_index", 0)
            )

            if key in seen:
                raise serializers.ValidationError(
                    f"Duplicate answer for question {key[0]} "
                    f"repeat {key[1]}"
                )

            seen.add(key)

        return answers
    
class KycConditionDependencySerializer(serializers.ModelSerializer):
    question_key = serializers.CharField(source="source_question.key")
    group_key = serializers.CharField(source="group.key", allow_null=True)

    class Meta:
        model = KycConditionDependency
        fields = ["question_key", "group_key", "is_required"]

class KycConditionSerializer(serializers.ModelSerializer):
    dependencies = KycConditionDependencySerializer(many=True)

    class Meta:
        model = KycCondition
        fields = [
            "id",
            "condition_type",
            "rule",
            "priority",
            "dependencies",
        ]

class KycQuestionSerializer(serializers.ModelSerializer):
    conditions = serializers.SerializerMethodField()

    class Meta:
        model = KycQuestion
        fields = [
            "id",
            "key",
            "label",
            "answer_type",
            "required",
            "order",
            "is_repeatable",
            "conditions",  # 👈 added here
        ]

    def get_conditions(self, obj):
        conditions = obj.conditions.filter(is_active=True).order_by("priority")

        if not conditions.exists():
            return []

        return KycConditionSerializer(conditions, many=True).data
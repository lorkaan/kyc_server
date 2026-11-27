
from kycserver.agenda import serializers
from kycserver.kyc.models import KYCRecord
from kycserver.kyc.serializers import KYCStatusSerializer, KycAnswerSerializer, RiskScoreSerializer


class KYCRecordQuerySerializer(serializers.ModelSerializer):
    status = KYCStatusSerializer(read_only=True)

    answers = KycAnswerSerializer(many=True, read_only=True)

    risk_score = RiskScoreSerializer(read_only=True)

    verified_by = serializers.SerializerMethodField()
    submitted_by = serializers.SerializerMethodField()

    def get_verified_by(self, obj):
        return self.get_user_display_name(obj.verified_by)

    def get_submitted_by(self, obj):
        return self.get_user_display_name(obj.submitted_by)

    @staticmethod
    def get_user_display_name(user):
        if not user:
            return None

        full_name = f'{user.full_name or ""}'.strip()

        return full_name or user.username

    class Meta:
        model = KYCRecord
        fields = [
            "id",
            "party",
            "status",
            "risk_score",
            "notes",
            "verified_at",
            "answers",
            "created_at",
            "updated_at",
            "expiry_date",
            "is_current",
            "verified_by",
            "submitted_by"
        ]
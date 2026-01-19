from rest_framework import serializers
from .models import (
    AlertStatus,
    AlertSeverity,
    AlertReason,
    Alert,
    SignalSeverity,
    SignalType,
    Signal,
)

class AlertStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertStatus
        fields = "__all__"

class AlertSeveritySerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertSeverity
        fields = "__all__"

class AlertReasonSerializer(serializers.ModelSerializer):
    default_severity = AlertSeveritySerializer(read_only=True)
    default_severity_id = serializers.PrimaryKeyRelatedField(
        queryset=AlertSeverity.objects.all(),
        source="default_severity",
        write_only=True
    )

    class Meta:
        model = AlertReason
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_active",
            "default_severity",
            "default_severity_id",
        ]

class AlertSerializer(serializers.ModelSerializer):
    reason = AlertReasonSerializer(read_only=True)
    reason_id = serializers.PrimaryKeyRelatedField(
        queryset=AlertReason.objects.all(),
        source="reason",
        write_only=True
    )

    severity = AlertSeveritySerializer(read_only=True)
    severity_id = serializers.PrimaryKeyRelatedField(
        queryset=AlertSeverity.objects.all(),
        source="severity",
        write_only=True
    )

    status = AlertStatusSerializer(read_only=True)
    status_id = serializers.PrimaryKeyRelatedField(
        queryset=AlertStatus.objects.all(),
        source="status",
        write_only=True
    )

    target = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "id",
            "reason",
            "reason_id",
            "severity",
            "severity_id",
            "status",
            "status_id",
            "message",
            "target",
            "triggered_at",
            "created_at",
            "updated_at",
        ]

    def get_target(self, obj):
        """
        Expose GenericTargetMixin safely
        """
        return {
            "type": obj.target_type,
            "id": obj.target_id,
        }

class SignalSeveritySerializer(serializers.ModelSerializer):
    class Meta:
        model = SignalSeverity
        fields = "__all__"


class SignalTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignalType
        fields = "__all__"


class SignalSerializer(serializers.ModelSerializer):
    signal_type = SignalTypeSerializer(read_only=True)
    signal_type_id = serializers.PrimaryKeyRelatedField(
        queryset=SignalType.objects.all(),
        source="signal_type",
        write_only=True
    )

    severity = SignalSeveritySerializer(read_only=True)
    severity_id = serializers.PrimaryKeyRelatedField(
        queryset=SignalSeverity.objects.all(),
        source="severity",
        write_only=True
    )

    class Meta:
        model = Signal
        fields = [
            "id",
            "signal_type",
            "signal_type_id",
            "severity",
            "severity_id",
            "metadata",
            "resolved_at",
            "created_at",
            "updated_at",
        ]


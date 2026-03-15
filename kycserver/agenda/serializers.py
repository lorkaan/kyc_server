from rest_framework import serializers
from .models import AgendaEventType, AgendaEvent
from users.models import User


class AgendaEventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgendaEventType
        fields = ["id", "name", "description"]
        read_only_fields = ["id"]


class AgendaEventSerializer(serializers.ModelSerializer):
    # Nested event type
    event_type = AgendaEventTypeSerializer(read_only=True)
    event_type_id = serializers.PrimaryKeyRelatedField(
        queryset=AgendaEventType.objects.all(),
        source="event_type",
        write_only=True,
        required=False,
        allow_null=True
    )

    # Organizer
    organizer = serializers.StringRelatedField(read_only=True)
    organizer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="organizer",
        write_only=True,
        required=False,
        allow_null=True
    )

    # Computed fields
    is_past = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()

    class Meta:
        model = AgendaEvent
        fields = [
            "id",
            "title",
            "description",
            "event_type",
            "event_type_id",
            "start_time",
            "end_time",
            "all_day",
            "location",
            "organizer",
            "organizer_id",
            "status",
            "is_past"
        ]
        read_only_fields = ["id", "is_past"]

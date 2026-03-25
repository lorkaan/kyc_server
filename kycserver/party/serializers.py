from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType

from .models import PartyType, Party, PartyRelationship
import logging

logger = logging.getLogger()

# --- PartyType ---
class PartyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartyType
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# --- Party ---
class PartySerializer(serializers.ModelSerializer):
    party_type = serializers.SlugRelatedField(
        slug_field="code",
        queryset=PartyType.objects.filter(is_active=True)
    )

    content_type = serializers.SlugRelatedField(
        slug_field="model",
        queryset=ContentType.objects.all()
    )

    class Meta:
        model = Party
        fields = [
            "id",
            "party_type",
            "name",
            "is_active",
            "content_type",
            "object_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        """
        Optional: enforce uniqueness at serializer level for better UX
        """
        if Party.objects.filter(
            content_type=data.get("content_type"),
            object_id=data.get("object_id")
        ).exists():
            raise serializers.ValidationError(
                "A Party already exists for this entity."
            )
        return data


# --- PartyRelationship ---
class PartyRelationshipSerializer(serializers.ModelSerializer):
    party = serializers.PrimaryKeyRelatedField(
        queryset=Party.objects.all()
    )

    target_party = serializers.PrimaryKeyRelatedField(
        queryset=Party.objects.all()
    )

    class Meta:
        model = PartyRelationship
        fields = [
            "id",
            "party",
            "target_party",
            "role",
            "start_date",
            "end_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        """
        Prevent self-referencing relationships unless explicitly allowed
        """
        if data["party"] == data["target_party"]:
            raise serializers.ValidationError(
                "A party cannot have a relationship with itself."
            )

        # Optional: validate date logic
        if data.get("end_date") and data["end_date"] < data["start_date"]:
            raise serializers.ValidationError(
                "end_date cannot be before start_date."
            )

        return data
    
class PartyCreateSerializer(serializers.ModelSerializer):
    # Use SlugRelatedField to map 'party_type' from its code
    party_type = serializers.SlugRelatedField(
        slug_field="code",
        queryset=PartyType.objects.all()  # avoid filtered queryset for reliability
    )

    # Nested entity data, write_only so it doesn't appear in output
    data = serializers.JSONField(write_only=True)

    class Meta:
        model = Party
        fields = ["party_type", "name", "data"]

    def validate_party_type(self, value):
        # Ensure the party_type is active
        if not value.is_active:
            raise serializers.ValidationError("PartyType is not active")
        return value

    def create(self, validated_data):
        # Pop entity-specific data
        entity_data = validated_data.pop("data")
        party_type = validated_data["party_type"]
        logger.error(f"Entity Data: {entity_data}\nPartyType: {party_type}")
        # Dynamically create the underlying entity
        entity = party_type.create_entity(entity_data)

        # Create the Party instance
        party = Party.objects.create(
            content_object=entity,
            **validated_data
        )
        return party
    
# ---------- PARTY GRAPH SERIALIZERS ---------------------#

class PartyRefSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["existing", "new"])
    id = serializers.IntegerField(required=False)
    data = PartyCreateSerializer(required=False)

    def validate(self, data):
        if data["type"] == "existing" and not data.get("id"):
            raise serializers.ValidationError("Existing party requires id")
        if data["type"] == "new" and not data.get("data"):
            raise serializers.ValidationError("New party requires data")
        return data


class RelationshipInputSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=["in", "out"])
    party = PartyRefSerializer()
    role = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)


class PartyGraphSerializer(serializers.Serializer):
    main_party = PartyRefSerializer()
    relationships = RelationshipInputSerializer(many=True)
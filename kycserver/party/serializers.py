from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType

from .models import PartyType, Party, PartyRelationship


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
    
class PartyCreateSerializer(serializers.Serializer):
    party_type = serializers.SlugRelatedField(
        slug_field="code",
        queryset=PartyType.objects.filter(is_active=True)
    )
    name = serializers.CharField(max_length=255)
    data = serializers.JSONField()

    def create(self, validated_data):
        party_type = validated_data["party_type"]
        entity_data = validated_data["data"]

        # Create underlying entity dynamically
        entity = party_type.create_entity(entity_data)

        return Party.objects.create(
            party_type=party_type,
            name=validated_data["name"],
            content_object=entity
        )
    
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
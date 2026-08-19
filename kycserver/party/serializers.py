from django.apps import apps

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db import transaction

from .models import PartyType, Party, PartyRelationship


# --- PartyType ---
class PartyTypeSerializer(serializers.ModelSerializer):
    model_fields = serializers.SerializerMethodField()

    class Meta:
        model = PartyType
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_active",
            "created_at",
            "model_fields"
        ]
        read_only_fields = ["id", "created_at"]

    def get_model_fields(self, obj):
        return obj.get_model_fields()


# --- Party ---
class PartySerializer(serializers.ModelSerializer):
    party_type = serializers.SlugRelatedField(
        slug_field="code",
        read_only=True
    )

    entity_type = serializers.SerializerMethodField()

    entity = serializers.SerializerMethodField() 

    class Meta:
        model = Party
        fields = [
            "id",
            "party_type",
            "name",
            "is_active",
            "entity_type",
            "created_at",
            "entity",
            "updated_at",
        ]

    def get_entity_type(self, obj):
        return obj.content_type.model
    
    def get_entity(self, obj):
        target = obj.content_object
        if not target:
            return None

        if hasattr(target, "get_serialized_data"):
            return target.get_serialized_data()

        return {
            "id": str(target.pk),
            "repr": str(target),
        }

# --- PartyRelationship ---

def get_relationship_role_serializer():
    from kyc.serializers import RelationshipRoleSerializer
    return RelationshipRoleSerializer

class PartyRelationshipReadSerializer(serializers.ModelSerializer):

    party = PartySerializer()
    target_party = PartySerializer()
    role = get_relationship_role_serializer()()

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
                'contact'
            ]
            read_only_fields = ["id", "created_at", "updated_at"]

class PartyRelationshipUpdateSerializer(serializers.ModelSerializer):
    end_date = serializers.DateField(required=False, allow_null=True)
    contact = serializers.BooleanField(required=False)

    class Meta:
        model = PartyRelationship
        fields = ["end_date", "contact"]

    def validate(self, data):
        instance = self.instance

        # Handle end_date rules
        if "end_date" in data:
            # Prevent modifying once already set
            if instance.end_date is not None:
                raise ValidationError({
                    "end_date": "Cannot modify end_date once it is set."
                })

            # Prevent explicitly setting null (optional rule)
            if data["end_date"] is None:
                raise ValidationError({
                    "end_date": "Cannot be null once set."
                })

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
        # Dynamically create the underlying entity
        entity = party_type.create_entity(entity_data)

        # Create the Party instance
        party = Party.objects.create(
            content_object=entity,
            **validated_data
        )
        return party

class PartyInputField(serializers.Field):
    def to_internal_value(self, data):
        '''
        Accepts:
        {
            "type": "new",
            "party_type": "...",
            "name": "...",
            "data": {...}
        }

        OR

        {
            "type": "existing",
            "id": "uuid"
        }
        '''
        input_type = data.get("type")

        if input_type == "existing":
            party_id = data.get("id")
            if not party_id:
                raise serializers.ValidationError("ID is required for existing party")

            try:
                return Party.objects.get(pk=party_id)
            except Party.DoesNotExist:
                raise serializers.ValidationError("Party not found")

        elif input_type == "new":
            payload = data.get("data", data)

            serializer = PartyCreateSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            return serializer.save()

        else:
            raise serializers.ValidationError("Invalid type. Must be 'new' or 'existing'")

    def to_representation(self, value):
        # You can customize this later if needed
        return str(value.pk)
    
class PartyRelationshipSerializer(serializers.ModelSerializer):

    party = PartyInputField()
    target_party = PartyInputField()

    '''target_party = serializers.PrimaryKeyRelatedField(
        queryset=Party.objects.all()
    )'''

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
            'contact'
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        '''
        Prevent self-referencing relationships unless explicitly allowed
        '''
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
    
def get_relationship_role_model():
    return apps.get_model("kyc", "RelationshipRole")
    
class RelationshipInputSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=["in", "out"])
    party = PartyInputField()
    role = serializers.PrimaryKeyRelatedField(
        queryset=get_relationship_role_model().objects.all()
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    contact = serializers.BooleanField(required=False, default=False)

class PartyGraphSerializer(serializers.Serializer):
    party = PartyInputField()
    relationships = RelationshipInputSerializer(many=True)

    def create(self, validated_data):
        with transaction.atomic():
            main_party = validated_data["party"]
            relationships_data = validated_data.get("relationships", [])

            created_relationships = []

            for rel in relationships_data:
                other_party = rel["party"]

                if rel["direction"] == "out":
                    party = main_party
                    target_party = other_party
                else:
                    party = other_party
                    target_party = main_party

                relationship = PartyRelationship.objects.create(
                    party=party,
                    target_party=target_party,
                    role=rel["role"],
                    start_date=rel["start_date"],
                    end_date=rel.get("end_date"),
                    contact=rel.get("contact")
                )

                created_relationships.append(relationship)

            return {
                "party": main_party,
                "relationships": created_relationships
            }

class PartyGraphResponseSerializer(serializers.Serializer):
    party = PartySerializer()
    relationships = PartyRelationshipSerializer(many=True)
    




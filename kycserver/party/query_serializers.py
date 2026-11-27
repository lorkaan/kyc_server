from kyc.query_serializers import KYCRecordQuerySerializer

from .models import Party, PartyRelationship

from .serializers import PartyRelationshipMetadataSerializer
from rest_framework import serializers

class PartyQuerySerializer(serializers.ModelSerializer):

    party_type = serializers.SlugRelatedField(
        slug_field="code",
        read_only=True
    )

    entity_type = serializers.SerializerMethodField()

    entity = serializers.SerializerMethodField() 

    active_record = serializers.SerializerMethodField()  # I need this to be the latest only

    class Meta:
        model = Party
        fields = [
            "active_record"
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

    def get_active_record(self, obj):
        record = obj.current_records[0] if obj.current_records else None

        if record is None:
            return None

        return KYCRecordQuerySerializer(record).data

class PartyRelationshipQuerySerializer(serializers.ModelSerializer):
    metadata = PartyRelationshipMetadataSerializer(read_only=True)  # many?

    party = PartyQuerySerializer(read_only=True)
    target_party = PartyQuerySerializer(read_only=True)
    role = serializers.SerializerMethodField()

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
            'contact',
            'metadata'
        ]

    def get_role(self, obj):
            from kyc.serializers import RelationshipRoleSerializer
            return RelationshipRoleSerializer(obj.role).data
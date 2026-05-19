from rest_framework import serializers
from .models import SavedQuery, SavedQueryPermission
from users.models import User

class SavedQueryPermissionSerializer(serializers.ModelSerializer):
    target_type_display = serializers.CharField(
        source="get_target_type_display", read_only=True
    )
    level_display = serializers.CharField(
        source="get_level_display", read_only=True
    )

    class Meta:
        model = SavedQueryPermission
        fields = [
            "id",
            "target_type",
            "target_type_display",
            "target_id",
            "level",
            "level_display",
        ]

class SavedQuerySerializer(serializers.ModelSerializer):
    permissions = SavedQueryPermissionSerializer(many=True, read_only=True)

    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        allow_null=True,
        required=False
    )

    owner_username = serializers.CharField(
        source="owner.username", read_only=True
    )

    class Meta:
        model = SavedQuery
        fields = [
            "id",
            "name",
            "description",
            "model",
            "query",
            "owner",
            "owner_username",
            "is_system",
            "permissions",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """
        Enforce system-query ownership rules at serializer level
        (mirrors DB constraint for better API errors)
        """
        is_system = data.get("is_system", getattr(self.instance, "is_system", False))
        owner = data.get("owner", getattr(self.instance, "owner", None))

        if is_system and owner is not None:
            raise serializers.ValidationError(
                "System queries cannot have an owner."
            )

        return data

class SavedQueryPermissionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedQueryPermission
        fields = [
            "id",
            "query",
            "target_type",
            "target_id",
            "level",
        ]

    def validate(self, data):
        target_type = data.get("target_type")
        target_id = data.get("target_id")

        if target_type == SavedQueryPermission.TargetType.ALL and target_id:
            raise serializers.ValidationError(
                "ALL target type must not have a target_id."
            )

        if target_type != SavedQueryPermission.TargetType.ALL and not target_id:
            raise serializers.ValidationError(
                "target_id is required for this target type."
            )

        return data

class DynamicResultSerializer(serializers.ModelSerializer):
    target_name = serializers.SerializerMethodField()

    class Meta:
        model = None  # set dynamically
        fields = "__all__"

    def get_target_name(self, obj):
        # handles GenericForeignKey
        if hasattr(obj, "content_object") and obj.content_object:
            return getattr(obj.content_object, "name", None)
        return None
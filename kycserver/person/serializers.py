from rest_framework import serializers
from .models import Person

class PersonSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    date_of_death = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "last_name",
            "name",
            "full_name",
            "date_of_birth",
            "date_of_death",
            "created_at",
            "updated_at",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

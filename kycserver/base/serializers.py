from rest_framework import serializers

class HistoryEventSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"

class KeyConversionSerializer(serializers.ModelSerializer):

    CONVERSION_KEYS = {}
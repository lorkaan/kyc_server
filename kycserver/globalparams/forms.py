import json

from django import forms

from .models import (
    GlobalParameter,
    JsonValue,
    StringValue,
    IntValue,
    FloatValue,
    BooleanValue,
    UUIDValue,
    DateTimeValue,
)

VALUE_MODEL_MAP = {
    GlobalParameter.Type.STRING: StringValue,
    GlobalParameter.Type.INT: IntValue,
    GlobalParameter.Type.FLOAT: FloatValue,
    GlobalParameter.Type.BOOLEAN: BooleanValue,
    GlobalParameter.Type.UUID: UUIDValue,
    GlobalParameter.Type.DATETIME: DateTimeValue,
    GlobalParameter.Type.JSON: JsonValue
}


class GlobalParameterAdminForm(forms.ModelForm):
    value = forms.CharField(required=False, widget=forms.Textarea)  # will adapt dynamically

    class Meta:
        model = GlobalParameter
        fields = ["name", "description", "type", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = kwargs.get("instance")

        # If editing, preload existing value
        if instance and instance.content_object:
            self.fields["value"].initial = instance.content_object.get_value()

    def clean(self):
        cleaned = super().clean()

        param_type = cleaned.get("type")
        raw_value = cleaned.get("value")

        if raw_value in [None, ""]:
            return cleaned

        # Convert to correct type
        try:
            if param_type == GlobalParameter.Type.INT:
                cleaned["value"] = int(raw_value)
            elif param_type == GlobalParameter.Type.FLOAT:
                cleaned["value"] = float(raw_value)
            elif param_type == GlobalParameter.Type.BOOLEAN:
                cleaned["value"] = str(raw_value).lower() in ["true", "1", "yes"]
            elif param_type == GlobalParameter.Type.UUID:
                import uuid
                cleaned["value"] = uuid.UUID(raw_value)
            elif param_type == GlobalParameter.Type.DATETIME:
                from datetime import datetime
                cleaned["value"] = datetime.fromisoformat(raw_value)
            elif param_type == GlobalParameter.Type.JSON:
                # 👇 NEW: safe JSON parsing
                if isinstance(raw_value, (dict, list)):
                    cleaned["value"] = raw_value
                else:
                    cleaned["value"] = json.loads(raw_value)
            else:
                cleaned["value"] = str(raw_value)
        except Exception as e:
            raise forms.ValidationError(f"Invalid value for type {param_type}: {e}")

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit)

        value = self.cleaned_data.get("value")
        param_type = self.cleaned_data.get("type")

        if value is None:
            return instance

        value_model = VALUE_MODEL_MAP[param_type]

        # If existing value exists, update it
        existing = instance.content_object if instance.pk else None

        if existing and isinstance(existing, value_model):
            existing.value = value
            existing.parameter = instance
            existing.save()
            obj = existing
        else:
            # delete old if type changed
            if existing:
                existing.delete()

            obj = value_model.objects.create(
                value=value,
                parameter=instance
            )

        # attach via Generic FK
        instance.set_target(obj)

        return instance